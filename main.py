import requests
import time
import os
import xml.etree.ElementTree as ET
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "-1003743099672"

seen_links = set()

# =========================
# SEND
# =========================
def send(title, price, link, tag):
    msg = f"{tag} • Allegro\n\n📦 {title}\n💸 {price} zł\n\n🔗 {link}"

    print("📤", title[:60])

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
    except:
        return None

    return None

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
# ALLEGRO RSS (WORKING)
# =========================
def check_allegro():
    print("\n🟡 ALLEGRO RSS...")

    url = "https://allegro.pl/rss/oferty?q=pokemon"

    try:
        r = requests.get(url)
        root = ET.fromstring(r.content)

        items = root.findall(".//item")
        print("📦 ZNALEZIONO:", len(items))

        for item in items:
            try:
                title = item.find("title").text
                link = item.find("link").text
                desc = item.find("description").text

                if not is_new(link):
                    continue

                price = extract_price(desc)

                if not price:
                    continue

                tag = is_pokemon_deal(title, price)

                if tag:
                    send(title, price, link, tag)

            except:
                continue

    except:
        print("❌ RSS ERROR")

# =========================
# START
# =========================
print("🚀 RSS BOT START")
send("START", 0, "", "🚀 SYSTEM")

while True:
    check_allegro()
    time.sleep(60)