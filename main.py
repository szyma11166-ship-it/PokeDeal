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
    except Exception as e: print(f"⚠️ Cache error: {e}")

sent_links = load_sent_links()
ai_cache = load_ai_cache()

def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()

def get_price(text):
    text = text.lower()
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
    banned = ["pudełko", "box only", "samo opakowanie", "etui", "ładowarka", "kabel", "uszkodz", "części"]
    if any(b in t for b in banned): return False
    if "uszkodz" in f or "nie działa" in f: return False
    return True

def console_filter(query, title, price, text):
    t = clean(title)
    if "psp" in query and "psp" in t: return price <= 250
    if "3ds" in query and ("3ds" in t or "2ds" in t): return price <= 450
    if "gameboy" in query and ("gameboy" in t or "gba" in t): return price <= 350
    return False

def pokemon_filter(title, price):
    t = clean(title)
    if "pokemon" not in t: return False
    if any(x in t for x in ["booster", "etb", "tincase"]): return price <= 250
    return False

def is_uncertain(title, query):
    # Prosta logika: jeśli tytuł jest bardzo krótki, pytaj AI
    return len(title.split()) < 4

# =========================
# AI & NETWORK
# =========================
def ai_review(title, full_text, price, img_url=None):
    if not GEMINI_API_KEY: return False, "No API Key"
    
    # Check Cache
    cache_key = f"{clean(title)}|{int(price/20)}"
    if cache_key in ai_cache: return ai_cache[cache_key]["accept"], ai_cache[cache_key]["reason"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Czy to jest konsola (nie gra/akcesorium)? Tytuł: {title}, Cena: {price}. Odpowiedz: ACCEPT lub REJECT + powód."
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 429: return None, "Rate limit"
        res = r.json()
        text = res['candidates'][0]['content']['parts'][0]['text'].upper()
        accept = "ACCEPT" in text
        ai_cache[cache_key] = {"accept": accept, "reason": text[:30]}
        save_ai_cache(ai_cache)
        return accept, text[:30]
    except:
        return None, "Error"

def send_telegram(title, price, link, source):
    clean_link = link.split("?")[0]
    if clean_link in sent_links: return
    
    msg = f"🔥 *OKAZJA {source}*\n📦 {title}\n💰 *{price} zł*\n🔗 {clean_link}"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                  data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    
    sent_links.add(clean_link)
    save_sent_link(clean_link)

# =========================
# SCRAPERS
# =========================
def olx_search(query):
    print(f"🟢 OLX: {query}")
    api_url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&limit=20"
    try:
        r = SESSION.get(api_url, timeout=10)
        data = r.json().get('data', [])
        for offer in data:
            title = offer.get('title')
            price = offer.get('price', {}).get('value', {}).get('amount')
            link = offer.get('url')
            if not all([title, price, link]): continue
            
            if is_valid(title, title) and console_filter(query, title, float(price), ""):
                send_telegram(title, price, link, "OLX")
    except Exception as e: print(f"❌ OLX Error: {e}")

# =========================
# MAIN LOOP
# =========================
if __name__ == "__main__":
    print("🚀 SNIPER START")
    QUERIES = ["psp konsola", "nintendo 3ds", "gameboy color"]
    
    while True:
        for q in QUERIES:
            olx_search(q)
            time.sleep(random.uniform(5, 10))
        
        print("⏳ Czekam 60s...")
        time.sleep(60)
