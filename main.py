import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# BLACKLIST PRO MAX
# =========================
blacklist = [
    "album", "plusz", "figurka", "zabawka",
    "funko", "maskotka", "bulk", "mix",
    "pojedyncza", "single", "karta", "karty",
    "promo", "gx", "vmax", "vstar",
    "ładowarka", "zasilacz", "kabel", "adapter",
    "gra", "gry", "game", "cd", "dvd",
    "plecak", "torba", "etui", "case",
    "lego",
    "uszkodz", "nie działa", "na części"
]

bad_languages = [
    "japo", "jp", "german", "niem", "de",
    "french", "fr", "italian", "it"
]

# =========================
# SEND
# =========================
def send(title, price, link, tag, shop):
    msg = f"""{tag} • {shop}

📦 {title}

💸 {price} zł

🔗 {link}"""

    print("📤", shop, "|", title[:60], "|", price)

    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except:
        pass

# =========================
# HELPERS
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

def extract_price(text):
    text = text.lower().replace(",", ".")

    match = re.search(r"(\d+[.,]?\d*)\s*zł", text)
    if match:
        return float(match.group(1))

    return None

def is_bad(name):
    name = name.lower()
    return any(w in name for w in blacklist) or any(l in name for l in bad_languages)

# =========================
# POKEMON
# =========================
def is_pokemon(name):
    return "pokemon" in name or "pokémon" in name

def is_real_pokemon(name):
    return any(k in name for k in [
        "booster", "etb", "elite trainer box",
        "bundle", "collection", "box", "tin", "set"
    ])

def pokemon_level(name, price):
    if "etb" in name or "elite trainer" in name:
        if price < 250:
            return "🔥🔥🔥 ETB"
    if "bundle" in name or "set" in name:
        if price < 120:
            return "🔥🔥 BUNDLE"
    if "booster" in name and price < 20:
        return "🔥 BOOSTER"
    if "ultra premium" in name and price < 500:
        return "🔥🔥🔥 PREMIUM"
    return None

# =========================
# KONSOLE
# =========================
def is_console(name):
    return any(k in name for k in [
        "psp", "3ds", "dsi", "gameboy", "gba"
    ])

def is_real_console(name):
    name = name.lower()

    if any(x in name for x in [
        "gra", "gry", "game", "cd", "dvd",
        "ładowarka", "kabel", "adapter",
        "etui", "case", "pokrowiec"
    ]):
        return False

    return True

def console_level(name, price):
    if "psp" in name and price < 220:
        return "🎮 PSP FLIP"
    if "3ds" in name and price < 320:
        return "🎮 3DS FLIP"
    if "dsi" in name and price < 170:
        return "🎮 DSI FLIP"
    if ("gameboy" in name or "gba" in name) and price < 280:
        return "🎮 GAMEBOY FLIP"
    return None

# =========================
# OLX
# =========================
def scan_olx(url, label):
    print(f"\n🟢 OLX {label}...")

    try:
        r = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.find_all("div", {"data-cy": "l-card"})
        print("📦", len(items))

        for item in items:
            try:
                text = item.get_text().lower()
                link = item.find("a")["href"]

                if not link.startswith("http"):
                    link = "https://www.olx.pl" + link

                if not is_new(link) or is_bad(text):
                    continue

                price = extract_price(text)
                if not price:
                    continue

                tag = None

                if is_pokemon(text) and is_real_pokemon(text):
                    tag = pokemon_level(text, price)

                elif is_console(text) and is_real_console(text):
                    tag = console_level(text, price)

                if tag:
                    send(text[:80], price, link, tag, f"OLX {label}")

            except:
                continue
    except:
        print("❌ OLX ERROR")

# =========================
# VINTED
# =========================
def scan_vinted():
    print("\n🟣 VINTED...")

    try:
        url = "https://www.vinted.pl/catalog?search_text=pokemon"
        r = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.find_all("a", href=True)
        print("📦", len(items))

        for item in items:
            try:
                text = item.get_text().lower()
                link = "https://www.vinted.pl" + item["href"]

                if not is_new(link) or is_bad(text):
                    continue

                price = extract_price(text)
                if not price:
                    continue

                if is_pokemon(text):
                    tag = pokemon_level(text, price)
                    if tag:
                        send(text[:80], price, link, tag, "VINTED")

                elif is_console(text):
                    tag = console_level(text, price)
                    if tag:
                        send(text[:80], price, link, tag, "VINTED")

            except:
                continue
    except:
        print("❌ VINTED ERROR")

# =========================
# ALLEGRO LOKALNIE (FIX RSS)
# =========================
def scan_allegro_local():
    print("\n🟠 ALLEGRO LOKALNIE...")

    try:
        url = "https://allegrolokalnie.pl/oferty/q/pokemon?order=new"
        r = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.find_all("a", href=True)
        print("📦", len(items))

        for item in items:
            try:
                text = item.get_text().lower()
                link = item["href"]

                if not link.startswith("http"):
                    link = "https://allegrolokalnie.pl" + link

                if not is_new(link) or is_bad(text):
                    continue

                price = extract_price(text)
                if not price:
                    continue

                if is_pokemon(text):
                    tag = pokemon_level(text, price)
                    if tag:
                        send(text[:80], price, link, tag, "ALLEGRO")

                elif is_console(text):
                    tag = console_level(text, price)
                    if tag:
                        send(text[:80], price, link, tag, "ALLEGRO")

            except:
                continue
    except:
        print("❌ ALLEGRO ERROR")

# =========================
# START
# =========================
print("🚀 FINAL ULTRA FLIP BOT")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    scan_olx("https://www.olx.pl/oferty/q-pokemon/", "POKEMON")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-psp/", "PSP")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-nintendo-3ds/", "3DS")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-gameboy/", "GAMEBOY")
    time.sleep(10)

    scan_vinted()
    time.sleep(10)

    scan_allegro_local()
    time.sleep(20)