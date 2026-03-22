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
# BLACKLIST (MOCNA)
# =========================
blacklist = [
    "album", "plusz", "figurka", "zabawka",
    "funko", "maskotka", "bulk", "mix",
    "pojedyncza", "single", "karta", "karty",
    "promo", "gx", "v", "ex", "vmax", "vstar",
    "ładowarka", "zasilacz", "kabel",
    "uszkodz", "na części", "części",
    "gra", "gry", "cd", "dvd"
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

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg}
    )

# =========================
# HELPERS
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

# 🔥 FIX NA GB / zł
def extract_price(text):
    text = text.lower().replace(",", ".")

    # 🎯 najpierw szukaj ceny przed zł
    match = re.search(r"(\d+[.,]?\d*)\s*zł", text)
    if match:
        return float(match.group(1))

    # fallback
    prices = re.findall(r"\d+\.\d+|\d+", text)

    for p in prices:
        val = float(p)
        if 20 < val < 10000:
            return val

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
        "booster bundle", "ultra premium",
        "collection", "box", "tin", "set"
    ])

def pokemon_level(name, price):
    name = name.lower()

    if "elite trainer box" in name or "etb" in name:
        if price < 250:
            return "🔥🔥🔥 ETB"

    if "bundle" in name or "set" in name or "3 booster" in name or "4 booster" in name:
        if price < 120:
            return "🔥🔥 BUNDLE"

    if "booster" in name and any(x in name for x in ["2", "3", "4", "5"]):
        if price < 120:
            return "🔥🔥 MULTI"

    if "booster" in name and "box" not in name:
        if price < 20:
            return "🔥 BOOSTER"

    if "ultra premium" in name:
        if price < 500:
            return "🔥🔥🔥 PREMIUM"

    if "tin" in name or "collection" in name:
        if price < 150:
            return "🔥 COLLECTION"

    return None

# =========================
# KONSOLE
# =========================
def is_console(name):
    return any(k in name for k in [
        "psp", "3ds", "dsi", "gameboy", "gba"
    ])

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
# OLX SEARCH
# =========================
def scan_olx(url, label):
    print(f"\n🟢 OLX {label}...")

    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("div", {"data-cy": "l-card"})
    print("📦 ZNALEZIONO:", len(items))

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

            # 🎯 POKEMON
            if is_pokemon(text) and is_real_pokemon(text):
                tag = pokemon_level(text, price)

            # 🎮 KONSOLE
            elif is_console(text):
                tag = console_level(text, price)

            else:
                continue

            if tag:
                print("✅", text[:60])
                send(text[:80], price, link, tag, f"OLX {label}")

        except:
            continue

# =========================
# START
# =========================
print("🚀 FINAL ULTRA BOT")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    scan_olx("https://www.olx.pl/oferty/q-pokemon/", "POKEMON")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-psp/", "PSP")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-nintendo-3ds/", "3DS")
    time.sleep(10)

    scan_olx("https://www.olx.pl/oferty/q-gameboy/", "GAMEBOY")
    time.sleep(15)