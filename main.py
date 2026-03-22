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
# BLACKLIST
# =========================
blacklist = [
    "album", "plusz", "figurka", "zabawka",
    "funko", "maskotka", "bulk", "mix",
    "pojedyncza", "single", "karta", "karty",
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
    msg = f"""
{tag} • {shop}

📦 {title}

💸 {price} zł

🔗 {link}
"""
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

def extract_price(text):
    text = text.replace(",", ".")
    prices = re.findall(r"\d+\.\d+|\d+", text)

    for p in prices:
        val = float(p)
        if val > 20:
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
        "booster bundle", "ultra premium", "collection"
    ])

def pokemon_level(name, price):
    if "elite trainer box" in name and price < 250:
        return "🔥🔥🔥 ETB"
    if "booster bundle" in name and price < 100:
        return "🔥🔥 BUNDLE"
    if "booster" in name and "box" not in name and price < 20:
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

def console_level(name, price):
    if "psp" in name and price < 200:
        return "🎮 PSP FLIP"
    if "3ds" in name and price < 300:
        return "🎮 3DS FLIP"
    if "dsi" in name and price < 150:
        return "🎮 DSI FLIP"
    if ("gameboy" in name or "gba" in name) and price < 250:
        return "🎮 GAMEBOY FLIP"
    return None

# =========================
# OLX
# =========================
def check_olx():
    print("\n🟢 OLX...")
    url = "https://www.olx.pl/oferty/q-pokemon/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("div", {"data-cy": "l-card"}):
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

            if is_pokemon(text) and is_real_pokemon(text):
                tag = pokemon_level(text, price)
            elif is_console(text):
                tag = console_level(text, price)
            else:
                continue

            if tag:
                send(text[:80], price, link, tag, "OLX")

        except:
            continue

# =========================
# VINTED
# =========================
def check_vinted():
    print("\n🟣 VINTED...")
    url = "https://www.vinted.pl/catalog?search_text=pokemon"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.find_all("a", href=True):
        try:
            text = a.get_text().lower()
            link = a["href"]

            if not link.startswith("http"):
                link = "https://www.vinted.pl" + link

            if not is_new(link) or is_bad(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            if is_pokemon(text) and is_real_pokemon(text):
                tag = pokemon_level(text, price)
            elif is_console(text):
                tag = console_level(text, price)
            else:
                continue

            if tag:
                send(text[:80], price, link, tag, "Vinted")

        except:
            continue

# =========================
# AMAZON
# =========================
def check_amazon():
    print("\n🟡 AMAZON...")
    url = "https://www.amazon.pl/s?k=pokemon+tcg+booster"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.select("div[data-component-type='s-search-result']"):
        try:
            text = item.get_text().lower()
            link = "https://amazon.pl" + item.find("a")["href"]

            if not is_new(link) or is_bad(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            if is_pokemon(text) and is_real_pokemon(text):
                tag = pokemon_level(text, price)
            elif is_console(text):
                tag = console_level(text, price)
            else:
                continue

            if tag:
                send(text[:80], price, link, tag, "Amazon")

        except:
            continue

# =========================
# ALLEGRO LOKALNIE (RSS)
# =========================
def check_allegro_local():
    print("\n🟠 ALLEGRO LOKALNIE...")
    url = "https://allegrolokalnie.pl/oferty/q/pokemon/rss"
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("item"):
        try:
            title = item.title.text.lower()
            link = item.link.text

            if not is_new(link) or is_bad(title):
                continue

            price = extract_price(title)
            if not price:
                continue

            if is_pokemon(title) and is_real_pokemon(title):
                tag = pokemon_level(title, price)
            elif is_console(title):
                tag = console_level(title, price)
            else:
                continue

            if tag:
                send(title[:80], price, link, tag, "Allegro Lokalnie")

        except:
            continue

# =========================
# START
# =========================
print("🚀 ULTRA FLIP BOT")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    check_olx()
    time.sleep(15)

    check_vinted()
    time.sleep(20)

    check_amazon()
    time.sleep(25)

    check_allegro_local()
    time.sleep(30)