import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import hashlib

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = os.getenv("CHAT_ID") or "-1003743099672"
SENT_FILE = "sent_links.txt"
LOG_FILE = "sniper_debug.log"

def log_debug(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {msg}\n")

def get_hash(title, price):
    raw = f"{title[:50]}_{int(price)}"
    return hashlib.md5(raw.encode()).hexdigest()

def is_valid_strict(title, text, price):
    t_f = (title + " " + (text or "")).lower()
    
    # 1. KATEGORYZACJA
    cat = None
    if any(x in t_f for x in ["gameboy", "game boy", "gba", "gbc", "advance", "dmg"]): cat = "GB"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds", "n2ds"]): cat = "3DS"
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl", "ds "]): cat = "DS_OLD"
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed", "box"]): cat = "POKE"
    
    if not cat:
        return False, None

    # 2. PROGI CENOWE
    limits = {"GB": 300, "PSP": 250, "3DS": 450, "DS_OLD": 200, "POKE": 160}
    min_prices = {"GB": 80, "PSP": 70, "3DS": 180, "DS_OLD": 70, "POKE": 15}
    
    if price > limits.get(cat, 999) or price < min_prices.get(cat, 0):
        log_debug(f"ODRZUCONO (Cena {price}): {title}")
        return False, None

    # 3. LOGIKA SPRZĘTOWA
    # Dodane same nazwy konsol jako HW
    hw_keywords = [
        "konsola", "zestaw", "sprawna", "gameboy", "game boy", "gba", "psp", "3ds", "2ds", "dsi",
        "1004", "2004", "3004", "street", "e1004", "go", "xl", "lite",
        "booster", "box", "sealed", "tali", "deck" # Dla Pokemonów
    ]
    
    is_hardware = any(hw in t_f for hw in hw_keywords)

    hard_forbidden = ["r36s", "g28", "arkos", "emulator", "klon", "data frog", "repro", "3d printed", "drukarka 3d"]
    if any(f in t_f for f in hard_forbidden):
        log_debug(f"ODRZUCONO (HardForbidden): {title}")
        return False, None

    soft_forbidden = ["adapter", "obudowa", "shell", "zamiennik", "części", "naprawa", "wyświetlacz", "bateria", "ładowarka"]

    if not is_hardware:
        if any(s in t_f for s in soft_forbidden):
            log_debug(f"ODRZUCONO (SoftForbidden + brak HW): {title}")
            return False, None
        if cat != "POKE":
            log_debug(f"ODRZUCONO (Nie sprzęt): {title}")
            return False, None

    return True, cat

# --- SCRAPING ---

def process_item(title, url, price, text, src):
    full_url = url if "http" in url else f"https://www.vinted.pl{url}"
    clean_url = full_url.split("?")[0].rstrip("/")
    item_hash = get_hash(title, price)
    
    if item_hash in sent_hashes or clean_url in sent_hashes: 
        return

    valid, cat = is_valid_strict(title, text, price)
    if not valid: 
        return

    # Jeśli przeszło przez filtr, logujemy to!
    log_debug(f"PRZEPUSZCZONO: {title} | {price} zł")

    score = score_deal(cat, price)
    msg = f"{score} | {src}\n━━━━━━━━━━━━━━━━━━━━\n📦 *{title[:70]}*\n💰 Cena: `{price:.2f} zł`\n━━━━━━━━━━━━━━━━━━━━\n🔗 [KUP TERAZ]({clean_url})"
    
    send_telegram(msg)
    sent_hashes.add(item_hash)
    sent_hashes.add(clean_url)
    with open(SENT_FILE, "a") as f: f.write(f"{item_hash}\n{clean_url}\n")

# ... (reszta funkcji scrape_olx i scrape_vinted bez zmian) ...
