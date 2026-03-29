import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()

PROXY_LIST = [
    "http://atftxamf:1p1a9yoim27z@31.59.20.176:6754",
    "http://atftxamf:1p1a9yoim27z@23.95.150.145:6114",
    "http://atftxamf:1p1a9yoim27z@198.23.239.134:6540",
    "http://atftxamf:1p1a9yoim27z@45.38.107.97:6014",
    "http://atftxamf:1p1a9yoim27z@107.172.163.27:6543",
    "http://atftxamf:1p1a9yoim27z@198.105.121.200:6462",
    "http://atftxamf:1p1a9yoim27z@216.10.27.159:6837",
    "http://atftxamf:1p1a9yoim27z@142.111.67.146:5611",
    "http://atftxamf:1p1a9yoim27z@191.96.254.138:6185",
    "http://atftxamf:1p1a9yoim27z@31.58.9.4:6077"
]

USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"]

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_valid_strict(title, price):
    t_f = title.lower()
    
    # 1. CZARNA LISTA
    bad_words = ["otwarte", "box only", "pusta", "pusty", "goala", "bez konsoli", "sama góra", "bluza", "pluszak", "shirt", "niemiecki", "german", "kasetka", "fifa", "pes 20", "mystery box", "replika", "repro"]
    if any(x in t_f for x in bad_words):
        return False, None, "Blacklist"

    # 2. KATEGORYZACJA
    cat = None
    if any(x in t_f for x in ["psp go", "psp-go"]): cat = "PSP_GO"
    elif any(x in t_f for x in ["ps vita", "psvita", "pstv"]): cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance"]): cat = "GB"
    elif any(x in t_f for x in ["booster", "bundle", "etb", "display", "sealed"]): cat = "POKE"
    
    if not cat: return False, None, "No Category Match"

    # 3. CENY (Weryfikacja okazji)
    limits = {"POKE": 300, "GB": 350, "PSP": 300, "PSP_GO": 450, "VITA": 550, "3DS": 550}
    min_p = {"POKE": 20, "GB": 40, "PSP": 40, "PSP_GO": 80, "VITA": 100, "3DS": 80}
    
    if price > limits.get(cat, 999): return False, cat, f"Price too high ({price} > {limits.get(cat)})"
    if price < min_p.get(cat, 0): return False, cat, f"Price too low ({price} < {min_p.get(cat)})"
    
    return True, cat, "OK"

def scrape_olx(query, silent=False):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&t={int(time.time())}"
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=12)
        if r.status_code == 200:
            data = r.json().get('data', [])
            for i, o in enumerate(data):
                found += 1
                title = o['title']
                url_item = o['url']
                
                # Wyciąganie ceny (poprawione)
                p_raw = o.get('price', {})
                price = None
                if 'regularPrice' in p_raw: price = p_raw['regularPrice'].get('value')
                elif 'value' in p_raw: price = p_raw['value']
                
                if price is not None:
                    price = float(price)
                    valid, cat, reason = is_valid_strict(title, price)
                    
                    # DIAGNOSTYKA: Pokaż pierwsze ogłoszenie z pętli, jeśli nic nie wysłano
                    if i == 0 and not silent:
                        log_debug(f"🔍 OLX PEEK [{query}]: '{title[:30]}' | {price}zł | Status: {reason}")
                        
                    if valid:
                        process_item(title, url_item, price, "OLX", silent)
    except Exception as e:
        log_debug(f"❌ OLX Error: {e}")
    return found

def scrape_vinted(session, query, silent=False):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            if not cards: return -1
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "days", "vakar"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link.get("title", ""), link['href'], price, "VINTED", silent)
        else: return -1
    except: return -1
    return found

def process_item(title, url, price, src, silent=False):
    clean_url = url.split("?")[0].rstrip("/")
    item_hash = hashlib.md5(f"{title[:50]}_{int(price)}".encode()).hexdigest()
    if item_hash in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, cat, reason = is_valid_strict(title, price)
    if not valid: return False
    
    if not silent:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": f"🎯 *HIT {src}*\n📦 *{title[:75]}*\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})", "parse_mode": "Markdown"})
        log_debug(f"🔥 WYSŁANO: {title[:30]}... ({price:.2f} zł)")
    
    SENT_HASHES.update([item_hash, clean_url])
    return True

def get_new_session():
    s = requests.Session()
    px = random.choice(PROXY_LIST)
    s.proxies.update({"http": px, "https": px})
    s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    log_debug(f"🌐 Nowe IP: {px.split('@')[-1]}")
    return s

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.25 - Diagnostyka OLX")
    vs = get_new_session()
    QUERIES = ["psp konsola", "ps vita", "3ds", "gameboy", "pokemon bundle", "pokemon booster"]
    
    # Cold start (bez powiadomień)
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    while True:
        v_total = o_total = 0
        v_blocked = False
        random.shuffle(QUERIES)
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(4, 7))
            if not v_blocked:
                res = scrape_vinted(vs, q)
                if res == -1: v_blocked = True
                else: v_total += res
                time.sleep(random.randint(10, 15))
        
        log_debug(f"Pętla OK. V({v_total}) O({o_total})")
        if v_blocked:
            log_debug("🔄 Zmiana Proxy...")
            vs.close()
            vs = get_new_session()
            time.sleep(5)
        else:
            time.sleep(random.randint(30, 60))
