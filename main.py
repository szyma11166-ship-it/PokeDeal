import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# PRICE (FIX)
# =========================
def get_price(text):
    text = text.lower()

    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)

    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

    if not matches:
        return None

    prices = [float(m.replace(",", ".")) for m in matches]
    return min(prices)


# =========================
# FILTER
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części", "obudow",
        "za sztuk", "każda", "1 szt", "pojedyncz",
        "etui", "ładowark", "kabel", "adapter",
        "bez gry", "brak gry", "nie działa",
        "do naprawy", "przerobion",
        "konto", "psn", "steam"
    ]

    return not any(b in t for b in banned)


# =========================
# BUNDLE
# =========================
def is_bundle(title):
    t = clean(title)

    words = [
        "zestaw", "komplet", "kolekcja",
        "pakiet", "lot", "bundle",
        "gier", "games", "+"
    ]

    return any(w in t for w in words)


# =========================
# VALUE (SMART)
# =========================
def estimate_value(title, price):
    t = clean(title)

    multiplier = 1.0

    if "psp" in t and is_bundle(t):
        multiplier = 1.8

    elif "3ds" in t and is_bundle(t):
        multiplier = 1.6

    elif "gameboy" in t:
        if "pokemon" in t:
            multiplier = 2.0
        elif is_bundle(t):
            multiplier = 1.7

    elif "pokemon" in t:
        if "booster box" in t:
            multiplier = 1.5
        elif is_bundle(t):
            multiplier = 1.4

    return price * multiplier


# =========================
# SEND
# =========================
def send(title, price, value, link, source):
    score = round(value - price)

    # 🔥 tylko realne okazje
    if score < 50:
        return

    print(f"🔥 OKAZJA +{score} zł")
    print(f"📦 {title[:70]}")
    print(f"💰 {price} zł | 📊 {round(value)} zł")
    print(f"🔗 {link}")
    print(f"📍 {source}")
    print("")


# =========================
# OLX
# =========================
def olx_search(query, label):
    print(f"\n🟢 OLX {label}...")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)}")

    for item in items:
        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            text = item.get_text()

            price = get_price(text)
            if not price:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

            value = estimate_value(title, price)

            # 🔥 filtr undervalue
            if value < price * 1.4:
                continue

            send(title, price, value, link, f"OLX {label}")

        except:
            continue


# =========================
# VINTED
# =========================
def vinted_search(query):
    print("\n🟣 VINTED...")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print(f"📦 {len(items)}")

    for item in items:
        try:
            text = item.get_text()
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            if not is_bundle(text) and price < 50:
                continue

            value = estimate_value(text, price)

            if value < price * 1.4:
                continue

            print(f"🔥 OKAZJA")
            print(f"📦 {text[:70]}")
            print(f"💰 {price} zł | 📊 {round(value)} zł")
            print("📍 VINTED\n")

        except:
            continue


# =========================
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print("\n🟠 ALLEGRO LOKALNIE...")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("a")

    print(f"📦 {len(items)}")

    for item in items:
        try:
            title = item.get_text().lower()
            link = item.get("href")

            if not link:
                continue

            if not link.startswith("http"):
                link = "https://allegrolokalnie.pl" + link

            if "promowane" in title:
                continue

            if not is_valid(title):
                continue

            price = get_price(title)
            if not price:
                continue

            if price > 400:
                continue

            if not is_bundle(title) and price < 50:
                continue

            value = estimate_value(title, price)

            if value < price * 1.4:
                continue

            send(title, price, value, link, "ALLEGRO")

        except:
            continue


# =========================
# START
# =========================
print("🚀 FINAL SNIPER BOT v2")
print("📤 BOT START | 0")

# 🟥 POKEMON
olx_search("pokemon", "POKEMON")

# 🎮 KONSOLE
olx_search("psp", "PSP")
olx_search("nintendo 3ds", "3DS")
olx_search("gameboy", "GAMEBOY")

# 🟣 VINTED
vinted_search("pokemon")
vinted_search("psp")
vinted_search("nintendo 3ds")
vinted_search("gameboy")

# 🟠 ALLEGRO
allegro_local("pokemon")
allegro_local("psp")
allegro_local("nintendo 3ds")
allegro_local("gameboy")