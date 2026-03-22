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
# BLACKLIST
# =========================
blacklist = [
    "album", "plusz", "figurka", "zabawka",
    "funko", "lego", "maskotka",
    "bulk", "mix", "losowe",
    "pojedyncza", "single", "karta", "karty",
]

bad_languages = [
    "japo", "jp", "german", "niem", "de",
    "french", "fr", "italian", "it"
]

# =========================
# SEND
# =========================
def send(title, price, link, tag, shop):
    msg = f"""
{tag} • {shop}

📦 {title}

💸 {price if price else 'brak'} zł

🔗 {link}
"""
    print("📤", shop, "|", title[:60])

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

def is_bad(name):
    name = name.lower()
    return any(w in name for w in blacklist) or any(l in name for l in bad_languages)

def is_real(name):
    name = name.lower()
    return any(k in name for k in [
        "booster",
        "elite trainer box",
        "etb",
        "booster bundle",
        "ultra premium",
        "collection"
    ])

# =========================
# LEVELS
# =========================
def get_level(name, price):
    name = name.lower()

    if price:
        if "elite trainer box" in name and price < 280:
            return "🔥🔥🔥 ETB FLIP"
        if "booster bundle" in name and price < 110:
            return "🔥🔥 BUNDLE"
        if "booster" in name and "box" not in name and price < 22:
            return "🔥 BOOSTER"
        if "ultra premium" in name and price < 550:
            return "🔥🔥🔥 PREMIUM"

    return None

# =========================
# OLX
# =========================
def check_olx():
    print("\n🟢 OLX...")

    url = "https://www.olx.pl/oferty/q-pokemon/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.find_all("div", {"data-cy": "l-card"}):
        try:
            text = item.get_text().lower()
            link = item.find("a")["href"]

            if not link.startswith("http"):
                link = "https://www.olx.pl" + link

            if not is_new(link):
                continue

            if is_bad(text):
                continue

            if not is_real(text):
                continue

            price = extract_price(text)
            tag = get_level(text, price)

            if tag:
                send(text[:80], price, link, tag, "OLX")

        except:
            continue

# =========================
# VINTED
# =========================
def check_vinted():
    print("\n🟣 VINTED...")

    url = "https://www.vinted.pl/catalog?search_text=pokemon"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for a in soup.find_all("a", href=True):
        try:
            text = a.get_text().lower()

            if "pokemon" not in text:
                continue

            link = a["href"]
            if not link.startswith("http"):
                link = "https://www.vinted.pl" + link

            if not is_new(link):
                continue

            if is_bad(text):
                continue

            if not is_real(text):
                continue

            price = extract_price(text)
            tag = get_level(text, price)

            if tag:
                send(text[:80], price, link, tag, "Vinted")

        except:
            continue

# =========================
# AMAZON
# =========================
def check_amazon():
    print("\n🟡 AMAZON...")

    url = "https://www.amazon.pl/s?k=pokemon+tcg+booster"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for item in soup.select("div[data-component-type='s-search-result']"):
        try:
            text = item.get_text().lower()
            link = "https://amazon.pl" + item.find("a")["href"]

            if not is_new(link):
                continue

            if is_bad(text):
                continue

            if not is_real(text):
                continue

            price = extract_price(text)
            tag = get_level(text, price)

            if tag:
                send(text[:80], price, link, tag, "Amazon")

        except:
            continue

# =========================
# SKLEPY
# =========================
shops = {
    "Rebel": "https://www.rebel.pl",
    "LootQuest": "https://lootquest.pl",
    "Strefa Kart": "https://strefakart.pl",
    "Strefa TCG": "https://strefa-tcg.pl",
    "Kanto Drop": "https://kantodrop.pl",
    "Świat Kart": "https://swiatkart.com.pl",
    "Skład Gier": "https://skladgier.pl"
}

def check_shops():
    print("\n🏪 SKLEPY...")

    for name, url in shops.items():
        try:
            r = requests.get(url, headers=HEADERS)
            soup = BeautifulSoup(r.text, "html.parser")

            for a in soup.find_all("a", href=True):
                text = a.get_text().lower()

                if "pokemon" not in text:
                    continue

                link = a["href"]
                if not link.startswith("http"):
                    link = url + link

                # pomijamy kategorie
                if "product" not in link and "produkt" not in link:
                    continue

                if not is_new(link):
                    continue

                if is_bad(text):
                    continue

                if not is_real(text):
                    continue

                price = extract_price(text)
                tag = get_level(text, price)

                if tag:
                    send(text[:80], price, link, tag, name)

        except:
            continue

# =========================
# START
# =========================
print("🚀 FULL BOT (ALL SOURCES)")
send("BOT START", 0, "", "🚀 SYSTEM", "BOT")

while True:
    check_olx()
    time.sleep(15)

    check_vinted()
    time.sleep(20)

    check_amazon()
    time.sleep(25)

    check_shops()
    time.sleep(40)