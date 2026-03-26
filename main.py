import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import json
from datetime import datetime

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"
SENT_FILE = "sent_links.txt"
HISTORY_FILE = "price_history.json"

# --- SYSTEM TRENDÓW ---
def update_trends(title, price):
    history = {}
    cat = identify_category(title)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f: history = json.load(f)
    if cat not in history: history[cat] = []
    history[cat].append({"p": price, "d": datetime.now().strftime("%Y-%m-%d")})
    history[cat] = history[cat][-50:]
    with open(HISTORY_FILE, "w") as f: json.dump(history, f)

def get_avg_price(title):
    cat = identify_category(title)
    if not os.path.exists(HISTORY_FILE): return 0
    with open(HISTORY_FILE, "r") as f:
        history = json.load(f)
        prices = [x["p"] for x in history.get(cat, [])]
        return sum(prices) / len(prices) if prices else 0

# --- VISION AI (LIMITOWANE) ---
def analyze_visuals(title, img_url):
    if not img_url or not GEMINI_API_KEY: return True
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Produkt: {title}. Czy na zdjęciu {img_url} urządzenie wydaje się sprawne (świeci dioda/ekran) mimo opisu 'uszkodzone'? Odpowiedz krótko: OK lub REJECT."
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        return "REJECT" not in r.json()['candidates'][0]['content']['parts'][0]['text'].upper()
    except: return True

# --- FILTRY ---
def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc"]): return "GAMEBOY"
    if "psp" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds"]): return "3DS_FAMILY"
    if "booster bundle" in t: return "POKEMON_BUNDLE"
    if "illustration" in t or "partner" in t: return "POKEMON_ILLUST"
    if "day 2026" in t: return "POKEMON_DAY"
    return "OTHER"

def is_valid(title, text, price):
    t_f = (title + " " + text).lower()
    if price > 500 or price < 15: return False
    
    # Sztywne limity
    cat = identify_category(title)
    limits = {
        "GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450,
        "POKEMON_BUNDLE": 150, "POKEMON_ILLUST": 150, "POKEMON_DAY": 80
    }
    if price > limits.get(cat, 500): return False
    
    # Blokada śmieci
    if any(b in t_f for b in ["r36s", "anbernic", "powkiddy", "etui", "ładowarka", "case", "r4"]): return False
    return True

# --- SCRAPER SILNIK ---
def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(90,120)}.0.0.0"}
    items = []
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            for o in r.json().get('data', []):
                img = o.get('photos', [{}])[0].get('link', '').replace('{width}', '600').replace('{height}', '450')
                items.append((o['title'], o['url'], float(o['price']['value']['amount']), o['description'], img))
        
        elif source == "VINTED":
            # Poprawiony selektor Vinted
            r = requests.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                link_tag = card.find("a", href=True)
                if not link_tag: continue
                
                title = link_tag.get("title") or "Brak tytułu"
                url = link_tag['href'] if "vinted.pl" in link_tag['href'] else "https://www.vinted.pl" + link_tag['href']
                
                price_search = re.findall(r"(\d+[,.]\d+) zł", card.get_text())
                if not price_search: continue
                price = float(price_search[0].replace(",", "."))
                
                img_tag = card.find("img")
                img = img_tag['src'] if img_tag else ""
                items.append((title, url, price, title, img))

        for title, link, price, text, img in items:
            clean_link = link.split("?")[0].rstrip("/")
            if clean_link in sent_links: continue
            
            if is_valid(title, text, price):
                # Jeśli podejrzane 'uszkodzenie', użyj Gemini Vision
                if any(x in (title+text).lower() for x in ["uszkodz", "nietest", "brak ładowarki"]):
                    if not analyze_visuals(title, img): continue
                
                avg = get_avg_price(title)
                update_trends(title, price)
                
                # Telegram
                total = price + (15 if source != "VINTED" else 18)
                diff = f" (Taniej o {avg-price:.0f}zł od śr.)" if avg > price else ""
                
                msg = (
                    f"🎯 *OKAZJA {source}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 *{title[:75]}*\n\n"
                    f"💰 Cena: `{price:.2f} zł`\n"
                    f"🚚 Razem: ~`{total:.2f} zł`{diff}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 [KUP TERAZ]({clean_link})"
                )
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                sent_links.add(clean_link)
                with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")

    except Exception as e: print(f"⚠️ Błąd {source}: {e}")

# --- MAIN ---
if __name__ == "__main__":
    sent_links = set(open(SENT_FILE).read().split()) if os.path.exists(SENT_FILE) else set()
    QUERIES = ["gameboy", "psp zestaw", "3ds", "pokemon booster bundle", "first partner illustration", "pokemon day 2026"]
    
    print("🚀 SNIPER V10.2 | VINTED LINKS FIXED | VISION ACTIVE")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(12, 25))
        time.sleep(60)
