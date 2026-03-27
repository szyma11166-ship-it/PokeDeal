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
    cat = None
    warning = ""
    
    # WYKLUCZENIA (Wii U i Klony)
    if any(x in t_f for x in ["wii u", "wiiu", "r36s", "r36h", "emulator", "klon", "3d printed"]):
        return False, None, ""

    # KATEGORYZACJA
    if "micro" in t_f and ("gameboy" in t_f or "gba" in t_f): 
        cat = "GB_MICRO"
    elif "game" in t_f and "watch" in t_f: 
        cat = "G_WATCH"
    elif any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance"]): 
        cat = "GB"
    elif "psp go" in t_f: 
        cat = "PSP_GO"
    elif "ps vita" in t_f or "psvita" in t_f: 
        cat = "VITA"
    elif "psp" in t_f: 
        cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): 
        cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): 
        cat = "DS"
    elif any(x in t_f for x in ["booster", "sealed", "slab", "box", "first partner", "pokemon day", "day 2026"]): 
        cat = "POKE"
    
    # FILTR STANU (JUNK / USZKODZONE)
    if any(x in t_f for x in ["uszkodzon", "nietestowan", "na części", "brak klapki", "porysowan", "do naprawy"]):
        if price <= 110: # Bardzo tanie uszkodzone to okazja na części
            cat = "JUNK"
        else:
            return False, None, "" # Droższe uszkodzone ignorujemy

    if not cat: return False, None, ""
    
    # LIMITY CENOWE
    limits = {
        "GB": 370, "PSP": 300, "PSP_GO": 350, "VITA": 500, 
        "3DS": 500, "DS": 250, "POKE": 220, "GB_MICRO": 450, 
        "G_WATCH": 150, "JUNK": 115
    }
    min_p = {
        "GB": 50, "PSP": 50, "PSP_GO": 100, "VITA": 150, 
        "3DS": 100, "DS": 50, "POKE": 5, "GB_MICRO": 100, 
        "G_WATCH": 40, "JUNK": 10
    }
    
    if price > limits.get(cat, 999) or price < min_p.get(cat, 0):
        return False, None, ""

    # WYKRYWANIE FAKE (Dla popularnych gier Pokemon na GBA/GBC)
    if any(x in t_f for x in ["emerald", "firered", "leafgreen", "ruby", "sapphire", "crystal"]):
        if price < 85:
            warning = "\n⚠️ *UWAGA: Podejrzanie niska cena! Może to być REPRO (podróbka).* "

    return True, cat, warning

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def process_item(title, url, price, src, silent=False):
    clean_url = url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    
    if item_hash in SENT_HASHES or clean_url in SENT_HASHES:
        return False

    valid, cat, warn = is_valid_strict(title, price)
    if not valid:
        return False

    if not silent:
        tag = f"#{cat}"
        msg = f"🎯 *HIT {src}* {tag}\n📦 *{title[:70]}*\n💰 `{price:.2f} zł`{warn}\n🔗 [KUP TERAZ]({clean_url})"
        send_telegram(msg)
        log_debug(f"🔥 WYSŁANO: [{cat}] {title[:30]}...")
    
    SENT_HASHES.add(item_hash)
    SENT_HASHES.add(clean_url)
    return True

# --- SCRAPERY BEZ ZMIAN (v17.1 logic) ---
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
    log_debug("🚀 SNIPER v17.3 - PRO MODE (Micro, Junk, Fake Alert)")
    vs = requests.Session()
    
    QUERIES = [
        "psp konsola", "psp go", "ps vita konsola",
        "3ds konsola", "gameboy advance", "gameboy micro",
        "nintendo game watch", "stara konsola nintendo",
        "pokemon booster bundle", "pokemon first partner", "pokemon day 2026"
    ]
    
    log_debug("Zaciągam obecne oferty...")
    for q in QUERIES:
        scrape_olx(q, silent=True)
        scrape_vinted(vs, q, silent=True)
    
    log_debug(f"Baza gotowa ({len(SENT_HASHES)} linków). Start.")

    while True:
        v_total, o_total = 0, 0
        random.shuffle(QUERIES)
        for q in QUERIES:
            o_total += scrape_olx(q)
            time.sleep(random.randint(5, 10))
            v_total += scrape_vinted(vs, q)
            time.sleep(random.randint(15, 25))
        log_debug(f"Pętla OK. Vinted({v_total}), OLX({o_total}).")
        time.sleep(random.randint(40, 80))
