import requests
from bs4 import BeautifulSoup
import re
import os

# =========================
# 🔐 TELEGRAM
# =========================
TOKEN = os.getenv("TOKEN")
CHAT_ID = "-1003743099672"  # 🔥 NA STAŁE

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# ⚙️ LIMITY
# =========================
MAX_SEND = 6
sent_count = 0

MAX_PRICE_CONSOLE = 400


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
# OGÓLNE FILTRY
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części",
        "obudow", "za sztuk", "każda",
        "1 szt", "pojedyncz", "etui",
        "ładowark", "kabel", "adapter",
        "bez gry", "brak gry",
        "nie działa", "do naprawy",
        "konto", "psn", "steam"
    ]

    return not any(b in t for b in banned)


# =========================
# 🔥 POKEMON FILTER
# =========================
def is_good_pokemon(title):
    t = clean(title)

    bad = [
        "bulk", "losowe", "random", "mix",
        "common", "uncommon",
        "pojedyncza", "single", "1 karta",
        "proxy", "fake",

        "korea", "korean",
        "japan", "japanese",
        "deutsch", "german", "de ",
        "franc", "french", "fr ",
        "ital", "italian", "it "
    ]

    if any(b in t for b in bad):
        return False

    good = [
        "elite trainer box",
        "etb",
        "booster",
        "bundle",
        "illustration",
        "first partner",
        "pokemon day 2026"
    ]

    return any(g in t for g in good)


# =========================
# 💰 LIMITY POKEMON
# =========================
def get_pokemon_limit(title):
    t = clean(title)

    if "first partner" in t:
        return 150

    if "pokemon day 2026" in t:
        return 70

    if "booster" in t:
        return 25

    if "elite trainer box" in t or "etb" in t:
        return 300

    if "bundle" in t:
        return 200

    if "illustration" in t:
        return 150

    return 120


# =========================
# 📤 SEND
# =========================
def send(title, price, link, source, is_pokemon=False):
    global sent_count

    if sent_count >= MAX_SEND:
        return

    if is_pokemon:
        limit = get_pokemon_limit(title)
        if price > limit:
            return
    else:
        if price > MAX_PRICE_CONSOLE:
            return

    msg = f"""🔥 OKAZJA

📦 {title[:80]}

💰 {price} zł
📍 {source}

🔗 {link}
"""

    print(msg)
    send_telegram(msg)

    sent_count += 1


# =========================
# 🟢 OLX
# =========================
def olx_search(query, label, is_pokemon=False):
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

            if is_pokemon and not is_good_pokemon(title):
                continue

            send(title, price, link, f"OLX {label}", is_pokemon)

        except:
            continue


# =========================
# 🟣 VINTED
# =========================
def vinted_search(query, is_pokemon=False):
    print(f"\n🟣 VINTED {query}...")

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

            if is_pokemon and not is_good_pokemon(text):
                continue

            send(text[:80], price, "brak linku", f"VINTED {query}", is_pokemon)

        except:
            continue


# =========================
# 🟠 ALLEGRO LOKALNIE
# =========================
def allegro_local(query, is_pokemon=False):
    print(f"\n🟠 ALLEGRO LOKALNIE {query}...")

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

            if is_pokemon and not is_good_pokemon(title):
                continue

            send(title[:80], price, "brak linku", f"ALLEGRO LOKALNE {query}", is_pokemon)

        except:
            continue


# =========================
# 🚀 START
# =========================
print("🚀 FINAL SNIPER BOT v5")
print("📤 START")

# 🎯 POKEMON
olx_search("pokemon", "POKEMON", True)
vinted_search("pokemon", True)
allegro_local("pokemon", True)

# 🎮 KONSOLE
olx_search("psp", "PSP")
olx_search("nintendo 3ds", "3DS")
olx_search("gameboy", "GAMEBOY")

vinted_search("psp")
vinted_search("nintendo 3ds")
vinted_search("gameboy")

allegro_local("psp")
allegro_local("nintendo 3ds")
allegro_local("gameboy")

print(f"\n📤 WYSŁANO: {sent_count}")