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
# BLACKLIST (AGRESYWNA)
# =========================
blacklist = [
    "album", "plusz", "figurka", "zabawka",
    "funko", "lego", "maskotka", "plush",
    "koszulka", "gra planszowa",
    "bulk", "mix", "losowe",
    "etui", "pudełko", "box empty",
    "uszkodz", "na części",
]

# =========================
# SEND (ŁADNY FORMAT)
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
# HELPERS
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

def is_blacklisted(name):
    name = name.lower()
    return any(word in name for word in blacklist)

# =========================
# TYLKO PRAWDZIWY POKEMON TCG
# =========================
def is_real_pokemon(name):
    name = name.lower()

    keywords = [
        "pokemon tcg",
        "booster",
        "elite trainer box",
        "etb",
        "booster bundle",
        "ultra premium",
        "collection"
    ]

    return any(k in name for k in keywords)

# =========================
# POZIOMY OKAZJI
# =========================
def get_level(name, price):
    name = name.lower()

    if "elite trainer box" in name and price < 280:
        return "🔥🔥🔥 ETB FLIP"

    if "booster bundle" in name and price < 110:
        return "🔥🔥 BOOSTER BUNDLE"

    if "booster" in name and "box" not in name and price < 22:
        return "🔥 BOOSTER"

    if "ultra premium" in name and price < 550:
        return "🔥🔥🔥 ULTRA PREMIUM"

    if price < 70:
        return "🟡 TANIE"

    return None

# =========================
# OLX (NAPRAWIONE)
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
            if not link.startswith("http"):
                link = "https://www.olx.pl" + link

            if not is_new(link):
                continue

            if is_blacklisted(text):
                continue

            if not is_real_pokemon(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            tag = get_level(text, price)

            if tag:
                send(text[:80], price, link, tag, "OLX")

        except:
            continue

# =========================
# AMAZON (OCZYSZCZONY)
# =========================
def check_amazon():
    print("\n🟡 AMAZON...")

    url = "https://www.amazon.pl/s?k=pokemon+tcg"
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

            if is_blacklisted(text):
                continue

            if not is_real_pokemon(text):
                continue

            price = extract_price(text)
            if not price:
                continue

            tag = get_level(text, price)

            if tag:
                send(text[:80], price, link, tag, "Amazon")

        except:
            continue

# =========================
# START
# =========================
print("🚀 FINAL CLEAN BOT START")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    check_olx()
    time.sleep(20)

    check_amazon()
    time.sleep(40)