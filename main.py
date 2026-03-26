import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_FILE = "sent_links.txt"
LOG_FILE = "sniper_debug.log" # TU BĘDĄ LOGI DO DEKODOWANIA

def log_debug(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")

def is_valid_strict(title, text, price):
    t_f = (title + " " + text).lower()
    
    # 1. TOTALNA CZARNA LISTA (Blokada śmieci ze screenów)
    forbidden = [
        "r36s", "g28", "arkos", "emulator", "retro konsola", "klon", "data frog",
        "m17", "r4", "adapter", "obudowa", "shell", "zamiennik", "części", "naprawa",
        "wyświetlacz", "lcd", "bateria", "ładowarka", "zasilacz", "etui", "case",
        "bulk", "cards", "energy", "holo", "reverse", "talia", "loose", "bootleg",
        "repro", "gra na", "sama gra", "płyta", "dyskietka", "sticker", "naklejka"
    ]
    
    for f in forbidden:
        if f in t_f:
            # log_debug(f"ODRZUCONO (Forbidden: {f}): {title}")
            return False

    # 2. KATEGORYZACJA
    cat = None
    if any(x in t_f for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "new 3ds", "2ds xl"]): cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl", "ds "]): cat = "DS_OLD"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed"]): cat = "POKE"
    
    if not cat: 
        return False

    # 3. TWARDE PROGI I LOGIKA
    limits = {"GB": 300, "PSP": 250, "3DS": 450, "DS_OLD": 200, "POKE": 160}
    min_prices = {"GB": 80, "PSP": 70, "3DS": 180, "DS_OLD": 70, "POKE": 15}
    
    limit = limits.get(cat)
    min_p = min_prices.get(cat)

    # Weryfikacja czy to konsola, a nie pojedyncza gra (jak New Zealand Story)
    is_console = any(word in t_f for word in ["konsola", "konsolę", "urządzenie"])
    
    if cat != "POKE":
        if not is_console and "zestaw" not in title.lower(): # Sprawdzamy "zestaw" tylko w tytule!
            log_debug(f"ODRZUCONO (Nie konsola/brak zestawu w tytule): {title}")
            return False
        if price < min_p:
            log_debug(f"ODRZUCONO (Za tanio - śmieć/gra): {title} ({price}zł)")
            return False

    if price > limit:
        log_debug(f"ODRZUCONO (Za drogo): {title} ({price}zł > {limit}zł)")
        return False

    log_debug(f"Puszczono: {title} | Kat: {cat} | Cena: {price}")
    return True

def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(110,128)}.0.0.0"}
    try:
        if source == "OLX":
            url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
            data = requests.get(url, headers=headers).json().get('data', [])
            for o in data:
                p = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if p: process_item(o['title'], o['url'], float(p), o.get('description', ""), source)
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers)
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
        # Wysyłanie na Telegram
        msg = f"🎯 *HIT {src}*\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        sent_links.add(clean_url)
        with open(SENT_FILE, "a") as f: f.write(clean_url + "\n")

if __name__ == "__main__":
    if not os.path.exists(SENT_FILE): open(SENT_FILE, 'w').close()
    sent_links = set(open(SENT_FILE).read().split())
    QUERIES = ["psp konsola", "3ds konsola", "dsi konsola", "gameboy advance", "pokemon booster bundle", "pokemon slab"]
    
    print("🚀 SNIPER V11.5 | DEBUG MODE | LOGS: sniper_debug.log")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(25, 45))
        time.sleep(60)
