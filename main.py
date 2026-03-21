import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

# =========================
# BLACKLIST (EDYTUJ)
# =========================
blacklist = [
    "etui",
    "case",
    "pokrowiec",
    "naklejka",
    "folia",
    "szkło",
    "uszkodz",
    "części",
    "na części",
    "pudełko",
    "box empty"
]

# =========================
# SEND
# =========================
def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })

# =========================
# PRICE
# =========================
def extract_price(text):
    try:
        text = text.replace(",", ".")
        price = float(re.findall(r"\d+\.\d+|\d+", text)[0])
        return price
    except:
        return None

# =========================
# DUPLIKATY
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

# =========================
# BLACKLIST CHECK
# =========================
def is_blacklisted(name):
    name = name.lower()
    return any(word in name for word in blacklist)

# =========================
# POKEMON
# =========================
def is_pokemon(name):
    return "pokemon" in name or "pokémon" in name

def is_pokemon_deal(name, price):
    name = name.lower()

    if "elite trainer box" in name and price and price < 300:
        return "🟣 ETB"

    if ("booster box" in name or "display" in name) and price and price < 200:
        return "🟣 BOOSTER BOX"

    if "booster" in name and "box" not in name and price and price < 25:
        return "🟣 BOOSTER"

    if "tin" in name and price and price < 100:
        return "🟣 TIN"

    if "ultra premium" in name and price and price < 600:
        return "🟣 ULTRA PREMIUM"

    return None

# =========================
# MARKET PRICE
# =========================
def get_market_price(name):
    try:
        short_name = " ".join(name.split()[:5])

        url = f"https://allegro.pl/listing?string={short_name.replace(' ', '%20')}"
        headers = {"User-Agent": "Mozilla/5.0"}

        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        prices = []

        for item in soup.find_all("article")[:6]:
            text = item.get_text().replace(",", ".")
            p = re.findall(r"\d+\.\d+|\d+", text)
            if p:
                val = float(p[0])
                if val > 10:
                    prices.append(val)

        if len(prices) >= 3:
            return sum(prices) / len(prices)

    except:
        return None

    return None

# =========================
# OCENA OKAZJI ⭐
# =========================
def rate_deal(price, market):
    if not market:
        return "⚪ brak danych"

    ratio = price / market

    if ratio < 0.4:
        return "🔥🔥🔥 MEGA FLIP"
    elif ratio < 0.5:
        return "🔥🔥 DOBRA OKAZJA"
    elif ratio < 0.6:
        return "🔥 OKAZJA"
    else:
        return None

# =========================
# OGÓLNE OKAZJE
# =========================
def is_general_deal(name, price):
    if not price:
        return None, None

    market = get_market_price(name)

    if market:
        rating = rate_deal(price, market)

        if rating:
            discount = int((1 - price/market) * 100)
            return f"{rating} (-{discount}%)", market

    return None, None

# =========================
# ALLEGRO
# =========================
def check_allegro():
    url = "https://allegro.pl/listing?string=pokemon%20lego%20ps5%20xbox"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("article")

    for item in items:
        try:
            text = item.get_text().lower()
            link = "https://allegro.pl" + item.find("a")["href"]

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)

            # POKEMON
            if is_pokemon(text):
                deal = is_pokemon_deal(text, price)

                if deal:
                    send(f"""
🟣 POKEMON OKAZJA

📦 {text[:80]}
💸 {price} zł
🔗 {link}
""")

            # INNE
            else:
                deal, market = is_general_deal(text, price)

                if deal:
                    send(f"""
{deal}

📦 {text[:80]}

💸 {price} zł
📊 ~{int(market)} zł

🔗 {link}
""")

        except:
            continue

# =========================
# OLX
# =========================
def check_olx():
    url = "https://www.olx.pl/oferty/q-ps5/"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("div", {"data-cy": "l-card"})

    for item in items:
        try:
            text = item.get_text().lower()
            link = item.find("a")["href"]

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)

            if is_pokemon(text):
                deal = is_pokemon_deal(text, price)

                if deal:
                    send(f"🟣 OLX POKEMON\n{text[:80]}\n💸 {price}\n{link}")

            else:
                deal, market = is_general_deal(text, price)

                if deal:
                    send(f"{deal}\n{text[:80]}\n💸 {price}\n📊 ~{int(market)} zł\n{link}")

        except:
            continue

# =========================
# START
# =========================
print("🚀 BOT ULTRA START")
send("🚀 BOT ULTRA DZIAŁA")

while True:
    check_allegro()
    time.sleep(15)

    check_olx()
    time.sleep(30)