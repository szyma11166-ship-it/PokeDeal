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

# Wklej tutaj swoje proxy (np. z darmowego Webshare)
# Format: "http://username:password@ip:port"
PROXY_LIST = [
    # "http://twoj_login:twoje_haslo@p.webshare.io:80", 
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
    
    # 1. CZARNA LISTA
    bad_words = [
        "otwarte", "otwarty", "otwarta", "open", "opened", "nincs", "üres", 
        "empty", "box only", "puste", "goala", "cutie goala", "fara", "tom", 
        "without boosters", "nincs benne", "no console", "bez konsoli", "sama góra",
        "bluza", "plush", "plusz", "pluszak", "koszulka", "shirt", "używany kod", "pudełko po",
        "japanese", "japoński", "japońskie", "jp", "jap", "korean", "koreański", "kor",
        "german", "deutsch", "niemiecki", " de ", "chinese", "chiński", "spanish", "hiszpański", "esp",
        "french", "francuski", "it", "italian", "włoski", "kártya", "magyar",
        " gra", "gry ", "igre", "hry", "spil", "juego", "jeu", "cartridge", "kasetka", "kassette",
        "zelda", "mario", "pokemon y", "pokemon x", "pokemon sun", "pokemon moon", "fantasy life",
        "animal crossing", "žárovky",
        "lego", "r36s", "r36h", "r35s", "r36x", "miyoo", "anbernic", "trimui", "rg35xx", "fx40", "fx 40",
        "mystery", "mystery box", "niespodzianka", "paczka niespodzianka", "repack",
        "destined rivals", "perfect order", "gem pack", "brilliant fantasy", "ascended heroes",
        "mega evolution", "glory of", "super electric", "proxy", "diy", "custom", "aliexpress", 
        "temu", "zamiennik", "replika", "bootleg", "repro", "reprodukcja", "journey together",
        "trick or trade", "celebrations 25"
    ]
    
    if "game" in t_f and "gameboy" not in t_f and "game boy" not in t_f and "gamecube" not in t_f:
        return False, None

    if any(x in t_f for x in bad_words):
        return False, None

    if re.search(r"\d\s?db\b", t_f) and "booster" not in t_f and price < 60:
        return False, None
    if re.search(r"\d{1,3}/\d{3}", t_f) and price < 60 and "slab" not in t_f:
        return False, None

    cat = None
    if "first partner" in t_f: cat = "POKE_FIRST"
    elif any(x in t_f for x in ["pokemon day", "day 2026", "30th anniversary", "30th"]): cat = "POKE_DAY"
    elif "etb" in t_f or "elite trainer box" in t_f: cat = "POKE_ETB"
    elif any(x in t_f for x in ["booster", "sealed", "display", "bundle", "tin", "shrouded", "surging"]) or re.search(r"\b(box|slab)\b", t_f): cat = "POKE_GEN"
    elif "psp go" in t_f: cat = "PSP_GO"
    elif any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance", "color"]): cat = "GB"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): cat = "DS"
    
    if not cat: return False, None
    
    limits = {"POKE_ETB": 250, "POKE_FIRST": 150, "POKE_DAY": 80, "POKE_GEN": 200, "GB": 300, "PSP": 300, "PSP_GO": 350, "VITA": 500, "3DS": 500, "DS": 250}
    min_p = {"POKE_ETB": 95, "POKE_FIRST": 30, "POKE_DAY": 15, "POKE_GEN": 35, "GB": 80, "PSP": 80, "PSP_GO": 150, "VITA": 180, "3DS": 120, "DS": 70}
    
    if any(x in t_f for x in ["kort", "karta", "card"]) and price < 50:
        if "slab" not in t_f and "graded" not in t_f:
            return False, None

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
                p = (o.get('price', {}).get('value', {}) or o.get('price', {})).get('amount')
                if p: process_item(o['title'], o['url'], float(p), "OLX", silent)
    except: pass
    return found

def scrape_vinted(session, query, silent=False):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first&random={random.random()}"
        r = session.get(url, headers={"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "pl-PL,pl;q=0.9"}, timeout=12)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            
            # WYKRYWANIE CICHEGO BANA - Jeśli nie ma żadnych kart, a szukamy popularnej rzeczy, to ban.
            if not cards:
                log_debug(f"❌ VINTED: Cichy ban (0 ofert dla '{query}')")
                return -1
                
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "days", "dienas", "dage", "vakar"]): continue
                
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link.get("title", ""), link['href'], price, "VINTED", silent)
        else:
            log_debug(f"❌ VINTED: Blokada HTTP {r.status_code}")
            return -1
    except Exception: return -1
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
    s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    if PROXY_LIST:
        px = random.choice(PROXY_LIST)
        s.proxies.update({"http": px, "https": px})
        log_debug(f"🌐 Podpięto nowe IP proxy")
    return s

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.19 - Proxy Ready & Ghost Ban Fix")
    vs = get_new_session()
    QUERIES = ["psp konsola", "ps vita", "3ds", "gameboy", "booster bundle", "pokemon bundle", "pokemon booster", "shrouded fable", "pokemon day", "pokemon 30th"]
    log_debug("Cold Start...")
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    log_debug(f"Gotowe. Baza: {len(SENT_HASHES)} linków.")
    
    while True:
        v_total = o_total = 0
        vinted_blocked_in_this_loop = False
        random.shuffle(QUERIES)
        
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(5, 8)) 
            if not vinted_blocked_in_this_loop:
                v_res = scrape_vinted(vs, q)
                if v_res == -1: vinted_blocked_in_this_loop = True
                else:
                    v_total += v_res
                    time.sleep(random.randint(15, 25))
        
        log_debug(f"Pętla OK. V({v_total}) O({o_total})")
        
        if vinted_blocked_in_this_loop:
            vs.close()
            if PROXY_LIST:
                log_debug("🔄 Blokada! Zmieniam IP przez Proxy i robię szybki reset (30s)...")
                time.sleep(30)
            else:
                log_debug("🔄 Blokada! Brak Proxy. Czekam 15 minut na odblokowanie Twojego IP...")
                time.sleep(900)
            vs = get_new_session()
            log_debug("✅ Wybudzono. Wznawiam polowanie.")
        else:
            time.sleep(random.randint(45, 90))
