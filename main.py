import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

# =========================
# HEADERS (FIX ALLEGRO)
# =========================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
    "Connection": "keep-alive"
}

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

    print("📤 WYSYŁAM:", msg[:100])

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

        r = requests.get(url, headers=HEADERS)
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
            avg = sum(prices)/len(prices)
            print("📊 MARKET:", avg)
            return avg

    except:
        print("❌ MARKET ERROR")
        return None

    return None

# =========================
# DEAL SCORE
# =========================
def rate_deal(price, market):
    if not market:
        return None

    ratio = price / market
    print(f"📉 RATIO: {ratio:.2f}")

    if ratio < 0.5:
        return "🔥🔥🔥 MEGA FLIP"
    elif ratio < 0.65:
        return "🔥🔥 DOBRA OKAZJA"
    elif ratio < 0.75:
        return "🔥 OKAZJA"

    return None

def is_general_deal(name, price):
    print("🔎 SPRAWDZAM:", name[:50], "|", price)

    market = get_market_price(name)

    if market:
        rating = rate_deal(price, market)
        if rating:
            print("✅ OKAZJA!")
            return rating, market

    if price < 150:
        print("💰 TANIE fallback")
        return "💰 TANIE", price

    print("❌ ODRZUCONE")
    return None, None

# =========================
# ALLEGRO (FIXED)
# =========================
def check_allegro():
    print("\n🟡 SPRAWDZAM ALLEGRO...")

    url = "https://allegro.pl/kategoria/gry-karciane-pokemon-260080"

    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("article")
    print("📦 ZNALEZIONO:", len(items))

    for item in items:
        try:
            text = item.get_text().lower()

            link_tag = item.find("a")
            if not link_tag:
                continue

            link = "https://allegro.pl" + link_tag["href"]

            price = extract_price(text)
            print("💸 CENA:", price)

            if not price:
                continue

            if is_blacklisted(text) or not is_new(link):
                continue

            tag = is_pokemon_deal(text, price)

            if tag:
                send(text[:80], price, link, tag, shop="Allegro")

        except:
            continue

# =========================
# START
# =========================
print("🚀 DEBUG BOT START")
send("DEBUG START", "", "", "🚀 SYSTEM")

while True:
    check_allegro()
    time.sleep(30)