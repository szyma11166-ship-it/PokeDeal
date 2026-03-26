import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
from datetime import datetime

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_FILE = "sent_links.txt"

def identify_category(title):
    t = title.lower()
    if any(x in t for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): return "GAMEBOY"
    if "psp" in t or "playstation portable" in t: return "PSP"
    if any(x in t for x in ["3ds", "2ds", "dsi"]): return "3DS_FAMILY"
    if any(x in t for x in ["pokemon", "booster", "bundle", "illustration", "day 2026", "psa", "slab"]): return "POKEMON"
    return None

def is_valid(title, text, price):
    # 1. HARD LIMITS & BASICS
    if not price or price <= 10 or price > 500: return False
    t_f = (title + " " + text).lower()
    cat = identify_category(title)
    if not cat: return False

    # 2. CZARNA LISTA TOTALNA (Części, akcesoria, podróby, śmieci)
    # Dodano: bateria, ekran, wyświetlacz, przyciski, gumki, szybka, sup, retro, shell
    trash = [
        "bateria", "battery", "ekran", "display", "wyświetlacz", "lcd", "szybka", "glass",
        "obudowa", "shell", "klapka", "przyciski", "buttons", "gumki", "joystick", "analog",
        "naprawa", "części", "na części", "serwis", "uszkodzony", "pęknięty", "stojak",
        "ładowarka", "zasilacz", "kabel", "usb", "adapter", "etui", "case", "pokrowiec",
        "szkło", "folia", "grip", "uchwyt", "pudełko", "box", "instrukcja", "manual",
        "broszura", "plakat", "naklejka", "sticker", "coin", "moneta", "ritka", "pouzdro",
        "sup", "g28", "m17", "r36s", "anbernic", "powkiddy", "miyoo", "data frog",
        "gra", "gry", "płyta", "cartridge", "dyskietka", "karta", "karty", "single",
        "alba", "sukienka", "plecak", "torba", "torebka", "ubrania", "buty"
    ]
    if any(b in t_f for b in trash): return False

    # 3. FILTRY SPECYFICZNE DLA KATEGORII
    if cat == "POKEMON":
        # Tylko szczelnie zamknięte lub gradowane
        pkmn_white = ["booster", "bundle", "display", "tin", "box", "sealed", "zamknięte", "psa", "bgs", "cgc", "slab"]
        if not any(w in t_f for w in pkmn_white): return False
        if any(bad in t_f for bad in ["zestaw", "lot", "bulk", "klaser", "album"]): return False
    
    else:
        # KONSOLA: Musi być słowo "konsola" lub konkretny model, a nie samo "PSP" (które często oznacza baterię)
        # Cena < 80 zł dla konsoli to prawie zawsze oszustwo lub bateria - odrzucamy.
        if price < 80 and "zestaw" not in t_f: return False
        
        # Wymuszamy, aby w tytule nie było słowa "gra", chyba że to "zestaw gier"
        if " gra " in t_f or " gry " in t_f:
            if "zestaw" not in t_f: return False

    # 4. LIMITY CENOWE (Twoje sztywne progi)
    limits = {"GAMEBOY": 300, "PSP": 250, "3DS_FAMILY": 450, "POKEMON": 160}
    return price <= limits.get(cat, 0)

def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,127)}.0.0.0"}
    try:
        if source == "OLX":
            r = requests.get(f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc", headers=headers, timeout=10)
            items = r.json().get('data', [])
            for o in items:
                title = o.get('title')
                url = o.get('url')
                p_raw = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if title and url and p_raw:
                    process_item(title, url, float(p_raw), o.get('description', ""), source)
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=5)
            r = s.get(f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                link_tag = card.find("a", href=True)
                if not link_tag: continue
                title = link_tag.get("title") or "Okazja"
                url = link_tag['href'] if "http" in link_tag['href'] else "https://www.vinted.pl" + link_tag['href']
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", card.get_text(separator=" "))
                if p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    process_item(title, url, price, "", source)
    except Exception as e: print(f"⚠️ Błąd {source}: {e}")

def process_item(title, url, price, text, source):
    clean_link = url.split("?")[0].rstrip("/")
    if clean_link in sent_links: return
    
    if is_valid(title, text, price):
        msg = f"🎯 *HIT {source}*\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_link})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        sent_links.add(clean_link)
        with open(SENT_FILE, "a") as f: f.write(clean_link + "\n")

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    # Bardzo precyzyjne zapytania
    QUERIES = ["psp konsola", "gameboy advance", "nintendo 3ds", "pokemon booster bundle", "pokemon illustration", "pokemon psa slab"]
    
    print(f"🚀 SNIPER V11.2 | ANT-TRASH ACTIVE")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(20, 35))
        time.sleep(60)
