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

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def get_hash(title, price):
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_valid_strict(title, price):
    t_f = title.lower()
    
    # 1. CZARNA LISTA (Śmieci + Języki których NIE CHCESZ)
    bad_words = [
        # Śmieci/Puste
        "otwarte", "otwarty", "otwarta", "open", "opened", "nincs", "üres", 
        "empty", "box only", "puste", "goala", "cutie goala", "fara", "tom", 
        "without boosters", "nincs benne", "no console", "bez konsoli", "sama góra",
        "bluza", "plush", "plusz", "pluszak", "koszulka", "shirt", "używany kod", "pudełko po",
        
        # JĘZYKI DO BLOKADY (Japońskie, Koreańskie, Niemieckie, itp.)
        "japanese", "japoński", "japońskie", "japońska", "jp", "jap", 
        "korean", "koreański", "koreańska", "kor",
        "german", "deutsch", "niemiecki", "niemiecka", "niemieckie", " de ",
        "chinese", "chiński", "chińska", "spanish", "hiszpański", "esp",
        "french", "francuski", "it", "italian", "włoski"
    ]
    
    # Sprawdzanie czy którykolwiek "bad word" występuje jako osobne słowo lub fraza
    if any(x in t_f for x in bad_words):
        return False, None

    # 2. FILTRY SPECJALISTYCZNE
    if re.search(r"\d\s?db\b", t_f) and "booster" not in t_f and price < 60:
        return False, None
    if re.search(r"\d{1,3}/\d{3}", t_f) and price < 60 and "slab" not in t_f:
        return False, None

    cat = None
    
    # 3. KATEGORYZACJA
    if "first partner" in t_f: 
        cat = "POKE_FIRST"
    elif any(x in t_f for x in ["pokemon day", "day 2026", "30th anniversary", "30th"]): 
        cat = "POKE_DAY"
    elif "etb" in t_f or "elite trainer box" in t_f:
        cat = "POKE_ETB"
    elif any(x in t_f for x in ["booster", "sealed", "display", "bundle", "tin", "shrouded", "surging"]) or re.search(r"\b(box|slab)\b", t_f): 
        cat = "POKE_GEN"
    elif "psp go" in t_f: 
        cat = "PSP_GO"
    elif any(x in t_f for x in ["ps vita", "psvita"]): 
        cat = "VITA"
    elif "psp" in t_f: 
        cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): 
        cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance", "color"]): 
        cat = "GB"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): 
        cat = "DS"
    
    if not cat: return False, None
    
    # 4. LIMITY CENOWE
    limits = {
        "POKE_ETB": 250, "POKE_FIRST": 150, "POKE_DAY": 80, "POKE_GEN": 200,    
        "GB": 300, "PSP": 300, "PSP_GO": 350, "VITA": 500, "3DS": 500, "DS": 250
    }
    
    min_p = {
        "POKE_ETB": 95, "POKE_FIRST": 30, "POKE_DAY": 15, "POKE_GEN": 35,
        "GB": 80, "PSP": 80, "PSP_GO": 150, "VITA": 180, "3DS": 120, "DS": 70
    }
    
    # Anty-Single (Karty)
    if any(x in t_f for x in ["kort", "karta", "card"]) and price < 50:
        if "slab" not in t_f and "graded" not in t_f:
            return False, None

    if price > limits.get(cat, 999) or price < min_p.get(cat, 0):
        return False, None
        
    return True, cat

# --- Reszta kodu bez zmian (scrape_olx, scrape_vinted, process_item, send_telegram) ---

def scrape_olx(query, silent=False):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Accept": "application/json", "Referer": "https://m.olx.pl/"
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            data = r.json().get('data', [])
            for o in data:
                found += 1
                p_data = o.get('price', {}).get('value', {}) or o.get('price', {})
                p = p_data.get('amount')
                if p: process_item(o['title'], o['url'], float(p), "OLX", silent)
    except: pass
    return found

def scrape_vinted(session, query, silent=False):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first&random={random.random()}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"}
        r = session.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "days", "dienas", "dage", "vakar"]): continue
                
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link.get("title", ""), link['href'], price, "VINTED", silent)
    except: pass
    return found

def process_item(title, url, price, src, silent=False):
    clean_url = url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    if item_hash in SENT_HASHES or clean_url in SENT_HASHES: return False
    valid, cat = is_valid_strict(title, price)
    if not valid: return False
    if not silent:
        msg = f"🎯 *HIT {src}*\n📦 *{title[:75]}*\n💰 `{price:.2f} zł`\n🔗 [KUP TERAZ]({clean_url})"
        send_telegram(msg)
        log_debug(f"🔥 WYSŁANO: {title[:30]}... ({price:.2f} zł)")
    SENT_HASHES.add(item_hash)
    SENT_HASHES.add(clean_url)
    return True

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.12 - START (No Japanese/German/Korean)")
    vs = requests.Session()
    QUERIES = [
        "psp konsola", "ps vita", "3ds", "gameboy", 
        "booster bundle", "pokemon bundle", "pokemon booster", 
        "shrouded fable", "pokemon day", "pokemon 30th"
    ]
    log_debug("Cold Start...")
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    log_debug(f"Gotowe. Baza: {len(SENT_HASHES)} linków.")
    while True:
        v_total = o_total = 0
        random.shuffle(QUERIES)
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(5, 8))
            v_total += scrape_vinted(vs, q)
            time.sleep(random.randint(10, 15))
        log_debug(f"Pętla OK. V({v_total}) O({o_total})")
        time.sleep(random.randint(30, 60))
