import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import json
from datetime import datetime

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"
SENT_FILE = "sent_links.txt"
HISTORY_FILE = "price_history.json"

def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): return "GAMEBOY"
    if "psp" in t or "playstation portable" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds", "dsi"]): return "3DS_FAMILY"
    if "booster bundle" in t: return "POKEMON_BUNDLE"
    if any(x in t for x in ["illustration", "partner"]): return "POKEMON_ILLUST"
    if any(x in t for x in ["day 2026", "pokemon day"]): return "POKEMON_DAY"
    return None

def is_valid(title, text, price):
    if not price or price <= 5 or price > 500: return False
    
    t_f = (title + " " + text).lower()
    cat = identify_category(title)
    if not cat: return False

    # 1. ROZSZERZONA CZARNA LISTA (Broszury, Alby, Tekstylia, Akcesoria)
    trash = [
        "switch", "lite", "oled", "wii", "balance board", "fit", "move", "pegasus",
        "szkło", "glass", "folia", "etui", "case", "pokrowiec", "uchwyt", "grip",
        "r36s", "anbernic", "powkiddy", "miyoo", "sf2000", "pudełko", "box",
        "instrukcja", "manual", "broszura", "ulotka", "gazetka", "plakat",
        "plecak", "torba", "torebka", "backpack", "bag", "koszulka", "shirt",
        "alba", "sukienka", "komunijna", "dziewczynka", "strój",
        "ładowarka", "zasilacz", "kabel", "adapter", "części", "na części", "obudowa", "shell",
        "gra", "gry", "gra na", "sama gra", "cartridge", "dyskietka", "płyta"
    ]
    if any(b in t_f for b in trash): return False

    # 2. FILTR CENOWY "ANTY-GRY / ANTY-ŁADOWARKI"
    # Jeśli szukamy konsoli, a cena jest podejrzanie niska (np. 30zł), to prawdopodobnie sama gra/kabel
    if cat in ["GAMEBOY", "PSP", "3DS_FAMILY"] and price < 60: return False

    # 3. BIAŁA LISTA I SZTYWNE LIMITY
    whitelist = {
        "GAMEBOY": ["gameboy", "game boy", "gba", "gbc", "dmg", "advance", "sp"],
        "PSP": ["psp", "1004", "2004", "3004", "go", "e1004", "street", "konsola"],
        "3DS_FAMILY": ["3ds", "2ds", "new 3ds", "new 2ds", "xl", "ll", "konsola"],
        "POKEMON_BUNDLE": ["booster bundle", "bundle"],
        "POKEMON_ILLUST": ["illustration", "partner"],
        "POKEMON_DAY": ["day 2026", "pokemon day"]
    }
    
    if not any(w in t_f for w in whitelist.get(cat, [])): return False

    limits = {
        "GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450, 
        "POKEMON_BUNDLE": 150, "POKEMON_ILLUST": 150, "POKEMON_DAY": 80
    }
    
    return price <= limits.get(cat, 0)

# --- SYSTEM TRENDÓW ---
def update_trends(title, price):
    cat = identify_category(title)
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: history = json.load(f)
        except: history = {}
    if cat not in history: history[cat] = []
    history[cat].append({"p": price, "d": datetime.now().strftime("%Y-%m-%d")})
    history[cat] = history[cat][-30:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_avg_price(title):
    cat = identify_category(title)
    if not os.path.exists(HISTORY_FILE): return 0
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            prices = [x["p"] for x in history.get(cat, []) if x["p"] > 0]
            return sum(prices) / len(prices) if prices else 0
    except: return 0

# --- SCRAPER SILNIK ---
def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(115,127)}.0.0.0"}
    items = []
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            for o in r.json().get('data', []):
                p_raw = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if p_raw:
                    items.append((o.get('title'), o.get('url'), float(p_raw), o.get('description', "")))
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=5)
            r = s.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                txt = card.get_text(separator=" ").replace('\xa0', ' ')
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                link_tag = card.find("a", href=True)
                if p_match and link_tag:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    url = link_tag['href'] if "http" in link_tag['href'] else "https://www.vinted.pl" + link_tag['href']
                    items.append((link_tag.get("title") or "Okazja", url, price, ""))

        for title, link, price, text in items:
            clean_link = link.split("?")[0].rstrip("/")
            if clean_link in sent_links: continue
            
            if is_valid(title, text, price):
                avg = get_avg_price(title)
                update_trends(title, price)
                
                msg = (
                    f"🎯 *OKAZJA {source}*\n━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 *{title[:70]}*\n"
                    f"💰 Cena: `{price:.2f} zł` (Śr: {avg:.1f} zł)\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_link})"
                )
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                sent_links.add(clean_link)
                with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")

    except Exception as e:
        print(f"⚠️ Błąd {source}: {e}")

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    
    # Precyzyjne zapytania z wykluczeniami
    QUERIES = [
        "gameboy konsola -switch -wii -alba -torba -plecak",
        "psp konsola -etui -ładowarka -sukienka",
        "nintendo 3ds -switch -wii",
        "pokemon booster bundle",
        "pokemon illustration collection",
        "pokemon day 2026"
    ]
    
    print(f"🚀 SNIPER V10.8 ACTIVE | NUCLEAR CLEAN MODE")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(20, 40))
        time.sleep(60)
