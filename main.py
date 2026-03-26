import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import json

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

SENT_FILE = "sent_links.txt"
AI_CACHE_FILE = "ai_cache.json"

# =========================
# HELPERS & STORAGE
# =========================
def load_sent_links():
    if not os.path.exists(SENT_FILE): return set()
    with open(SENT_FILE, "r") as f: return set(line.strip() for line in f if line.strip())

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
    except: pass

sent_links = load_sent_links()
ai_cache = load_ai_cache()

def clean(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()

def get_price(text):
    matches = re.findall(r"(\d{1,5}(?:[.,]\d{1,2})?)\s*zł", text.lower())
    if not matches: return None
    try:
        prices = [float(m.replace(",", ".")) for m in matches if float(m.replace(",", ".")) >= 5]
        return min(prices) if prices else None
    except: return None

# =========================
# LOGIKA FILTROWANIA
# =========================
def is_bundle(title, text):
    t_f = clean(title + " " + text)
    bundle_words = ["zestaw", "pakiet", "lot", "kolekcja", "ilość", "sztuk", "gier", "bundle"]
    return any(w in t_f for w in bundle_words)

def is_valid(title, text):
    t_f = clean(title + " " + text)
    # Blokada śmieci i nagrywarek R4
    banned = ["pudełko", "box only", "etui", "ładowarka", "kabel", "uszkodz", "części", 
              "r4", "r4i", "gold pro", "dual core", "dstwo", "acekard", "programator"]
    if any(b in t_f for b in banned): return False
    
    # Rozróżnienie: Konsola vs Pojedyncza Gra
    is_console = any(c in t_f for c in ["konsola", "system", "nintendo", "sony", "psp", "3ds", "2ds", "gba"])
    if not is_console and not is_bundle(title, text):
        return False # Odrzuć jeśli to ani konsola, ani zestaw gier
        
    return True

def calculate_total(price, source):
    """Oblicza przybliżony koszt z wysyłką i prowizją."""
    if source == "VINTED":
        # Ochrona (2.90 + 5%) + Wysyłka (~10-14 zł)
        protection = 2.90 + (price * 0.05)
        return price + protection + 12.0
    if source == "ALLEGRO":
        # Allegro Lokalnie: Ochrona jest w cenie, dodajemy tylko wysyłkę (InPost ~15 zł)
        return price + 15.0
    return price # OLX zazwyczaj do negocjacji / odbiór

# =========================
# AI ENGINE
# =========================
def ai_review(title, text, price):
    if not GEMINI_API_KEY: return False, "No Key"
    ckey = f"{clean(title)}|{int(price/10)*10}"
    if ckey in ai_cache: return ai_cache[ckey]["accept"], ai_cache[ckey]["reason"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Analiza oferty: '{title}'. Opis: {text[:200]}. Czy to konsola lub ZESTAW gier? (Odrzuć pojedyncze gry). Odpowiedz: ACCEPT/REJECT + krótki powód."
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10)
        res = r.json()
        ans = res['candidates'][0]['content']['parts'][0]['text'].upper()
        accept = "ACCEPT" in ans
        ai_cache[ckey] = {"accept": accept, "reason": ans[:50]}
        save_ai_cache(ai_cache)
        return accept, ans[:50]
    except: return True, "AI Error - Passing"

# =========================
# TELEGRAM & CORE
# =========================
def send_telegram(title, price, link, source):
    clean_link = link.split("?")[0].rstrip("/")
    if clean_link in sent_links: return
    
    total = calculate_total(price, source)
    emoji = {"OLX": "🟢", "VINTED": "🟣", "ALLEGRO": "🟠"}.get(source, "📍")
    
    msg = (
        f"{emoji} *NOWA OKAZJA {source}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{title[:70]}*\n\n"
        f"💰 Cena: `{price:.2f} zł`\n"
        f"🚚 Łącznie: ~`{total:.2f} zł` (z opłatami)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [OTWÓRZ OFERTĘ]({clean_link})"
    )
    
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": False})
        sent_links.add(clean_link)
        save_sent_link(clean_link)
        print(f"✅ Wysłano: {title[:40]}")
    except Exception as e: print(f"❌ Telegram Error: {e}")

def process_items(items, query, source, parse_func):
    for item in items[:15]:
        try:
            title, link, price, text = parse_func(item)
            if not all([title, link, price]): continue
            
            if not is_valid(title, text): continue
            
            # Decyzja AI tylko dla niepewnych tytułów
            is_sure = any(x in clean(title) for x in ["konsola", "zestaw", "komplet"])
            if not is_sure:
                acc, reason = ai_review(title, text, price)
                if not acc: 
                    print(f"🤖 AI Odrzuciło ({reason}): {title[:30]}")
                    continue

            send_telegram(title, price, link, source)
        except: continue

# =========================
# SCRAPERS
# =========================
def olx_search(query):
    print(f"🔎 OLX: {query}")
    try:
        r = SESSION.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", timeout=10)
        data = r.json().get('data', [])
        process_items(data, query, "OLX", lambda o: (o['title'], o['url'], float(o['price']['value']['amount']), o['description']))
    except: pass

def vinted_search(query):
    print(f"🔎 VINTED: {query}")
    try:
        r = SESSION.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("div.feed-grid__item")
        def parse_v(i):
            a = i.select_one("a")
            return a['title'], "https://www.vinted.pl" + a['href'], get_price(i.get_text()), i.get_text()
        process_items(items, query, "VINTED", parse_v)
    except: pass

def allegro_search(query):
    print(f"🔎 ALLEGRO: {query}")
    try:
        r = SESSION.get(f"https://allegrolokalnie.pl/oferty/q/{query}?order=newest", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article")
        def parse_a(i):
            a = i.select_one("a")
            t = i.select_one("h3").get_text() if i.select_one("h3") else ""
            return t, "https://allegrolokalnie.pl" + a['href'], get_price(i.get_text()), i.get_text()
        process_items(items, query, "ALLEGRO", parse_a)
    except: pass

# =========================
# MAIN LOOP
# =========================
if __name__ == "__main__":
    print("🚀 SNIPER V9.5 ACTIVE")
    # Zapytania zoptymalizowane pod konsole i zestawy
    QUERIES = ["psp konsola zestaw", "nintendo 3ds zestaw", "gameboy zestaw gier", "nintendo 2ds", "nintendo ds pakiet"]
    
    while True:
        for q in QUERIES:
            olx_search(q)
            vinted_search(q)
            allegro_search(q)
            time.sleep(random.uniform(3, 7))
        print(f"😴 Cykl zakończony. {time.strftime('%H:%M:%S')}")
        time.sleep(60)
