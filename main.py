import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import hashlib

# --- CONFIG ---
# Używaj zmiennych środowiskowych dla bezpieczeństwa lub wpisz na sztywno poniżej
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_FILE = "sent_links.txt"
LOG_FILE = "sniper_debug.log"

# --- LOGGING ---
def log_debug(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")

# --- CORE LOGIC ---
def get_hash(title, price):
    """Tworzy unikalny identyfikator oferty na podstawie tytułu i ceny."""
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def score_deal(category, price):
    """Ocenia jak dobra jest oferta."""
    thresholds = {
        "GB": (120, 200),
        "PSP": (120, 180),
        "3DS": (250, 350),
        "DS_OLD": (100, 160),
        "POKE": (40, 100)
    }
    low, mid = thresholds.get(category, (999, 999))
    if price <= low: return "🔥 SUPER HIT"
    if price <= mid: return "🎯 HIT"
    return "🟡 OK"

def is_valid_strict(title, text, price):
    t_f = (title + " " + (text or "")).lower()
    
    # 1. Czarna lista (rozszerzona z obu kodów)
    forbidden = [
        "r36s", "g28", "arkos", "emulator", "retro konsola", "klon", "data frog",
        "m17", "r4", "adapter", "obudowa", "shell", "zamiennik", "części", "naprawa",
        "wyświetlacz", "lcd", "bateria", "ładowarka", "zasilacz", "etui", "case",
        "bulk", "cards", "energy", "holo", "reverse", "talia", "loose", "bootleg",
        "repro", "gra na", "sama gra", "płyta", "dyskietka", "sticker", "naklejka"
    ]
    
    if any(f in t_f for f in forbidden):
        return False, None

    # 2. Kategoryzacja
    cat = None
    if any(x in t_f for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "new 3ds", "2ds"]): cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl"]): cat = "DS_OLD"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed"]): cat = "POKE"
    
    if not cat: return False, None

    # 3. Progi cenowe
    limits = {"GB": 300, "PSP": 250, "3DS": 450, "DS_OLD": 200, "POKE": 160}
    min_prices = {"GB": 80, "PSP": 70, "3DS": 180, "DS_OLD": 70, "POKE": 15}
    
    if price > limits.get(cat, 999) or price < min_prices.get(cat, 0):
        return False, None

    # 4. Weryfikacja czy to konsola (dla kategorii sprzętowych)
    if cat != "POKE":
        is_console = any(word in t_f for word in ["konsola", "konsolę", "urządzenie", "system"])
        is_set = "zestaw" in title.lower()
        if not (is_console or is_set):
            return False, None

    return True, cat

# --- PROCESSING & TELEGRAM ---
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        log_debug(f"TG ERROR: {e}")

def process_item(title, url, price, text, src):
    full_url = url if "http" in url else f"https://www.vinted.pl{url}"
    clean_url = full_url.split("?")[0].rstrip("/")
    
    item_hash = get_hash(title, price)
    if item_hash in sent_hashes or clean_url in sent_hashes:
        return

    valid, cat = is_valid_strict(title, text, price)
    if not valid:
        return

    score = score_deal(cat, price)
    
    msg = (
        f"{score} | {src}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{title[:70]}*\n"
        f"💰 Cena: `{price:.2f} zł`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [KUP TERAZ]({clean_url})"
    )

    send_telegram(msg)
    log_debug(f"WYSŁANO: {title} ({price}zł)")
    
    sent_hashes.add(item_hash)
    sent_hashes.add(clean_url)
    with open(SENT_FILE, "a") as f:
        f.write(f"{item_hash}\n{clean_url}\n")

# --- SCRAPERS ---
def get_headers():
    return {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,130)}.0.0.0"}

def scrape_olx(query):
    url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
    try:
        r = requests.get(url, headers=get_headers(), timeout=10)
        data = r.json().get('data', [])
        for o in data:
            price_data = o.get('price', {}).get('value', {}) or o.get('price', {})
            price = price_data.get('amount')
            if price:
                process_item(o['title'], o['url'], float(price), o.get('description', ""), "OLX")
    except Exception as e:
        log_debug(f"OLX ERROR ({query}): {e}")

def scrape_vinted(session, query):
    url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
    try:
        # Vinted wymaga wejścia na stronę główną najpierw, aby pobrać ciastka (sesja to załatwia)
        r = session.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
        
        for card in cards:
            link_tag = card.find("a", href=True)
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", card.get_text(separator=" "))
            if link_tag and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link_tag.get("title", ""), link_tag['href'], price, "", "VINTED")
    except Exception as e:
        log_debug(f"VINTED ERROR ({query}): {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_hashes = set(open(SENT_FILE).read().split())
    
    QUERIES = [
        "psp konsola", "3ds konsola", "dsi konsola", 
        "gameboy advance", "pokemon booster bundle", "pokemon slab"
    ]
    
    vinted_session = requests.Session()
    # Inicjalizacja sesji Vinted
    try:
        vinted_session.get("https://www.vinted.pl", headers=get_headers())
    except:
        pass

    print(f"🚀 SNIPER v13 START | LOGI: {LOG_FILE}")
    
    while True:
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(5, 10))
            
            scrape_vinted(vinted_session, q)
            time.sleep(random.randint(20, 40)) # Vinted jest wrażliwy na banowanie
            
        time.sleep(30)
