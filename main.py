import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import base64
import json

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

SENT_FILE = "sent_links.txt"
AI_CACHE_FILE = "ai_cache.json"
ai_pending_queue = []

# =========================
# STORAGE & HELPERS
# =========================
def load_sent_links():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
    with open(SENT_FILE, "a") as f: f.write(link + "\n")

def load_ai_cache():
    if not os.path.exists(AI_CACHE_FILE): return {}
    try:
        with open(AI_CACHE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_ai_cache(cache):
    try:
        with open(AI_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"⚠️ Błąd cache AI: {e}")

sent_links = load_sent_links()
ai_cache = load_ai_cache()

def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()

def get_price(text):
    text = text.lower()
    text = re.sub(r"\d+\s*gb", "", text)
    matches = re.findall(r"(\d{1,5}(?:[.,]\d{1,2})?)\s*zł", text)
    if not matches: return None
    try:
        prices = [float(m.replace(",", ".")) for m in matches if float(m.replace(",", ".")) >= 5]
        return min(prices) if prices else None
    except: return None

# =========================
# FILTERS
# =========================
def is_valid(title, full_text):
    t, f = clean(title), clean(full_text)
    banned = ["pudełko", "box only", "samo opakowanie", "etui", "ładowarka", "kabel", "uszkodz", "części", "niedziała"]
    if any(b in t for b in banned): return False
    if any(b in f for b in ["uszkodzone", "na części", "replacement", "zamiennik"]): return False
    return True

def console_filter(query, title, price, text):
    t = clean(title)
    q = query.lower()
    if "psp" in q: return ("psp" in t) and price <= 250
    if "3ds" in q: return ("3ds" in t or "2ds" in t or "dsi" in t) and price <= 450
    if "gameboy" in q: return ("gameboy" in t or "gba" in t or "gbc" in t) and price <= 350
    return False

def pokemon_filter(title, price):
    t = clean(title)
    if "pokemon" not in t and "pokémon" not in t: return False
    if any(x in t for x in ["booster", "etb", "blister", "bundle"]): return price <= 300
    return False

def is_uncertain(title, query):
    t = clean(title)
    if "pokemon" in query: return not any(x in t for x in ["booster", "etb", "blister"])
    return not any(x in t for x in ["1000", "2000", "3000", "lite", "xl"])

# =========================
# AI REVIEW
# =========================
def ai_review(title, full_text, price, img_url=None):
    if not GEMINI_API_KEY: return False, "Brak klucza"
    ckey = f"{clean(title)}|{int(price/20)*20}"
    if ckey in ai_cache: return ai_cache[ckey]["accept"], ai_cache[ckey]["reason"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Zidentyfikuj ofertę: '{title}'. Cena: {price}zł. Czy to konsola/zestaw TCG? Odpowiedz tylko: DECISION: ACCEPT/REJECT, REASON: (powód)."
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        if r.status_code == 429: return None, "Rate limit"
        res = r.json()
        ans = res['candidates'][0]['content']['parts'][0]['text']
        accept = "ACCEPT" in ans.upper()
        ai_cache[ckey] = {"accept": accept, "reason": ans[:50]}
        save_ai_cache(ai_cache)
        return accept, ans[:50]
    except: return None, "Błąd API"

# =========================
# CORE PROCESSING
# =========================
def send_telegram(title, price, link, source):
    clean_link = link.split("?")[0].rstrip("/")
    if clean_link in sent_links: return
    
    emoji = {"OLX": "🟢", "VINTED": "🟣", "ALLEGRO": "🟠"}.get(source, "📍")
    msg = f"🔥 *NOWA OKAZJA*\n{'-'*20}\n📦 {title[:80]}\n💰 *{price} zł*\n{emoji} {source}\n🔗 {clean_link}"
    
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        sent_links.add(clean_link)
        save_sent_link(clean_link)
    except Exception as e: print(f"❌ Telegram Error: {e}")

def process_items(items, query, source, get_data_func):
    for item in items[:15]:
        try:
            title, link, price, text, img = get_data_func(item)
            if not link or not price: continue
            
            if not is_valid(title, text): continue
            
            pass_filt = pokemon_filter(title, price) if query == "pokemon" else console_filter(query, title, price, text)
            if not pass_filt: continue

            if is_uncertain(title, query):
                acc, rea = ai_review(title, text, price, img)
                if acc is None:
                    ai_pending_queue.append({"title": title, "price": price, "link": link, "source": source, "text": text})
                    continue
                if not acc: continue
            
            send_telegram(title, price, link, source)
        except: continue

# =========================
# SCRAPERS
# =========================
def olx_search(query):
    print(f"🟢 OLX: {query}")
    try:
        r = SESSION.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", timeout=10)
        data = r.json().get('data', [])
        def parse(o):
            return o['title'], o['url'], float(o['price']['value']['amount']), o['title'], None
        process_items(data, query, "OLX", parse)
    except: print("❌ OLX Error")

def vinted_search(query):
    print(f"🟣 VINTED: {query}")
    try:
        r = SESSION.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.feed-grid__item")
        def parse(i):
            a = i.select_one("a")
            t = a.get('title', '') if a else ''
            l = "https://www.vinted.pl" + a['href'] if a else ''
            p = get_price(i.get_text())
            return t, l, p, i.get_text(), None
        process_items(items, query, "VINTED", parse)
    except: print("❌ VINTED Error")

def allegro_search(query):
    print(f"🟠 ALLEGRO: {query}")
    try:
        r = SESSION.get(f"https://allegrolokalnie.pl/oferty/q/{query}?order=newest", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article")
        def parse(i):
            t = i.select_one("h3").get_text() if i.select_one("h3") else ""
            l = "https://allegrolokalnie.pl" + i.select_one("a")['href']
            p = get_price(i.get_text())
            return t, l, p, i.get_text(), None
        process_items(items, query, "ALLEGRO", parse)
    except: print("❌ Allegro Error")

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    QUERIES = ["konsola psp", "nintendo 3ds", "gameboy", "pokemon"]
    while True:
        for q in QUERIES:
            olx_search(q)
            vinted_search(q)
            allegro_search(q)
            time.sleep(5)
        print("⏳ Cykl zakończony. Sen 60s.")
        time.sleep(60)
