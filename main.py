import requests
from bs4 import BeautifulSoup
import re
import os

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MAX_PRICE = 300  # 🔥 TWÓJ LIMIT

# =========================
# TELEGRAM
# =========================
def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})


# =========================
# CLEAN
# =========================
def clean(t):
    return re.sub(r"\s+", " ", t).lower()


# =========================
# PRICE (NAPRAWIONE)
# =========================
def get_price(text):
    text = text.lower()

    # usuń GB i %
    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)

    m = re.findall(r"(\d{1,5})\s*zł", text)

    if not m:
        return None

    return float(min(m))


# =========================
# FILTR
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części",
        "etui", "ładowark", "kabel",
        "bez gry", "nie działa",
        "konto", "psn",
        "naklejka", "tazo",
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
# FORMAT
# =========================
def format_msg(title, price, link, source):
    return f"""📦 {title[:90]}

💰 {price} zł

🔗 {link}
📍 {source}
"""


# =========================
# OLX
# =========================
def olx(query, label):
    print(f"\n🟢 OLX {label}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)}")

    for i in items:
        try:
            title = i.select_one("h6").text
            link = i.select_one("a")["href"]
            text = i.get_text()

            price = get_price(text)
            if not price:
                continue

            if price > MAX_PRICE:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

            send(format_msg(title, price, link, f"OLX {label}"))

        except:
            continue


# =========================
# VINTED (NAPRAWIONY LINK)
# =========================
def vinted(query):
    print("\n🟣 VINTED")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("a")

    print(f"📦 {len(items)}")

    for i in items:
        try:
            link = i.get("href")

            if not link or "/items/" not in link:
                continue

            full_link = "https://www.vinted.pl" + link
            text = i.get_text()

            price = get_price(text)
            if not price:
                continue

            if price > MAX_PRICE:
                continue

            if not is_valid(text):
                continue

            if not is_bundle(text) and price < 50:
                continue

            send(format_msg(text, price, full_link, "VINTED"))

        except:
            continue


# =========================
# ALLEGRO (NAPRAWIONE)
# =========================
def allegro(query):
    print("\n🟠 ALLEGRO")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("a")

    print(f"📦 {len(items)}")

    for i in items:
        try:
            title = i.get_text()
            link = i.get("href")

            if not link:
                continue

            if not link.startswith("http"):
                link = "https://allegrolokalnie.pl" + link

            if "promowane" in title.lower():
                continue

            price = get_price(title)
            if not price:
                continue

            if price > MAX_PRICE:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

            send(format_msg(title, price, link, "ALLEGRO"))

        except:
            continue


# =========================
# START
# =========================
print("🚀 FINAL SIMPLE BOT")

send("🚀 BOT START")

olx("pokemon", "POKEMON")
olx("psp", "PSP")
olx("nintendo 3ds", "3DS")
olx("gameboy", "GAMEBOY")

vinted("pokemon")
vinted("psp")
vinted("nintendo 3ds")
vinted("gameboy")

allegro("pokemon")
allegro("psp")
allegro("nintendo 3ds")
allegro("gameboy")