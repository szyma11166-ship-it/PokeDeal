import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# 🔧 CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# 💰 CENA (FIX)
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
# 🚫 FILTRY
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części", "obudow",
        "za sztuk", "każda", "1 szt", "pojedyncz",
        "etui", "ładowark", "kabel", "adapter",
        "bez gry", "brak gry", "nie działa",
        "do naprawy", "pobierać gry", "przerobion",
        "konto", "psn", "steam"
    ]

    return not any(b in t for b in banned)


# =========================
# 🎯 ZESTAW
# =========================
def is_bundle(title):
    t = clean(title)

    words = ["zestaw", "komplet", "kolekcja", "pakiet", "lot", "bundle", "gier", "games", "+"]

    return any(w in t for w in words)


# =========================
# 📊 ESTYMACJA WARTOŚCI
# =========================
def estimate_value(title, price):
    t = clean(title)

    value = price

    # 🎮 PSP
    if "psp" in t:
        if "gier" in t or "games" in t:
            value = price * 2

    # 🎮 3DS
    if "3ds" in t:
        if "gier" in t:
            value = price * 1.8

    # 🟩 GAMEBOY
    if "gameboy" in t:
        if "pokemon" in t:
            value = price * 2.5
        elif "gier" in t:
            value = price * 2

    # 🟥 POKEMON TCG
    if "pokemon" in t:
        if "booster" in t or "box" in t:
            value = price * 2
        elif "zestaw" in t:
            value = price * 1.8

    return value


# =========================
# 📤 OUTPUT
# =========================
def send(title, price, value, link, source):
    score = round(value - price)

    if score < 50:
        return

    print(f"🔥 OKAZJA +{score} zł")
    print(f"📦 {title[:70]}")
    print(f"💰 {price} zł | 📊 {round(value)} zł")
    print(f"🔗 {link}")
    print(f"📍 {source}")
    print("")


# =========================
# 🟢 OLX
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

            send(title, price, value, link, f"OLX {label}")

        except:
            continue


# =========================
# 🟣 VINTED
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

            send(text, price, value, "brak linku", "VINTED")

        except:
            continue


# =========================
# 🟠 ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print("\n🟠 ALLEGRO LOKALNIE...")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

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

            send(text, price, value, "brak linku", "ALLEGRO")

        except:
            continue


# =========================
# 🚀 START
# =========================
print("🚀 FINAL SNIPER BOT")
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