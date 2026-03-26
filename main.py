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

# --- LOGIKA KATEGORII I TRENDÓW ---
def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc"]): return "GAMEBOY"
    if "psp" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds", "dsi"]): return "3DS_FAMILY"
    if "booster bundle" in t: return "POKEMON_BUNDLE"
    if any(x in t for x in ["illustration", "partner"]): return "POKEMON_ILLUST"
    if any(x in t for x in ["day 2026", "pokemon day"]): return "POKEMON_DAY"
    return "OTHER"

def update_trends(title, price):
    if not price: return
    cat = identify_category(title)
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f: history = json.load(f)
        except: history = {}
    if cat not in history: history[cat] = []
    history[cat].append({"p": price, "d": datetime.now().strftime("%Y-%m-%d")})
    history[cat] = history[cat][-50:]
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

# --- FILTRY I VISION AI ---
def is_valid(title, text, price):
    t_f = (title + " " + text).lower()
    if price and price > 500: return False # Hard cap
    if any(b in t_f for b in ["r36s", "anbernic", "powkiddy", "etui", "r4", "ładowarka"]): return False
    
    cat = identify_category(title)
    limits = {"GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450, "POKEMON_BUNDLE": 150, "POKEMON_ILLUST": 150, "POKEMON_DAY": 80}
    
    # Jeśli cena jest wykryta, sprawdź limit. Jeśli brak ceny (0/None), przepuść do sprawdzenia ręcznego.
    if price and price > 0:
        return price <= limits.get(cat, 500)
    return True 

def analyze_visuals(title, img_url):
    if not img_url or not GEMINI_API_KEY: return True
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Produkt: {title}. Czy urządzenie na foto {img_url} wydaje się sprawne/kompletne? Odpowiedz: OK lub REJECT."
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        return "REJECT" not in r.json()['candidates'][0]['content']['parts'][0]['text'].upper()
    except: return True

# --- SCRAPER ---
def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,126)}.0.0.0"}
    items = []
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            for o in r.json().get('data', []):
                p_raw = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                price = float(p_raw) if p_raw else 0.0
                img = o.get('photos', [{}])[0].get('link', '').replace('{width}', '600')
                items.append((o.get('title'), o.get('url'), price, o.get('description', ''), img))
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=5)
            r = s.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                txt = card.get_text(separator=" ").replace('\xa0', ' ')
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                price = float(p_match.group(1).replace(",", ".").replace(" ", "")) if p_match else 0.0
                link_tag = card.find("a", href=True)
                if link_tag:
                    url = link_tag['href'] if "http" in link_tag['href'] else "https://www.vinted.pl" + link_tag['href']
                    img = card.find("img")['src'] if card.find("img") else ""
                    items.append((link_tag.get("title", "Okazja"), url, price, "Vinted Item", img))

        for title, link, price, text, img in items:
            clean_link = link.split("?")[0].rstrip("/")
            if clean_link in sent_links or not is_valid(title, text, price): continue
            
            # Vision AI dla podejrzanych opisów
            if any(x in (title + text).lower() for x in ["uszkodz", "nietest", "brak"]) and price > 0:
                if not analyze_visuals(title, img): continue

            avg = get_avg_price(title)
            update_trends(title, price)
            
            p_display = f"{price:.2f} zł" if price > 0 else "DO NEGOCJACJI / SPRAWDŹ"
            total = f"~{price + 18:.2f} zł" if price > 0 else "Zależne od ceny"
            trend_info = f"\n📉 Śr. rynkowa: {avg:.0f} zł" if avg > 0 else ""

            msg = (
                f"🎯 *OKAZJA {source}*\n━━━━━━━━━━━━━━━━━━━━\n"
                f"📦 *{title[:75]}*\n\n"
                f"💰 Cena: `{p_display}`\n"
                f"🚚 Razem: `{total}`{trend_info}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n🔗 [OTWÓRZ OFERTĘ]({clean_link})"
            )
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            sent_links.add(clean_link)
            with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")

    except Exception as e: print(f"⚠️ Błąd {source}: {e}")

# --- START ---
if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    QUERIES = ["gameboy konsola", "psp zestaw", "nintendo 3ds", "pokemon booster bundle", "pokemon first partner illustration", "pokemon day 2026"]
    
    print(f"🚀 SNIPER V10.5 ONLINE | {datetime.now().strftime('%H:%M:%S')}")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(15, 30))
        time.sleep(60)
