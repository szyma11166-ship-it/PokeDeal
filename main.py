import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# SEND (ŁADNIEJSZY)
# =========================
def send(title, price, link, tag, shop):
    msg = f"""
{tag} • {shop}

📦 {title}

💸 {price} zł

🔗 {link}
"""

    print("📤", title[:60], "|", price)

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# =========================
# FILTER
# =========================
def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

def extract_price(text):
    text = text.replace(",", ".")
    prices = re.findall(r"\d+\.\d+|\d+", text)

    for p in prices:
        val = float(p)
        if val > 20:
            return val

    return None

# =========================
# POKEMON DEAL
# =========================
def is_pokemon_deal(name, price):
    name = name.lower()

    if "elite trainer box" in name and price < 320:
        return "🟣 ETB"
    if "booster bundle" in name and price < 140:
        return "🟣 BOOSTER BUNDLE"
    if "booster" in name and "box" not in name and price < 30:
        return "🟣 BOOSTER"
    if "ultra premium" in name and price < 650:
        return "🟣 ULTRA PREMIUM"

    return None

# =========================
# FALLBACK (WAŻNE)
# =========================
def fallback(name, price):
    name = name.lower()

    if "pokemon" in name and price < 80:
        return "🟡 TANIE POKEMON"

    return None

# =========================
# OLX
# =========================
def check_olx():
    print("\n🟢 OLX...")

    url = "https://www.olx.pl/oferty/q-pokemon/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.find_all("div", {"data-cy": "l-card"})
    print("📦", len(items))

    for item in items:
        try:
            text = item.get_text().lower()
            link = item.find("a")["href"]

            if not is_new(link):
                continue

            price = extract_price(text)
            if not price:
                continue

            tag = is_pokemon_deal(text, price)

            if tag:
                send(text[:80], price, link, tag, "OLX")
                continue

            # fallback
            tag = fallback(text, price)
            if tag:
                send(text[:80], price, link, tag, "OLX")

        except:
            continue

# =========================
# AMAZON
# =========================
def check_amazon():
    print("\n🟡 AMAZON...")

    url = "https://www.amazon.pl/s?k=pokemon"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-component-type='s-search-result']")
    print("📦", len(items))

    for item in items:
        try:
            text = item.get_text().lower()
            link = "https://amazon.pl" + item.find("a")["href"]

            if not is_new(link):
                continue

            price = extract_price(text)
            if not price:
                continue

            tag = is_pokemon_deal(text, price)

            if tag:
                send(text[:80], price, link, tag, "Amazon")
                continue

            tag = fallback(text, price)
            if tag:
                send(text[:80], price, link, tag, "Amazon")

        except:
            continue

# =========================
# START
# =========================
print("🚀 FINAL BOT START")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    check_olx()
    time.sleep(20)

    check_amazon()
    time.sleep(40)