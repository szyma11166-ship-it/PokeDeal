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

USER_AGENTS = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"]

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_valid_strict(title, price):
    t_f = title.lower()
    
    # Rozszerzona czarna lista na akcesoria i usługi
    bad = [
        "otwarte", "box only", "pusta", "pusty", "goala", "mystery box", "replika", "repro",
        "ładowarka", "kabel", "etui", "pokrowiec", "case", "serwis", "naprawa", "modyfikacja",
        "odblokowanie", " przeróbka", "części", "uszkodzona", "uszkodzone", "display only",
        "czytnik", "r36s", "anbernic", "data frog", "zamienię", "wymiana"
    ]
    
    if any(x in t_f for x in bad): return False, None
    if price <= 5: return False, None # Ignoruj ceny 0 i 1-5 zł (spam)

    cat = None
    if any(x in t_f for x in ["psp go", "psp-go"]): cat = "PSP_GO"
    elif any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance"]): cat = "GB"
    elif any(x in t_f for x in ["booster", "bundle", "etb", "display", "sealed"]): cat = "POKE"
    
    if not cat: return False, None
    
    # Limity cenowe (możesz dostosować)
    limits = {"POKE": 400, "GB": 450, "PSP": 350, "PSP_GO": 550, "VITA": 650, "3DS": 650}
    if price > limits.get(cat, 999): return False, None
    
    return True, cat

def scrape_olx(query, silent=False):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&t={int(time.time())}"
        r = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=10)
        if r.status_code == 200:
            items = r.json().get('data', [])
            for o in items:
                found += 1
                title = o.get('title', '')
                url_item = o.get('url', '')
                price = None
                
                # Przeszukiwanie parametrów pod kątem ceny
                for p in o.get('params', []):
                    if p.get('key') == 'price':
                        val = p.get('value', {})
                        if isinstance(val, dict): price = val.get('value')
                
                if price is not None:
                    process_item(title, url_item, float(price), "OLX", silent)
    except: pass
    return found

def scrape_vinted(session, query, silent=False):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            if not cards: return -1
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "days"]): continue
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
    h = hashlib.md5(f"{title[:40]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, cat = is_valid_strict(title, price)
    if not valid: return False
    
    if not silent:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": f"🎯 *HIT {src}*\n📦 *{title[:75]}*\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})", "parse_mode": "Markdown"})
        log_debug(f"🔥 WYSŁANO: {title[:30]}... ({price:.2f} zł)")
    
    SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
    return True

def get_new_session():
    s = requests.Session()
    px = random.choice(PROXY_LIST)
    s.proxies.update({"http": px, "https": px})
    s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    return s

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.28 - Deep Filtering Active")
    vs = get_new_session()
    QUERIES = ["psp konsola", "ps vita", "3ds", "gameboy", "pokemon bundle", "pokemon booster"]
    
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    while True:
        v_total = o_total = 0
        v_blocked = False
        random.shuffle(QUERIES)
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(4, 8))
            if not v_blocked:
                res = scrape_vinted(vs, q)
                if res == -1: v_blocked = True
                else: v_total += res
                time.sleep(random.randint(12, 18))
        
        log_debug(f"Status OK: V({v_total}) O({o_total}). Baza: {len(SENT_HASHES)}")
        if v_blocked:
            log_debug("🔄 Blokada Vinted -> Zmiana IP")
            vs.close(); vs = get_new_session()
            time.sleep(10)
        else:
            time.sleep(random.randint(40, 70))
