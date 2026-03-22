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
# 💰 CENA (FINAL FIX)
# =========================
def get_price(text):
    text = text.lower()

    # usuń rzeczy które psują parsing
    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)

    # szukaj tylko zł
    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

    if not matches:
        return None

    # bierz NAJNIŻSZĄ sensowną (chroni przed scam listingami)
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
# 🎯 ZESTAWY (WAŻNE)
# =========================
def is_bundle(title):
    t = clean(title)

    bundle_words = [
        "zestaw", "komplet", "kolekcja",
        "pakiet", "lot", "bundle",
        "gier", "games", "x", "+"
    ]

    return any(w in t for w in bundle_words)


# =========================
# 📤 OUTPUT
# =========================
def send(title, price, link, source):
    print(f"📤 {source} | {title[:70]} | {price} zł")
    print(link)
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

            price = get_price(item.get_text())

            if not price:
                continue

            if not is_valid(title):
                continue

            # 🔥 tylko sensowne flippy
            if not is_bundle(title) and price < 50:
                continue

            print(f"✅ {title[:60]}")
            send(title, price, link, f"OLX {label}")

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

            print(f"📤 VINTED | {text[:60]} | {price} zł")

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
            title = item.get_text()
            price = get_price(title)

            if not price:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

            print(f"📤 ALLEGRO | {title[:60]} | {price} zł")

        except:
            continue


# =========================
# 🚀 START
# =========================
print("🚀 FINAL SNIPER BOT")
print("📤 BOT START | 0")

# 🎯 POKEMON
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