import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_FILE = "sent_links.txt"

def is_valid_strict(title, text, price):
    t_f = (title + " " + text).lower()
    
    # 1. CZERWONA LISTA (Absolutny zakaz - jeśli tu jest, kończymy)
    forbidden = [
        "r4", "r4i", "gold pro", "dual core", "adapter", "micro sd", "karta pamięci",
        "cover", "skin", "naklejka", "sticker", "obudowa", "shell", "housing", "faceplate",
        "zamiennik", "części", "na części", "naprawa", "serwis", "wyświetlacz", "lcd", "ekran",
        "bateria", "battery", "ładowarka", "zasilacz", "kabel", "etui", "pokrowiec", "case",
        "pudełko", "box", "instrukcja", "manual", "ulotka", "broszura", "płyta", "sama gra",
        "sup", "retro f7", "g28", "m17", "r36s", "anbernic", "powkiddy", "miyoo", "alba"
    ]
    if any(f in t_f for f in forbidden): return False

    # 2. IDENTYFIKACJA I LIMITY
    cat = None
    if any(x in t_f for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f or "playstation portable" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "dsi"]): cat = "3DS"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab"]): cat = "POKE"
    
    if not cat: return False

    # 3. FILTR "ANTY-SINGIEL" (Gry i akcesoria udające okazje)
    if cat == "3DS":
        if price < 150 and "zestaw" not in t_f: return False # 3DS < 150zł bez "zestaw" to gra/śmieć
        limit = 450
    elif cat == "PSP":
        if price < 75 and "zestaw" not in t_f: return False # PSP < 75zł bez "zestaw" to gra/bateria
        limit = 250
    elif cat == "GB":
        if price < 100 and "zestaw" not in t_f: return False
        limit = 300
    else: # POKE
        limit = 160

    return 10 < price <= limit

def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(115,128)}.0.0.0"}
    try:
        if source == "OLX":
            url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
            data = requests.get(url, headers=headers, timeout=10).json().get('data', [])
            for o in data:
                p = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if p: process_item(o['title'], o['url'], float(p), o.get('description', ""), source)
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=5)
            url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
            soup = BeautifulSoup(s.get(url, headers=headers).text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                link_tag = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", card.get_text(separator=" "))
                if link_tag and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(link_tag.get("title", ""), link_tag['href'], price, "", source)
    except Exception as e: print(f"Błąd {source}: {e}")

def process_item(title, url, price, text, src):
    full_url = url if "http" in url else f"https://www.vinted.pl{url}"
    clean_url = full_url.split("?")[0].rstrip("/")
    if clean_url in sent_links: return
    
    if is_valid_strict(title, text, price):
        msg = f"🎯 *HIT {src}*\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        sent_links.add(clean_url)
        with open(SENT_FILE, "a") as f: f.write(clean_url + "\n")

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    # Zapytania bez zbędnych słów, by nie "podpowiadać" silnikowi błędnych wyników
    QUERIES = ["psp konsola", "3ds konsola", "gameboy advance", "pokemon booster bundle", "pokemon psa"]
    
    print("🚀 SNIPER V11.3 ONLINE | STRICT MODE")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(25, 45))
        time.sleep(60)
