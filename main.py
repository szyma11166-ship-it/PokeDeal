import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import hashlib
import sys

# --- CONFIG ---
# Pobiera z Railway Variables, a jeśli ich brak, używa Twoich danych
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_FILE = "sent_links.txt"
LOG_FILE = "sniper_debug.log"

# --- LOGGING ---
def log_debug(msg):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    full_msg = f"{timestamp} | {msg}"
    # Zapis do pliku dla bezpieczeństwa
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except:
        pass
    # Wypisanie w konsoli Railway (flush=True wymusza natychmiastowe pokazanie logu)
    print(full_msg, flush=True)

# --- CORE LOGIC ---
def get_hash(title, price):
    """Generuje unikalny hash oferty, aby nie wysyłać duplikatów."""
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_valid_strict(title, text, price):
    t_f = (title + " " + (text or "")).lower()
    
    # 1. KATEGORYZACJA
    cat = None
    if any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds", "n2ds"]): cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl", "ds "]): cat = "DS_OLD"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed", "box"]): cat = "POKE"
    
    if not cat: return False, None

    # 2. PROGI CENOWE (Zatwierdzone przez Ciebie)
    limits = {"GB": 300, "PSP": 250, "3DS": 450, "DS_OLD": 200, "POKE": 160}
    min_prices = {"GB": 80, "PSP": 70, "3DS": 180, "DS_OLD": 70, "POKE": 15}
    
    if price > limits.get(cat, 999) or price < min_prices.get(cat, 0):
        return False, None

    # 3. LOGIKA SPRZĘTOWA (Hardware Keywords)
    hw_keywords = [
        "konsola", "zestaw", "sprawna", "gameboy", "game boy", "gba", "psp", "3ds", "2ds", "dsi",
        "1004", "2004", "3004", "street", "e1004", "go", "xl", "lite",
        "booster", "box", "sealed", "tali", "deck"
    ]
    is_hardware = any(hw in t_f for hw in hw_keywords)

    # 4. CZARNE LISTY
    hard_forbidden = ["r36s", "g28", "arkos", "emulator", "klon", "data frog", "repro", "3d printed", "drukarka 3d", "wydruk 3d"]
    if any(f in t_f for f in hard_forbidden): return False, None

    soft_forbidden = ["adapter", "obudowa", "shell", "zamiennik", "części", "naprawa", "wyświetlacz", "lcd", "bateria", "ładowarka", "etui", "case"]

    if not is_hardware:
        if any(s in t_f for s in soft_forbidden): return False, None
        if cat != "POKE": return False, None

    return True, cat

# --- COMMUNICATION ---
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except:
        pass

def process_item(title, url, price, text, src):
    full_url = url if "http" in url else f"https://www.vinted.pl{url}"
    clean_url = full_url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    
    # Sprawdzenie czy już wysłano (po linku lub hashu tytuł+cena)
    if item_hash in sent_hashes or clean_url in sent_hashes: 
        return

    valid, cat = is_valid_strict(title, text, price)
    if not valid: 
        return

    msg = (
        f"🎯 *HIT {src}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{title[:70]}*\n"
        f"💰 Cena: `{price:.2f} zł`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [KUP TERAZ]({clean_url})"
    )
    
    send_telegram(msg)
    log_debug(f"WYSŁANO: {title} ({price} zł)")
    
    sent_hashes.add(item_hash)
    sent_hashes.add(clean_url)
    with open(SENT_FILE, "a") as f:
        f.write(f"{item_hash}\n{clean_url}\n")

# --- SCRAPERS ---
def get_random_headers():
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    return {"User-Agent": random.choice(agents)}

def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        r = requests.get(url, headers=get_random_headers(), timeout=15)
        
        if r.status_code != 200:
            if r.status_code == 403: log_debug(f"OLX: Blokada 403 (Captcha/IP) dla '{query}'")
            return

        data = r.json()
        offers = data.get('data', [])
        for o in offers:
            p_data = o.get('price', {}).get('value', {}) or o.get('price', {})
            p = p_data.get('amount')
            if p:
                process_item(o['title'], o['url'], float(p), o.get('description', ""), "OLX")
    except Exception as e:
        if "Expecting value" not in str(e):
            log_debug(f"OLX ERROR {query}: {e}")

def scrape_vinted(session, query):
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, headers=get_random_headers(), timeout=15)
        
        if r.status_code != 200:
            return

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
        
        for card in cards:
            link = card.find("a", href=True)
            txt = card.get_text(separator=" ")
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
            if link and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link.get("title", ""), link['href'], price, "", "VINTED")
    except Exception as e:
        log_debug(f"VINTED ERROR {query}: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER v16.2 STARTUJĘ...")
    
    if not os.path.exists(SENT_FILE): 
        open(SENT_FILE, 'w').close()
    
    sent_hashes = set(open(SENT_FILE).read().split())
    vinted_session = requests.Session()
    
    # Inicjalizacja sesji Vinted (pobranie ciastek)
    try:
        vinted_session.get("https://www.vinted.pl", headers=get_random_headers(), timeout=10)
    except:
        pass

    QUERIES = [
        "psp konsola", "3ds konsola", "dsi konsola", 
        "gameboy advance", "pokemon booster bundle", "pokemon slab"
    ]
    
    log_debug(f"Wczytano {len(sent_hashes)} śladów wysyłek. Rozpoczynam nasłuchiwanie...")

    while True:
        # Przetasowanie zapytań, żeby nie szły zawsze w tej samej kolejności
        current_queries = QUERIES.copy()
        random.shuffle(current_queries)

        for q in current_queries:
            scrape_olx(q)
            time.sleep(random.randint(10, 20)) # Odstęp między OLX a Vinted
            
            scrape_vinted(vinted_session, q)
            time.sleep(random.randint(30, 60)) # Większy odstęp między kolejnymi zapytaniami
        
        log_debug("Pętla skanowania zakończona. Odpoczynek 60-120s...")
        time.sleep(random.randint(60, 120))
