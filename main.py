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

# --- TWOJE PROXY Z WEBSHARE (Zintegrowane v17.24) ---
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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:123.0) Gecko/20100101 Firefox/123.0"
]

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def get_hash(title, price):
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_valid_strict(title, price):
    t_f = title.lower()
    
    # CZARNA LISTA (Wide Net - Puszczamy japońskie, blokujemy śmieci)
    bad_words = [
        "otwarte", "otwarty", "otwarta", "open", "opened", "üres", "empty", "box only", 
        "pusta", "pusty", "puste", "pustą", "goala", "goale", "fara", "no console", 
        "bez konsoli", "bez kart", "bez kartek", "sama góra", "bluza", "plush", "plusz", 
        "pluszak", "shirt", "używany kod", "pudełko po", "german", "deutsch", "niemiecki", 
        "spanish", "hiszpański", "esp", "french", "francuski", "cartridge", "kasetka", 
        "fifa", "pes 20", "serum", "reedle", "krem", "vt cosmetics", "mystery box", 
        "repack", "proxy", "diy", "custom", "aliexpress", "temu", "zamiennik", "replika", 
        "bootleg", "repro", "reprodukcja", "trick or trade"
    ]

    if any(x in t_f for x in bad_words):
        return False, None

    cat = None
    if "first partner" in t_f: cat = "POKE_FIRST"
    elif any(x in t_f for x in ["pokemon day", "day 2026", "30th anniversary"]): cat = "POKE_DAY"
    elif "etb" in t_f or "elite trainer box" in t_f: cat = "POKE_ETB"
    elif any(x in t_f for x in ["booster", "sealed", "display", "bundle", "tin", "shrouded", "surging"]) or "box" in t_f or "slab" in t_f: cat = "POKE_GEN"
    elif "psp go" in t_f: cat = "PSP_GO"
    elif "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance", "color"]): cat = "GB"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): cat = "DS"
    
    if not cat: return False, None
    
    # CENY OKAZJI (Łapiemy wszystko co tanie)
    limits = {"POKE_ETB": 250, "POKE_FIRST": 150, "POKE_DAY": 80, "POKE_GEN": 200, "GB": 300, "PSP": 300, "PSP_GO": 350, "VITA": 500, "3DS": 500, "DS": 250}
    min_p = {"POKE_ETB": 40, "POKE_FIRST": 10, "POKE_DAY": 10, "POKE_GEN": 10, "GB": 30, "PSP": 30, "PSP_GO": 70, "VITA": 70, "3DS": 50, "DS": 30}
    
    if price > limits.get(cat, 999) or price < min_p.get(cat, 0): return False, None
    return True, cat

def scrape_olx(query, silent=False):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&t={int(time.time())}"
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=12)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                found += 1
                price_data = o.get('price', {})
                p = None
                if isinstance(price_data, dict):
                    if 'regularPrice' in price_data: p = price_data.get('regularPrice', {}).get('value')
                    elif 'value' in price_data: p = price_data.get('value')
                
                if p is not None: 
                    process_item(o['title'], o['url'], float(p), "OLX", silent)
    except: pass
    return found

def scrape_vinted(session, query, silent=False):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first&random={random.random()}"
        r = session.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=12)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            if not cards: return -1 # Sygnał cichego bana
                
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "days", "dienas", "dage", "vakar"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link.get("title", ""), link['href'], price, "VINTED", silent)
        else: return -1 # Błąd połączenia
    except: return -1
    return found

def process_item(title, url, price, src, silent=False):
    clean_url = url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    if item_hash in SENT_HASHES or clean_url in SENT_HASHES: return False
    valid, cat = is_valid_strict(title, price)
    if not valid: return False
    if not silent:
        send_telegram(f"🎯 *HIT {src}*\n📦 *{title[:75]}*\n💰 `{price:.2f} zł`\n🔗 [KUP TERAZ]({clean_url})")
        log_debug(f"🔥 WYSŁANO: {title[:30]}... ({price:.2f} zł)")
    SENT_HASHES.update([item_hash, clean_url])
    return True

def send_telegram(msg):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_new_session():
    s = requests.Session()
    px = random.choice(PROXY_LIST)
    s.proxies.update({"http": px, "https": px})
    s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    log_debug(f"🌐 Nowa sesja na IP: {px.split('@')[-1]}")
    return s

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.24 - Proxy & OLX Fix Live")
    vs = get_new_session()
    QUERIES = ["psp konsola", "ps vita", "3ds", "gameboy", "booster bundle", "pokemon bundle", "pokemon booster", "shrouded fable", "pokemon day", "pokemon 30th"]
    
    log_debug("Cold Start...")
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    log_debug(f"Baza: {len(SENT_HASHES)} linków.")
    
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
                else: 
                    v_total += res
                    time.sleep(random.randint(12, 18))
        
        log_debug(f"Pętla OK. V({v_total}) O({o_total})")
        
        if v_blocked:
            log_debug("🔄 Blokada Vinted! Zmiana proxy...")
            vs.close()
            vs = get_new_session()
            time.sleep(10)
        else:
            time.sleep(random.randint(30, 60))
