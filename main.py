import requests
from bs4 import BeautifulSoup
import re
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = -1003743099672

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
# POKEMON FILTER
# =========================
def pokemon_filter(title, price):
    t = clean(title)

    if "booster" in t:
        return price <= 20

    if "etb" in t:
        return price <= 300

    if "first partner" in t:
        return price <= 150

    if "pokemon day 2026" in t:
        return price <= 70

    if "illustration" in t:
        return price <= 200

    return False


# =========================
# CONSOLE FILTER
# =========================
def console_filter(query, price):
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

    r = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })

    print("📨", r.status_code, r.text)


# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")

    count = 0

    for item in items:
        if count >= 5:
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
                if not pokemon_filter(title, price):
                    continue
            else:
                if not console_filter(query, price):
                    continue

            send(title, price, link, "OLX")
            count += 1

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

    count = 0

    for item in items:
        if count >= 5:
            break

        try:
            text = item.get_text()
            a = item.select_one("a")

            if not a:
                continue

            link = "https://www.vinted.pl" + a["href"]
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(text, price):
                    continue
            else:
                if not console_filter(query, price):
                    continue

            send(text, price, link, "VINTED")
            count += 1

        except:
            continue


# =========================
# ALLEGRO LOKALNE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    count = 0

    for item in items:
        if count >= 5:
            break

        try:
            title = item.get_text()
            a = item.select_one("a")

            if not a:
                continue

            link = "https://allegrolokalnie.pl" + a["href"]
            price = get_price(title)

            if not price:
                continue

            if not is_valid(title):
                continue

            if "pokemon" in query:
                if not pokemon_filter(title, price):
                    continue
            else:
                if not console_filter(query, price):
                    continue

            send(title, price, link, "ALLEGRO")
            count += 1

        except:
            continue


# =========================
# START
# =========================
print("🚀 SNIPER START")

# POKEMON
olx_search("pokemon")
vinted_search("pokemon")
allegro_local("pokemon")

# KONSOLE
olx_search("psp")
vinted_search("psp")
allegro_local("psp")

olx_search("nintendo 3ds")
vinted_search("nintendo 3ds")
allegro_local("nintendo 3ds")

olx_search("gameboy")
vinted_search("gameboy")
allegro_local("gameboy")