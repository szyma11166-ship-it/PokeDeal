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
SENT_FILE = "sent_links.txt"

def get_hash(title, price):
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_valid_strict(title, text, price):
    t_f = (title + " " + (text or "")).lower()
    
    # 1. KATEGORYZACJA
    cat = None
    if any(x in t_f for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds", "n2ds"]): cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl", "ds "]): cat = "DS_OLD"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed"]): cat = "POKE"
    
    if not cat: return False, None

    # 2. PROGI CENOWE
    limits = {"GB": 300, "PSP": 250, "3DS": 450, "DS_OLD": 200, "POKE": 160}
    min_prices = {"GB": 80, "PSP": 70, "3DS": 180, "DS_OLD": 70, "POKE": 15}
    
    if price > limits.get(cat, 999) or price < min_prices.get(cat, 0):
        return False, None

    # 3. LOGIKA: CZY TO SPRZĘT CZY ŚMIEĆ?
    # Rozszerzona lista słów potwierdzających urządzenie/zestaw
    hw_keywords = [
        "konsola", "konsolę", "zestaw", "box", "cib", "komplet", "sprawna", "isps",
        "1004", "2004", "3004", "1000", "2000", "3000", "street", "e1004", "psp go", 
        "xl", "ll", "lite", "classic", "fat", "dmg-01", "agb-001", "ags-001", "ags-101",
        "pikachu", "zelda", "mario edition", "pokemon edition"
    ]
    
    is_hardware = any(hw in t_f for hw in hw_keywords)

    # TWARDA CZARNA LISTA (Odrzuca zawsze)
    hard_forbidden = [
        "r36s", "g28", "arkos", "emulator", "klon", "data frog", "repro", 
        "naklejka", "sticker", "3d printed", "drukarka 3d", "wydruk 3d", "druk 3d"
    ]
    if any(f in t_f for f in hard_forbidden):
        return False, None

    # MIĘKKA CZARNA LISTA (Odrzuca TYLKO jeśli NIE wykryto sprzętu z hw_keywords)
    soft_forbidden = [
        "adapter", "obudowa", "shell", "zamiennik", "części", "naprawa",
        "wyświetlacz", "lcd", "bateria", "ładowarka", "zasilacz", "etui", "case",
        "płyta główna", "analog", "gumki", "przyciski", "szkiełko", "r4", "karta"
    ]

    if not is_hardware:
        # Jeśli nie mamy potwierdzenia, że to konsola, a mamy słowo z soft_forbidden -> out
        if any(s in t_f for s in soft_forbidden):
            return False, None
        # Jeśli to nie karty Pokemon i nie ma słowa "konsola/model" -> out
        if cat != "POKE":
            return False, None

    return True, cat

# --- POZOSTAŁE FUNKCJE ---

def score_deal(category, price):
    thresholds = {"GB": (120, 200), "PSP": (120, 180), "3DS": (250, 350), "DS_OLD": (100, 160), "POKE": (40, 100)}
    low, mid = thresholds.get(category, (999, 999))
    if price <= low: return "🔥 SUPER HIT"
    if price <= mid: return "🎯 HIT"
    return "🟡 OK"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def process_item(title, url, price, text, src):
    full_url = url if "http" in url else f"https://www.vinted.pl{url}"
    clean_url = full_url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    
    if item_hash in sent_hashes or clean_url in sent_hashes: return

    valid, cat = is_valid_strict(title, text, price)
    if not valid: return

    score = score_deal(cat, price)
    msg = f"{score} | {src}\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_url})"
    
    send_telegram(msg)
    sent_hashes.add(item_hash)
    sent_hashes.add(clean_url)
    with open(SENT_FILE, "a") as f: f.write(f"{item_hash}\n{clean_url}\n")

def scrape_olx(query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,130)}"}
    try:
        r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
        for o in r.json().get('data', []):
            p_data = o.get('price', {}).get('value', {}) or o.get('price', {})
            p = p_data.get('amount')
            if p: process_item(o['title'], o['url'], float(p), o.get('description', ""), "OLX")
    except: pass

def scrape_vinted(session, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,130)}"}
    try:
        r = session.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
            link = card.find("a", href=True)
            txt = card.get_text(separator=" ")
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
            if link and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link.get("title", ""), link['href'], price, "", "VINTED")
    except: pass

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_hashes = set(open(SENT_FILE).read().split())
    vinted_session = requests.Session()
    
    QUERIES = ["psp konsola", "3ds konsola", "dsi konsola", "gameboy advance", "pokemon booster bundle", "pokemon slab"]
    
    print("🚀 SNIPER v15 START | NO 3D PRINTED | SMART FILTERS")
    while True:
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(10, 15))
            scrape_vinted(vinted_session, q)
            time.sleep(random.randint(25, 35))
