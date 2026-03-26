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
            prices = [x["p"] for x in history.get(cat, [])]
            return sum(prices) / len(prices) if prices else 0
    except: return 0

# --- VISION AI (DO ANALIZY USZKODZEŃ) ---
def analyze_visuals(title, img_url):
    if not img_url or not GEMINI_API_KEY: return True
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Produkt: {title}. Czy na zdjęciu {img_url} urządzenie wydaje się sprawne (świeci dioda/ekran) mimo opisu o uszkodzeniu? Odpowiedz tylko: OK lub REJECT."
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        res = r.json()
        ans = res['candidates'][0]['content']['parts'][0]['text'].upper()
        return "REJECT" not in ans
    except: return True

# --- FILTRY KATEGORII I LIMITÓW ---
def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc"]): return "GAMEBOY"
    if "psp" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds", "dsi"]): return "3DS_FAMILY"
    if "booster bundle" in t: return "POKEMON_BUNDLE"
    if any(x in t for x in ["illustration", "partner"]): return "POKEMON_ILLUST"
    if any(x in t for x in ["day 2026", "pokemon day"]): return "POKEMON_DAY"
    return "OTHER"

def is_valid(title, text, price):
    t_f = (title + " " + text).lower()
    if price > 500 or price < 15: return False
    
    cat = identify_category(title)
    limits = {
        "GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450,
        "POKEMON_BUNDLE": 150, "POKEMON_ILLUST": 150, "POKEMON_DAY": 80
    }
    if price > limits.get(cat, 500): return False
    
    banned = ["r36s", "anbernic", "powkiddy", "etui", "ładowarka", "case", "r4", "adapter", "zasilacz"]
    if any(b in t_f for b in banned): return False
    return True

# --- GŁÓWNY SILNIK SCRAPERA ---
def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(90,122)}.0.0.0"}
    items = []
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            data = r.json().get('data', [])
            for o in data:
                # FIX BŁĘDU 'price'
                price_val = o.get('price', {}).get('value', {}).get('amount')
                if price_val is None: continue
                
                img = o.get('photos', [{}])[0].get('link', '').replace('{width}', '600').replace('{height}', '450')
                items.append((o.get('title', 'Brak'), o.get('url'), float(price_val), o.get('description', ''), img))
        
        elif source == "VINTED":
            r = requests.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                link_tag = card.find("a", href=True)
                if not link_tag: continue
                
                title = link_tag.get("title") or link_tag.text.strip()
                url = link_tag['href'] if link_tag['href'].startswith("http") else "https://www.vinted.pl" + link_tag['href']
                
                p_search = re.findall(r"(\d+[,.]\d+) zł", card.get_text())
                if not p_search: continue
                price = float(p_search[0].replace(",", "."))
                
                img_tag = card.find("img")
                img = img_tag['src'] if img_tag else ""
                items.append((title, url, price, title, img))

        for title, link, price, text, img in items:
            clean_link = link.split("?")[0].rstrip("/")
            if clean_link in sent_links: continue
            
            if is_valid(title, text, price):
                # Vision AI dla ofert 'uszkodzonych' lub 'nietestowanych'
                if any(x in (title + text).lower() for x in ["uszkodz", "nietest", "nieznany", "brak ładowarki"]):
                    if not analyze_visuals(title, img): continue
                
                avg = get_avg_price(title)
                update_trends(title, price)
                
                total = price + (15 if source != "VINTED" else 18)
                trend_info = f" (📉 Śr: {avg:.0f}zł)" if avg > 0 else ""
                
                msg = (
                    f"🎯 *OKAZJA {source}*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 *{title[:75]}*\n\n"
                    f"💰 Cena: `{price:.2f} zł`\n"
                    f"🚚 Razem: ~`{total:.2f} zł`{trend_info}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 [KUP TERAZ]({clean_link})"
                )
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                             data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                sent_links.add(clean_link)
                with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")

    except Exception as e:
        print(f"⚠️ Błąd {source} przy '{query}': {e}")

# --- PĘTLA GŁÓWNA ---
if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    
    QUERIES = [
        "gameboy konsola", "psp zestaw", "nintendo 3ds", 
        "pokemon booster bundle", "pokemon first partner illustration", "pokemon day 2026"
    ]
    
    print(f"🚀 SNIPER V10.3 ACTIVE | {datetime.now().strftime('%H:%M:%S')}")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(15, 25)) # Anty-spam delay
        print(f"😴 Cykl zakończony. Sen 60s...")
        time.sleep(60)
