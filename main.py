import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# 🔑 TOKEN + CHAT ID
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = -1003743099672

print("🚀 SNIPER START")
print("TOKEN:", BOT_TOKEN)

sent_links = set()

# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# PRICE
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
# GLOBAL FILTER
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części",
        "etui", "ładowark", "kabel",
        "konto", "psn", "steam",
        "bulk", "lot", "mix", "random",
        "japanese", "korea", "korean",
        "de ", "fr ", "it "
    ]

    return not any(b in t for b in banned)


# =========================
# GAME FILTER
# =========================
def is_game(title):
    t = clean(title)

    game_words = [
        "gra", "game", "fifa", "lego",
        "pokemon y", "pokemon x",
        "mario", "zelda"
    ]

    return any(g in t for g in game_words)


# =========================
# CONSOLE FILTER
# =========================
def console_filter(query, title, price):
    t = clean(title)

    # musi być sprzęt
    if not any(x in t for x in ["konsol", "console", "psp", "3ds", "gameboy", "nintendo"]):
        return False

    # wywal gry
    if is_game(title):
        return False

    # limity cenowe
    if "psp" in query:
        return price <= 200

    if "3ds" in query:
        return price <= 400

    if "gameboy" in query:
        return price <= 300

    return False


# =========================
# TELEGRAM
# =========================
def send(title, price, link, source):
    if not link or "http" not in link:
        return

    if link in sent_links:
        return

    sent_links.add(link)

    msg = f"""🔥 OKAZJA

📦 {title[:80]}

💰 {price} zł
📍 {source}

🔗 {link}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })

        print("📨 TELEGRAM STATUS:", r.status_code)
        print("📨 RESPONSE:", r.text)

    except Exception as e:
        print("❌ TELEGRAM ERROR:", e)


# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")

    print("📦 znaleziono:", len(items))

    count = 0

    for item in items:
        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            price = get_price(item.get_text())

            if not price or not is_valid(title):
                continue

            if not console_filter(query, title, price):
                continue

            send(title, price, link, "OLX")
            count += 1

            if count >= 5:
                break

        except:
            continue


# =========================
# VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print("📦 znaleziono:", len(items))

    count = 0

    for item in items:
        try:
            a = item.select_one("a")
            if not a:
                continue

            link = a["href"]
            if not link.startswith("http"):
                link = "https://www.vinted.pl" + link

            title = item.get_text()
            price = get_price(title)

            if not price or not is_valid(title):
                continue

            if not console_filter(query, title, price):
                continue

            send(title, price, link, "VINTED")
            count += 1

            if count >= 5:
                break

        except:
            continue


# =========================
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    print("📦 znaleziono:", len(items))

    count = 0

    for item in items:
        try:
            if "Promowane" in item.get_text():
                continue

            a = item.select_one("a")
            if not a:
                continue

            link = "https://allegrolokalnie.pl" + a["href"]

            title_tag = item.select_one("h2")
            if not title_tag:
                continue

            title = title_tag.text
            price = get_price(item.get_text())

            if not price or not is_valid(title):
                continue

            if not console_filter(query, title, price):
                continue

            send(title, price, link, "ALLEGRO")
            count += 1

            if count >= 5:
                break

        except:
            continue


# =========================
# START
# =========================
import time

print("🔁 BOT LOOP START")

while True:
    try:
        print("\n🚀 NOWY CYKL")

        olx_search("psp")
        vinted_search("psp")
        allegro_local("psp")

        olx_search("nintendo 3ds")
        vinted_search("nintendo 3ds")
        allegro_local("nintendo 3ds")

        olx_search("gameboy")
        vinted_search("gameboy")
        allegro_local("gameboy")

        print("⏳ Czekam 60 sekund...\n")
        time.sleep(60)  # co ile odświeża

    except Exception as e:
        print("❌ LOOP ERROR:", e)
        time.sleep(30)