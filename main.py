import requests
from bs4 import BeautifulSoup
import re
import time
import os

# =========================
# ⚙️ CONFIG
# =========================
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MAX_PER_RUN = 5  # 🔥 anty spam

# =========================
# 📤 TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }

    r = requests.post(url, data=data)

    print("📨 TELEGRAM:", r.status_code)
    print(r.text)


# =========================
# 🔧 CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# 💰 PRICE
# =========================
def get_price(text):
    text = text.lower()

    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

    if not matches:
        return None

    return float(matches[0].replace(",", "."))


# =========================
# 🚫 FILTRY GLOBALNE
# =========================
def is_valid(text):
    t = clean(text)

    banned = [
        "uszkodz", "na części", "części",
        "etui", "kabel", "ładowark",
        "konto", "psn", "steam",
        "bulk", "lot", "mix",
        "proxy", "fake",
        "korea", "japan", "japo",
        "de ", "fr ", "it ",
        "niemie", "franc", "włos"
    ]

    return not any(b in t for b in banned)


# =========================
# 🎯 POKEMON FILTR
# =========================
def valid_pokemon(title, price):
    t = clean(title)

    # ❌ wywal śmieci
    if any(x in t for x in ["bulk", "szt", "karty", "lot", "mix"]):
        return False

    # ✔ BOOSTER
    if "booster" in t:
        return price <= 20

    # ✔ ETB
    if "etb" in t:
        return price <= 300

    # ✔ FIRST PARTNER
    if "first partner" in t:
        return price <= 150

    # ✔ POKEMON DAY
    if "pokemon day" in t:
        return price <= 70

    # ✔ ILLUSTRATION / SPECIAL
    if "illustration" in t:
        return price <= 200

    return False


# =========================
# 🎮 KONSOLE
# =========================
def valid_console(title, price):
    t = clean(title)

    if "psp" in t:
        return price <= 400

    if "gameboy" in t:
        return price <= 400

    if "3ds" in t:
        return price <= 500

    return False


# =========================
# 📤 FORMAT
# =========================
def build_msg(title, price, link, source):
    return f"""🔥 <b>OKAZJA</b>

📦 <b>{title[:80]}</b>

💰 <b>{price} zł</b>
📍 {source}

🔗 {link}
"""


# =========================
# 🟢 OLX
# =========================
def olx(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")

    sent = 0

    for item in items:
        if sent >= MAX_PER_RUN:
            break

        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            price = get_price(item.get_text())

            if not price:
                continue

            if not is_valid(title):
                continue

            if "pokemon" in query:
                if not valid_pokemon(title, price):
                    continue
            else:
                if not valid_console(title, price):
                    continue

            msg = build_msg(title, price, link, "OLX")
            send_telegram(msg)

            sent += 1

        except:
            continue


# =========================
# 🟣 VINTED
# =========================
def vinted(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    sent = 0

    for item in items:
        if sent >= MAX_PER_RUN:
            break

        try:
            text = item.get_text()
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not valid_pokemon(text, price):
                    continue
            else:
                if not valid_console(text, price):
                    continue

            msg = build_msg(text, price, "brak linku", "VINTED")
            send_telegram(msg)

            sent += 1

        except:
            continue


# =========================
# 🟠 ALLEGRO LOKALNIE
# =========================
def allegro(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    sent = 0

    for item in items:
        if sent >= MAX_PER_RUN:
            break

        try:
            title = item.get_text()
            link_tag = item.select_one("a")
            link = "https://allegrolokalnie.pl" + link_tag["href"] if link_tag else "brak linku"

            price = get_price(title)

            if not price:
                continue

            if not is_valid(title):
                continue

            if "pokemon" in query:
                if not valid_pokemon(title, price):
                    continue
            else:
                if not valid_console(title, price):
                    continue

            msg = build_msg(title, price, link, "ALLEGRO")
            send_telegram(msg)

            sent += 1

        except:
            continue


# =========================
# 🚀 START
# =========================
print("🚀 SNIPER START")

while True:
    try:
        olx("pokemon")
        vinted("pokemon")
        allegro("pokemon")

        olx("psp")
        vinted("psp")
        allegro("psp")

        olx("gameboy")
        vinted("gameboy")
        allegro("gameboy")

        olx("nintendo 3ds")
        vinted("nintendo 3ds")
        allegro("nintendo 3ds")

        print("⏳ SLEEP 60s")
        time.sleep(60)

    except Exception as e:
        print("❌ ERROR:", e)
        time.sleep(30)