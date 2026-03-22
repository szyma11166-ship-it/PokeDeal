import requests
from bs4 import BeautifulSoup
import re
import time

# =========================
# 🔑 TELEGRAM
# =========================
BOT_TOKEN = "TWÓJ_TOKEN_ZOSTAJE"
CHAT_ID = "-1003743099672"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text
    }
    try:
        requests.post(url, data=data)
    except:
        pass


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# 🔧 CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()

# =========================
# 💰 CENA
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
# 🚫 GLOBALNE FILTRY
# =========================
def is_valid(text):
    t = clean(text)

    banned = [
        "uszkodz", "części", "na części",
        "etui", "ładowark", "kabel",
        "konto", "psn", "steam",
        "bez gry", "brak gry",
        "do naprawy",
        "za sztuk", "1 szt",
        "fake", "replika",
    ]

    # ❌ języki
    banned_lang = ["de", "fr", "it"]

    if any(b in t for b in banned):
        return False

    if any(f" {l} " in t for l in banned_lang):
        return False

    return True

# =========================
# 🎯 POKEMON FILTRY
# =========================
def pokemon_filter(title, price):
    t = clean(title)

    # ❌ bulk / śmieci
    if any(x in t for x in ["bulk", "100 kart", "200 kart", "losowe", "mix kart"]):
        return False

    # 🎯 BOOSTER
    if "booster" in t:
        return price <= 20

    # 🎯 ETB
    if "elite trainer box" in t or "etb" in t:
        return price <= 300

    # 🎯 FIRST PARTNER
    if "first partner" in t:
        return price <= 150

    # 🎯 POKEMON DAY
    if "pokemon day" in t or "day 2026" in t:
        return price <= 70

    # 🎯 BUNDLE / BOX
    if any(x in t for x in ["bundle", "box", "collection", "tin", "illustration"]):
        return price <= 250

    return False

# =========================
# 📤 OUTPUT
# =========================
def send(title, price, link, source):
    msg = f"""🔥 OKAZJA

📦 {title[:80]}

💰 {price} zł
📍 {source}

🔗 {link}
"""
    print(msg)
    send_telegram(msg)

# =========================
# 🟢 OLX
# =========================
def olx_search(query, label):
    print(f"\n🟢 OLX {label}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            text = item.get_text()

            price = get_price(text)

            if not price:
                continue

            full_text = title + " " + text

            if not is_valid(full_text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(full_text, price):
                    continue
            else:
                if price < 100:
                    continue

            send(title, price, link, f"OLX {label}")
            sent += 1

            if sent >= 5:
                break

        except:
            continue

# =========================
# 🟣 VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            text = item.get_text()
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(text, price):
                    continue
            else:
                if price < 100:
                    continue

            send(text[:60], price, "brak linku", "VINTED")
            sent += 1

            if sent >= 5:
                break

        except:
            continue

# =========================
# 🟠 ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            text = item.get_text()
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(text, price):
                    continue
            else:
                if price < 100:
                    continue

            send(text[:60], price, "brak linku", "ALLEGRO")
            sent += 1

            if sent >= 5:
                break

        except:
            continue

# =========================
# 🚀 START
# =========================
print("🚀 SNIPER START")

# 🎯 POKEMON
olx_search("pokemon", "pokemon")
vinted_search("pokemon")
allegro_local("pokemon")

# 🎮 KONSOLE
olx_search("psp", "psp")
olx_search("gameboy", "gameboy")
olx_search("nintendo 3ds", "3ds")

vinted_search("psp")
vinted_search("gameboy")
vinted_search("nintendo 3ds")

allegro_local("psp")
allegro_local("gameboy")
allegro_local("nintendo 3ds")