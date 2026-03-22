import requests
from bs4 import BeautifulSoup
import re
import os

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
    print(f"📤 WYSYŁAM:\n{msg[:120]}\n")
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# PRICE FIX (NAPRAWIONE GB)
# =========================
def get_price(text):
    text = text.lower()

    # usuwamy GB i %
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
        "uszkodz", "części", "na części",
        "etui", "ładowark", "kabel",
        "bez gry", "nie działa",
        "konto", "psn",
        "naklejka", "tazo",
        "bulk", "losowe",
        "japoń", "german", "deutsch"
    ]

    return not any(b in t for b in banned)


# =========================
# BUNDLE
# =========================
def is_bundle(title):
    t = clean(title)

    return any(w in t for w in [
        "zestaw", "pakiet", "kolekcja",
        "bundle", "lot", "+"
    ])


# =========================
# VALUE
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
        else:
            multiplier = 1.6

    elif "pokemon" in t:
        if "booster box" in t:
            multiplier = 1.5
        elif is_bundle(t):
            multiplier = 1.4

    return price * multiplier


# =========================
# POZIOM OKAZJI
# =========================
def get_level(price, value):
    diff = value - price
    ratio = value / price

    if ratio >= 1.8 or diff > 200:
        return "🚀 MEGA FLIP"
    elif ratio >= 1.5:
        return "🔥 DOBRA OKAZJA"
    elif ratio >= 1.3:
        return "💰 OKAZJA"

    return None


# =========================
# SEND
# =========================
def send(title, price, value, link, source):
    level = get_level(price, value)

    if not level:
        return

    profit = round(value - price)

    msg = f"""{level}

📦 {title[:90]}

💰 {price} zł
📊 ~{round(value)} zł
📈 +{profit} zł

🔗 {link}
📍 {source}
"""

    send_telegram(msg)


# =========================
# OLX
# =========================
def olx_search(query, label):
    print(f"\n🟢 OLX {label}...")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 ZNALEZIONO: {len(items)}")

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
# VINTED
# =========================
def vinted_search(query):
    print("\n🟣 VINTED...")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print(f"📦 ZNALEZIONO: {len(items)}")

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
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print("\n🟠 ALLEGRO LOKALNIE...")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("a")

    print(f"📦 ZNALEZIONO: {len(items)}")

    for item in items:
        try:
            title = item.get_text()
            link = item.get("href")

            if not link:
                continue

            if not link.startswith("http"):
                link = "https://allegrolokalnie.pl" + link

            if "promowane" in title.lower():
                continue

            if not is_valid(title):
                continue

            price = get_price(title)
            if not price:
                continue

            if not is_bundle(title) and price < 50:
                continue

            value = estimate_value(title, price)

            send(title, price, value, link, "ALLEGRO")

        except:
            continue


# =========================
# START
# =========================
print("🚀 FINAL SNIPER BOT v4")

send_telegram("🚀 BOT START")

olx_search("pokemon", "POKEMON")
olx_search("psp", "PSP")
olx_search("nintendo 3ds", "3DS")
olx_search("gameboy", "GAMEBOY")

vinted_search("pokemon")
vinted_search("psp")
vinted_search("nintendo 3ds")
vinted_search("gameboy")

allegro_local("pokemon")
allegro_local("psp")
allegro_local("nintendo 3ds")
allegro_local("gameboy")