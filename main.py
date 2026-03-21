import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

# =========================
# BLACKLIST
# =========================
blacklist = [
    "etui", "case", "pokrowiec", "naklejka", "folia",
    "szkło", "uszkodz", "części", "na części",
    "pudełko", "box empty",
    "obserwuj", "zamienię", "za darmo",
    "gratis", "oddam", "rezerwacja"
]

# =========================
# SEND (ładny format)
# =========================
def send(title, price, link, tag, market=None):
    msg = f"{tag}\n\n📦 {title}\n"

    if price:
        msg += f"💸 {price} zł\n"

    if market:
        msg += f"📊 ~{int(market)} zł\n"

    msg += f"\n🔗 {link}"

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
        prices = re.findall(r"\d+\.\d+|\d+", text)

        for p in prices:
            val = float(p)
            if val > 20:  # 🔥 filtr śmieci
                return val

        return None
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
# BLACKLIST
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

    if "elite trainer box" in name and price < 300:
        return "🟣 POKEMON • ETB"

    if ("booster box" in name or "display" in name) and price < 200:
        return "🟣 POKEMON • BOOSTER BOX"

    if "booster" in name and "box" not in name and price < 25:
        return "🟣 POKEMON • BOOSTER"

    if "tin" in name and price < 100:
        return "🟣 POKEMON • TIN"

    if "ultra premium" in name and price < 600:
        return "🟣 POKEMON • ULTRA PREMIUM"

    if "pokemon day" in name and price < 70:
        return "🟣 POKEMON • DAY"

    if "first partner" in name and price < 120:
        return "🟣 POKEMON • FIRST PARTNER"

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
                if val > 20:
                    prices.append(val)

        if len(prices) >= 3:
            return sum(prices) / len(prices)

    except:
        return None

    return None

# =========================
# OCENA
# =========================
def rate_deal(price, market):
    if not market:
        return None

    ratio = price / market

    if ratio < 0.5:
        return "🔥🔥🔥 MEGA FLIP"
    elif ratio < 0.65:
        return "🔥🔥 DOBRA OKAZJA"
    elif ratio < 0.75:
        return "🔥 OKAZJA"

    return None

# =========================
# OGÓLNE OKAZJE
# =========================
def is_general_deal(name, price):
    market = get_market_price(name)

    if market:
        rating = rate_deal(price, market)
        if rating:
            return rating, market

    if price < 150:
        return "💰 TANIE", price

    return None, None

# =========================
# ALLEGRO
# =========================
def check_allegro():
    url = "https://allegro.pl/listing?string=pokemon%20lego%20ps5%20xbox"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("article"):
        try:
            text = item.get_text().lower()
            link = "https://allegro.pl" + item.find("a")["href"]

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            # POKEMON
            if is_pokemon(text):
                tag = is_pokemon_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag)

            # INNE
            else:
                tag, market = is_general_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, market)

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

    for item in soup.find_all("div", {"data-cy": "l-card"}):
        try:
            text = item.get_text().lower()
            link = item.find("a")["href"]

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            if is_pokemon(text):
                tag = is_pokemon_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag)

            else:
                tag, market = is_general_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, market)

        except:
            continue

# =========================
# START
# =========================
print("🚀 BOT START")
send("BOT DZIAŁA", "", "", "🚀 START")

while True:
    check_allegro()
    time.sleep(15)

    check_olx()
    time.sleep(30)