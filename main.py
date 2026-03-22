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
    "etui","case","pokrowiec","naklejka","folia",
    "szkło","uszkodz","części","na części",
    "pudełko","box empty",
    "gratis","oddam","rezerwacja",
    "tazo","nakretki","mirinda",
    "bulk","losowe karty","mix kart",
    "japoń","korea","chiń","niemieck","franc",

    # 🔥 gry które spamują OLX
    "yoshi","donkey","mario","fifa","zelda"
]

# =========================
# SEND
# =========================
def send(title, price, link, tag, source):
    msg = f"{tag} | {source}\n\n"
    msg += f"📦 {title[:80]}\n"
    msg += f"💰 {price} zł\n\n"
    msg += f"🔗 {link}"

    print("📤", msg)

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })

# =========================
# PRICE FIX (PLN ONLY)
# =========================
def extract_price(text):
    text = text.replace(",", ".")
    numbers = re.findall(r"\d+\.\d+|\d+", text)

    for n in numbers:
        val = float(n)

        if val < 10:
            continue

        # ❌ ignoruj GB pamięci
        if val in [16,32,64,128,256,512]:
            continue

        return val

    return None

# =========================
# FILTERS
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

def is_blacklisted(name):
    name = name.lower()
    return any(b in name for b in blacklist)

def is_pokemon(name):
    return "pokemon" in name or "pokémon" in name

# =========================
# 🔥 KONSOLE FILTER (FINAL FIX)
# =========================
def is_real_console(name):
    name = name.lower()

    # ❌ akcesoria
    if any(x in name for x in [
        "ładowarka","kabel","adapter","etui","case"
    ]):
        return False

    # ❌ pojedyncze gry (mocny filtr)
    if any(x in name for x in [
        "psp","3ds","dsi","gameboy"
    ]):
        if any(x in name for x in [
            "pokemon","mario","donkey","zelda",
            "yoshi","fifa","gta","call of duty",
            "need for speed"
        ]):
            if not any(x in name for x in [
                "zestaw","pakiet","kolekcja","bundle",
                "10 gier","5 gier","kilka gier"
            ]):
                return False

    return True

# =========================
# LEVEL SYSTEM
# =========================
def pokemon_level(name, price):
    name = name.lower()

    if "elite trainer box" in name and price < 280:
        return "🟣 MEGA DEAL"
    if "booster box" in name and price < 600:
        return "🟣 MEGA DEAL"
    if "booster" in name and price < 20:
        return "🟣 DEAL"
    if "premium" in name and price < 500:
        return "🟣 DEAL"

    return None

def console_level(name, price):
    name = name.lower()

    if "psp" in name and price < 220:
        return "🎮 FLIP"
    if "3ds" in name and price < 300:
        return "🎮 FLIP"
    if "dsi" in name and price < 150:
        return "🎮 FLIP"
    if "gameboy" in name and price < 250:
        return "🎮 FLIP"

    # 🔥 zestawy gier
    if any(x in name for x in ["zestaw","kolekcja","pakiet"]):
        if price < 200:
            return "🔥 GAME LOT"

    return None

# =========================
# OLX
# =========================
def check_olx(query, tag):
    print(f"\n🟢 OLX {tag}...")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("div", {"data-cy": "l-card"})
    print("📦 ZNALEZIONO:", len(items))

    for item in items:
        try:
            a = item.find("a")
            if not a:
                continue

            link = a["href"]
            text = item.get_text().lower()

            if not link.startswith("http"):
                link = "https://www.olx.pl" + link

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            # 🎮 KONSOLE
            if tag != "POKEMON":
                if not is_real_console(text):
                    continue

                level = console_level(text, price)
                if level:
                    send(text, price, link, level, f"OLX {tag}")

            # 🟣 POKEMON
            else:
                level = pokemon_level(text, price)
                if level:
                    send(text, price, link, level, "OLX POKEMON")

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

    items = soup.find_all("a", href=True)
    print("📦", len(items))

    for item in items[:80]:
        try:
            text = item.get_text().lower()
            link = "https://www.vinted.pl" + item["href"]

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            level = pokemon_level(text, price)
            if level:
                send(text, price, link, level, "VINTED")

        except:
            continue

# =========================
# ALLEGRO LOKALNIE
# =========================
def check_allegro_local():
    print("\n🟠 ALLEGRO LOKALNIE...")

    url = "https://allegrolokalnie.pl/oferty/q/pokemon"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("a", href=True)
    print("📦", len(items))

    for item in items[:100]:
        try:
            text = item.get_text().lower()
            link = item["href"]

            if not link.startswith("http"):
                link = "https://allegrolokalnie.pl" + link

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            level = pokemon_level(text, price)
            if level:
                send(text, price, link, level, "ALLEGRO")

        except:
            continue

# =========================
# START
# =========================
print("🚀 FINAL SNIPER BOT")
send("BOT START", 0, "", "🚀 BOT", "SYSTEM")

while True:
    check_olx("pokemon", "POKEMON")
    check_olx("psp", "PSP")
    check_olx("nintendo-3ds", "3DS")
    check_olx("gameboy", "GAMEBOY")

    check_vinted()
    check_allegro_local()

    time.sleep(60)