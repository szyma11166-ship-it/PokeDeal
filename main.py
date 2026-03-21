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
# SEND
# =========================
def send(title, price, link, tag, market=None, shop=""):
    msg = f"{tag}"

    if shop:
        msg += f" • {shop}"

    msg += f"\n\n📦 {title}\n"

    if price:
        msg += f"💸 {price} zł\n"

    if market:
        msg += f"📊 ~{int(market)} zł\n"

    msg += f"\n🔗 {link}"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# =========================
# PRICE
# =========================
def extract_price(text):
    try:
        text = text.replace(",", ".")
        prices = re.findall(r"\d+\.\d+|\d+", text)

        for p in prices:
            val = float(p)
            if val > 20:
                return val

        return None
    except:
        return None

# =========================
# FILTERS
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

def is_blacklisted(name):
    name = name.lower()
    return any(word in name for word in blacklist)

def is_pokemon(name):
    return "pokemon" in name or "pokémon" in name

# =========================
# POKEMON DEALS
# =========================
def is_pokemon_deal(name, price):
    name = name.lower()

    if "elite trainer box" in name and price < 300:
        return "🟣 ETB"
    if "booster bundle" in name and price < 120:
        return "🟣 BOOSTER BUNDLE"
    if "booster" in name and "box" not in name and price < 25:
        return "🟣 BOOSTER"
    if "ultra premium" in name and price < 600:
        return "🟣 ULTRA PREMIUM"

    return None

# =========================
# MARKET
# =========================
def get_market_price(name):
    try:
        short = " ".join(name.split()[:5])
        url = f"https://allegro.pl/listing?string={short.replace(' ', '%20')}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        prices = []

        for item in soup.find_all("article")[:5]:
            text = item.get_text().replace(",", ".")
            p = re.findall(r"\d+\.\d+|\d+", text)
            if p:
                val = float(p[0])
                if val > 20:
                    prices.append(val)

        if len(prices) >= 3:
            return sum(prices)/len(prices)

    except:
        return None

    return None

# =========================
# DEAL SCORE
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
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("article"):
        try:
            text = item.get_text().lower()
            link = "https://allegro.pl" + item.find("a")["href"]

            if not is_new(link) or is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            if is_pokemon(text):
                tag = is_pokemon_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, shop="Allegro")
            else:
                tag, market = is_general_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, market, "Allegro")

        except:
            continue

# =========================
# OLX
# =========================
def check_olx():
    url = "https://www.olx.pl/oferty/q-ps5/"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("div", {"data-cy": "l-card"}):
        try:
            text = item.get_text().lower()
            link = item.find("a")["href"]

            if not is_new(link) or is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            tag, market = is_general_deal(text, price)
            if tag:
                send(text[:80], price, link, tag, market, "OLX")

        except:
            continue

# =========================
# AMAZON
# =========================
def check_amazon():
    url = "https://www.amazon.pl/s?k=pokemon+lego+ps5"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.select("div[data-component-type='s-search-result']"):
        try:
            text = item.get_text().lower()
            link = "https://amazon.pl" + item.find("a")["href"]

            if not is_new(link) or is_blacklisted(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            if is_pokemon(text):
                tag = is_pokemon_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, shop="Amazon")

        except:
            continue

# =========================
# POKEMON SKLEPY
# =========================
shops = {
    "Strefa Kart": "https://strefakart.pl",
    "LootQuest": "https://lootquest.pl",
    "Rebel": "https://www.rebel.pl",
    "Świat Kart": "https://swiatkart.com.pl",
    "Skład Gier": "https://skladgier.pl",
    "Kanto Drop": "https://kantodrop.pl",
    "Strefa TCG": "https://strefa-tcg.pl"
}

def check_pokemon_shops():
    for name, url in shops.items():
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a", href=True):
                text = a.get_text().lower()

                if not is_pokemon(text):
                    continue

                link = a["href"]
                if not link.startswith("http"):
                    link = url + link

                if not is_new(link):
                    continue

                price = extract_price(text)

                tag = is_pokemon_deal(text, price)
                if tag:
                    send(text[:80], price, link, tag, shop=name)

        except:
            continue

# =========================
# START
# =========================
print("🚀 BOT ALL-IN-ONE START")
send("BOT START", "", "", "🚀 SYSTEM")

while True:
    check_allegro()
    time.sleep(10)

    check_olx()
    time.sleep(15)

    check_amazon()
    time.sleep(15)

    check_pokemon_shops()
    time.sleep(30)