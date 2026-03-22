import requests
from bs4 import BeautifulSoup
import re
import os
import time

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

seen = set()

# =========================
# 📤 TELEGRAM
# =========================
def send(title, price, link, source):
    msg = f"📍 {source}\n\n📦 {title[:100]}\n💰 {price} zł\n\n🔗 {link}"

    print(f"📤 {source} | {price} zł")

    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        print("❌ TELEGRAM ERROR")


# =========================
# 🔧 CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# 💰 CENA (FIX FINAL)
# =========================
def get_price(text):
    text = text.lower()

    # usuń GB i %
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
        "do naprawy", "konto", "psn", "steam",
        "bulk", "japo", "korea", "chiń", "fake",
        "proxy", "naklejka", "tazo"
    ]

    return not any(b in t for b in banned)


# =========================
# 🎯 BUNDLE ONLY
# =========================
def is_bundle(title):
    t = clean(title)

    words = [
        "zestaw", "komplet", "kolekcja",
        "pakiet", "lot", "bundle",
        "gier", "games", "+", "x"
    ]

    return any(w in t for w in words)


# =========================
# 🔁 DUPLIKATY
# =========================
def is_new(link):
    if link in seen:
        return False
    seen.add(link)
    return True


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

            if not link.startswith("http"):
                link = "https://www.olx.pl" + link

            if not is_new(link):
                continue

            price = get_price(item.get_text())

            if not price:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

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

            link_tag = item.find("a")
            if not link_tag:
                continue

            link = link_tag.get("href")

            if not link.startswith("http"):
                link = "https://www.vinted.pl" + link

            if not is_new(link):
                continue

            send(text, price, link, "VINTED")

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

            a = item.find("a")
            if not a:
                continue

            link = a.get("href")

            if not link.startswith("http"):
                link = "https://allegrolokalnie.pl" + link

            if not is_new(link):
                continue

            price = get_price(title)

            if not price:
                continue

            if not is_valid(title):
                continue

            if not is_bundle(title) and price < 50:
                continue

            send(title, price, link, "ALLEGRO")

        except:
            continue


# =========================
# 🚀 START LOOP
# =========================
print("🚀 FINAL SNIPER BOT")
send("BOT START", 0, "-", "SYSTEM")

while True:
    try:
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

    except Exception as e:
        print("❌ ERROR:", e)

    time.sleep(60)