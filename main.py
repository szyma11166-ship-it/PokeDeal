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
    
    # 1. CZERWONA LISTA (Blokada śmieci ze screenów: bulk, karty luzem, podróbki, części)
    forbidden = [
        "r4", "adapter", "karta pamięci", "cover", "obudowa", "shell", "zamiennik", 
        "części", "naprawa", "wyświetlacz", "lcd", "bateria", "ładowarka", "zasilacz", 
        "etui", "case", "pudełko", "instrukcja", "manual", "bootleg", "repro",
        "bulk", "cards", "energy", "holo", "reverse", "foil", "talia", "loose",
        "sup", "anbernic", "powkiddy", "miyoo", "data frog", "alba", "plecak", "torba",
        "gry", "gra na", "sama gra", "płyta", "dyskietka", "sticker", "naklejka"
    ]
    if any(f in t_f for f in forbidden): return False

    # 2. IDENTYFIKACJA I TWARDE LIMITY CENOWE
    cat = None
    if any(x in t_f for x in ["gameboy", "gba", "gbc", "advance", "dmg"]): 
        cat = "GB"; limit = 300; min_p = 80
    elif "psp" in t_f: 
        cat = "PSP"; limit = 250; min_p = 70
    elif any(x in t_f for x in ["3ds", "new 3ds", "2ds xl"]): 
        cat = "3DS"; limit = 450; min_p = 180
    elif any(x in t_f for x in ["dsi", "ds lite", "ndsl", "ds "]): 
        cat = "DS_OLD"; limit = 200; min_p = 70 # DSi MAX 200 ZŁ
    elif any(x in t_f for x in ["booster", "bundle", "psa", "slab", "sealed", "illustration"]): 
        cat = "POKE"; limit = 160; min_p = 15

    if not cat: return False

    # 3. FILTR "ANTY-SINGIEL" (Wycinanie Lord of Arcana i innych pojedynczych gier)
    if cat in ["GB", "PSP", "3DS", "DS_OLD"]:
        # Musi być słowo "konsola" lub "zestaw", żeby przeszło przy niskiej cenie
        if "konsola" not in t_f and "zestaw" not in t_f:
            return False
        if price < min_p: return False # Wywala tanie akcesoria udające okazje

    # 4. FILTR POKEMON (Tylko Sealed & Slabs - wywala zestawy kart ze screenów)
    if cat == "POKE":
        if any(bad in t_f for bad in ["karta", "karty", "zestaw", "lot", "bulk"]):
            # Przepuść tylko jeśli to slab (PSA/BGS/CGC)
            if not any(s in t_f for s in ["psa", "slab", "bgs", "cgc", "graad"]):
                return False

    return price <= limit

def scrape(source, query):
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(115,128)}.0.0.0"}
    try:
        if source == "OLX":
            url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json().get('data', [])
            for o in data:
                p = o.get('price', {}).get('value', {}).get('amount') or o.get('price', {}).get('amount')
                if p: process_item(o['title'], o['url'], float(p), o.get('description', ""), source)
        
        elif source == "VINTED":
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=5)
            url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
            r = s.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all("div", {"data-testid": re.compile(r"grid-item")}):
                link_tag = card.find("a", href=True)
                p_txt = card.get_text(separator=" ")
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", p_txt)
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
    
    # Bardzo surowe zapytania, żeby nie prowokować śmieciowych wyników
    QUERIES = ["psp konsola", "3ds konsola", "dsi konsola", "gameboy advance", "pokemon booster bundle", "pokemon slab psa"]
    
    print("🚀 SNIPER V11.4 ONLINE | EXTERMINATOR MODE")
    while True:
        for q in QUERIES:
            for src in ["OLX", "VINTED"]:
                scrape(src, q)
                time.sleep(random.randint(25, 45))
        time.sleep(60)
