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

def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): return "GAMEBOY"
    if "psp" in t or "playstation portable" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds", "dsi"]): return "3DS_FAMILY"
    if any(x in t for x in ["pokemon", "booster", "bundle", "illustration", "day 2026", "psa", "slab"]): return "POKEMON"
    return None

def is_valid(title, text, price):
    if not price or price <= 5 or price > 500: return False
    t_f = (title + " " + text).lower()
    cat = identify_category(title)
    if not cat: return False

    # 1. ROZSZERZONA CZARNA LISTA (Nuclear Clean V11.1)
    trash = [
        "switch", "wii", "pegasus", "szkło", "etui", "case", "pokrowiec", "uchwyt", 
        "r36s", "anbernic", "powkiddy", "pudełko", "instrukcja", "manual", "broszura", 
        "ulotka", "plecak", "torba", "torebka", "alba", "sukienka", "ładowarka", 
        "zasilacz", "kabel", "części", "na części", "sup", "pouzdro", "ritka", 
        "coin", "moneta", "sticker", "naklejka", "żeton"
    ]
    if any(b in t_f for b in trash): return False

    # 2. FILTR POKEMON (Tylko Sealed & Slabs)
    if cat == "POKEMON":
        pkmn_trash = ["karta", "karty", "single", "zestaw", "lot", "bulk", "klaser", "folder", "kod", "online", "stan", "near mint", "mint"]
        if any(p in t_f for p in pkmn_trash): return False
        
        pkmn_white = ["booster", "bundle", "display", "tin", "box", "sealed", "zamknięte", "psa", "bgs", "pgc", "graad", "slab", "illustration"]
        if not any(w in t_f for w in pkmn_white): return False
    
    # 3. FILTR KONSOL (Próg dolny dla sprzętu)
    else:
        if price < 60 and "zestaw" not in t_f: return False

    # 4. LIMITY CENOWE
    limits = {"GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450, "POKEMON": 150}
    return price <= limits.get(cat, 0)

def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(115,127)}.0.0.0"}
    items = []
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            for o in r.json().get('data', []):
                p = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if p: items.append((o.get('title'), o.get('url'), float(p), o.get('description', "")))
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
            if clean_link in sent_links or not is_valid(title, text, price): continue
            
            msg = f"🎯 *OKAZJA {source}*\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_link})"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            sent_links.add(clean_link)
            with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")
    except Exception as e: print(f"⚠️ Błąd {source}: {e}")

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    QUERIES = ["gameboy konsola", "psp konsola", "nintendo 3ds", "pokemon booster bundle", "pokemon illustration", "pokemon day 2026", "pokemon psa slab"]
    
    print(f"🚀 SNIPER V11.1 | CZYSZCZENIE: SUP, POUZDRO, COINS")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(20, 40))
        time.sleep(60)
