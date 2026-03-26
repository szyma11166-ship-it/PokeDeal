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

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

SENT_FILE = "sent_links.txt"
AI_CACHE_FILE = "ai_cache.json"

# =========================
# LOGIKA FILTROWANIA
# =========================
def is_valid(title, text, price):
    t_f = (title + " " + text).lower()
    
    # 1. Bezwzględny limit górny dla wszystkiego
    if price > 500 or price < 15: return False

    # 2. Blokada śmieci i klonów
    banned = ["r36s", "anbernic", "powkiddy", "etui", "case", "ładowarka", "uszkodz", "r4", "kabel", "zasilacz", "adapter"]
    if any(b in t_f for b in banned): return False

    # 3. SZTYWNE RAMY CENOWE (Priorytety)
    # --- Konsole ---
    if any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc"]):
        if price > 300: return False
    elif "psp" in t_f:
        if price > 250: return False
    elif any(x in t_f for x in ["3ds", "2ds", "dsi"]):
        if price > 450: return False
        
    # --- Pokemon TCG ---
    elif "booster bundle" in t_f:
        if price > 150: return False
    elif any(x in t_f for x in ["illustration collection", "first partner"]):
        if price > 150: return False
    elif any(x in t_f for x in ["pokemon day", "day 2026"]):
        if price > 80: return False
    elif "booster" in t_f and "bundle" not in t_f:
        if price > 35: return False

    # 4. ELASTYCZNY LIMIT (Jeśli powyższe nie złapały, a pasuje do słów kluczowych)
    # Tutaj wchodzą np. zestawy gier lub nietypowe akcesoria kolekcjonerskie
    return True

def calculate_total(price, source):
    if source == "VINTED": return price + (price * 0.05) + 2.90 + 13.0
    if source == "ALLEGRO": return price + 15.0
    return price

# =========================
# AI & TELEGRAM
# =========================
def ai_review(title, text, price):
    if not GEMINI_API_KEY: return True, "No Key"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"Czy to okazja? Tytuł: {title}. Opis: {text[:150]}. Cena: {price}zł. Odpowiedz krótko: ACCEPT/REJECT."
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=8)
        return "ACCEPT" in r.json()['candidates'][0]['content']['parts'][0]['text'].upper(), "AI"
    except: return True, "AI Error"

def send_telegram(title, price, link, source):
    clean_link = link.split("?")[0].rstrip("/")
    total = calculate_total(price, source)
    emoji = {"OLX": "🟢", "VINTED": "🟣", "ALLEGRO": "🟠"}.get(source, "📍")
    
    msg = (
        f"{emoji} *OKAZJA {source}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{title[:75]}*\n\n"
        f"💰 Cena: `{price:.2f} zł`\n"
        f"🚚 Razem: ~`{total:.2f} zł`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 [KLIKNIJ ABY KUPIĆ]({clean_link})"
    )
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

# =========================
# ENGINES
# =========================
def process_items(items, query, source, parse_func):
    for item in items[:15]:
        try:
            title, link, price, text = parse_func(item)
            if not link or not price or not is_valid(title, text, price): continue
            
            clean_link = link.split("?")[0].rstrip("/")
            if clean_link in sent_links: continue

            # AI dla niepewnych ofert
            if not any(x in title.lower() for x in ["konsola", "zestaw", "bundle", "collection"]):
                acc, _ = ai_review(title, text, price)
                if not acc: continue

            send_telegram(title, price, link, source)
            sent_links.add(clean_link)
            with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")
        except: continue

def olx_search(q):
    try:
        r = SESSION.get(f"https://www.olx.pl/api/v1/offers/?query={q}&sort_by=created_at:desc", timeout=10)
        process_items(r.json()['data'], q, "OLX", lambda o: (o['title'], o['url'], float(o['price']['value']['amount']), o['description']))
    except: pass

def vinted_search(q):
    try:
        r = SESSION.get(f"https://www.vinted.pl/catalog?search_text={q}&order=newest_first", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".feed-grid__item")
        def parse_v(i):
            a = i.find("a", href=True)
            p = re.findall(r"(\d+[,.]\d+) zł", i.get_text())
            return a.get("title"), "https://www.vinted.pl" + a['href'], float(p[0].replace(",", ".")) if p else None, i.get_text()
        process_items(items, q, "VINTED", parse_v)
    except: pass

def allegro_search(q):
    try:
        r = SESSION.get(f"https://allegrolokalnie.pl/oferty/q/{q}?order=newest", timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article")
        def parse_a(i):
            a = i.find("a", href=True)
            p = re.findall(r"(\d+[,.]\d+) zł", i.get_text())
            return i.find("h3").text, "https://allegrolokalnie.pl" + a['href'], float(p[0].replace(",", ".")) if p else None, i.get_text()
        process_items(items, q, "ALLEGRO", parse_a)
    except: pass

# =========================
# MAIN LOOP
# =========================
if __name__ == "__main__":
    sent_links = set(open(SENT_FILE).read().split()) if os.path.exists(SENT_FILE) else set()
    QUERIES = ["gameboy konsola", "psp zestaw", "nintendo 3ds", "pokemon booster bundle", "pokemon first partner illustration", "pokemon day 2026"]
    
    print("🚀 SNIPER V9.8 ONLINE | LIMIT 500 PLN")
    while True:
        for query in QUERIES:
            olx_search(query)
            vinted_search(query)
            allegro_search(query)
            time.sleep(random.randint(5, 10))
        time.sleep(60)
