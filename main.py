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
    
    # --- MIĘDZYNARODOWA CZARNA LISTA (ŚMIECI I PUSTE PUDEŁKA) ---
    # PL: puste, tylko pudełko | EN: empty, box only | RO: goala, fara | HU: nincs, üres | SE/DK: tom, kun
    bad_words = [
        "otwarte", "otwarty", "otwarta", "open", "opened",
        "empty", "empty box", "puste", "pudełko", "only box", "box only", "sama góra",
        "goala", "cutie goala", "fara", "nincs", "üres", "nincs benne", "without boosters",
        "tom", "kun box", "tom ask", "no console", "bez konsoli", "brak konsoli",
        "display only", "scatola", "leer", "nur box"
    ]
    
    if any(x in t_f for x in bad_words):
        return False, None

    # Filtr na "sztuki" (HU: db) - jeśli ktoś sprzedaje 1db, 2db (zazwyczaj single/śmieci)
    if re.search(r"\d\s?db", t_f) and "booster" not in t_f and price < 60:
        return False, None

    cat = None
    
    # 1. KATEGORYZACJA
    if "first partner" in t_f: 
        cat = "POKE_FIRST"
    elif any(x in t_f for x in ["pokemon day", "day 2026", "30th anniversary", "30th"]): 
        cat = "POKE_DAY"
    elif "etb" in t_f or "elite trainer box" in t_f:
        cat = "POKE_ETB"
    elif any(x in t_f for x in ["booster", "sealed", "slab", "box", "display", "bundle"]): 
        cat = "POKE_GEN"
    elif "psp go" in t_f: 
        cat = "PSP_GO"
    elif any(x in t_f for x in ["ps vita", "psvita"]): 
        cat = "VITA"
    elif "psp" in t_f: 
        cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): 
        cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance"]): 
        cat = "GB"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): 
        cat = "DS"
    
    if not cat: return False, None
    
    # 2. LIMITY CENOWE
    limits = {
        "POKE_ETB": 250, "POKE_FIRST": 150, "POKE_DAY": 80, "POKE_GEN": 200,    
        "GB": 370, "PSP": 300, "PSP_GO": 350, "VITA": 500, "3DS": 500, "DS": 250
    }
    
    # Wyższe ceny minimalne, żeby odciąć puste pudełka, które kosztują np. 30-50 zł
    min_p = {
        "POKE_ETB": 90, "POKE_FIRST": 30, "POKE_DAY": 25, "POKE_GEN": 35,
        "GB": 80, "PSP": 80, "PSP_GO": 150, "VITA": 180, "3DS": 120, "DS": 70
    }
    
    # SPECJALNY FILTR NA SINGLE (Karty):
    # Jeśli cena jest niska, a w tytule są słowa "kort", "karta", "card" - odrzucamy
    if any(x in t_f for x in ["kort", "karta", "card", "singiel"]) and price < 50:
        if "slab" not in t_f and "graded" not in t_f: # Chyba że to oceniona karta (slab)
            return False, None

    if price > limits.get(cat, 999) or price < min_p.get(cat, 0):
        return False, None
    
    # 3. FILTR KLONÓW
    if any(f in t_f for f in ["3d printed", "r36s", "r36h", "emulator", "klon", "drukarka"]):
        return False, None
        
    return True, cat

# ... (funkcje send_telegram, process_item, scrape_olx, scrape_vinted pozostają bez zmian)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def process_item(title, url, price, src, silent=False):
    clean_url = url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    if item_hash in SENT_HASHES or clean_url in SENT_HASHES: return False
    valid, cat = is_valid_strict(title, price)
    if not valid: return False
    if not silent:
        msg = f"🎯 *HIT {src}*\n📦 *{title[:70]}*\n💰 `{price:.2f} zł`\n🔗 [KUP TERAZ]({clean_url})"
        send_telegram(msg)
        log_debug(f"🔥 WYSŁANO: {title[:30]}... ({cat})")
    SENT_HASHES.add(item_hash)
    SENT_HASHES.add(clean_url)
    return True

def scrape_olx(query, silent=False):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
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
        r = session.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            for card in cards:
                found += 1
                txt = card.get_text(separator=" ")
                if any(x in txt.lower() for x in ["dni", "days", "dienas", "dage"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link.get("title", ""), link['href'], price, "VINTED", silent)
    except: pass
    return found

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.7 - START (Multi-Language Junk Filter)")
    vs = requests.Session()
    QUERIES = [
        "psp konsola", "psp go", "ps vita", "3ds konsola", "gameboy advance", 
        "pokemon booster bundle", "pokemon first partner", "pokemon day 2026", 
        "pokemon etb", "pokemon 30th anniversary"
    ]
    log_debug("Zaciągam obecne oferty (Cold Start)...")
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    log_debug(f"Baza gotowa ({len(SENT_HASHES)} linków).")
    while True:
        v_total = o_total = 0
        random.shuffle(QUERIES)
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(5, 10))
            v_total += scrape_vinted(vs, q)
            time.sleep(random.randint(15, 25))
        log_debug(f"Pętla OK. V({v_total}) O({o_total}).")
        time.sleep(random.randint(40, 80))
