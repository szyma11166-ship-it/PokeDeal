import requests
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
def send(title, price, link, tag):
    msg = f"{tag} • Allegro\n\n📦 {title}\n💸 {price} zł\n\n🔗 {link}"

    print("📤 WYSYŁAM:", title[:60])

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

def is_blacklisted(name):
    return any(word in name.lower() for word in blacklist)

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
# ALLEGRO API
# =========================
def check_allegro():
    print("\n🟡 ALLEGRO API...")

    url = "https://api.allegro.pl/offers/listing?phrase=pokemon&limit=20"

    headers = {
        "Accept": "application/vnd.allegro.public.v1+json",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers)
        data = r.json()

        items = data.get("items", {}).get("regular", [])
        print("📦 ZNALEZIONO:", len(items))

        for item in items:
            try:
                title = item["name"]
                link = item["url"]
                price = float(item["sellingMode"]["price"]["amount"])

                print("💸", price, "|", title[:50])

                if not is_new(link):
                    continue

                if is_blacklisted(title):
                    continue

                if price < 20:
                    continue

                tag = is_pokemon_deal(title, price)

                if tag:
                    send(title, price, link, tag)

            except:
                continue

    except:
        print("❌ API ERROR")

# =========================
# START
# =========================
print("🚀 ALLEGRO API BOT START")
send("START", 0, "", "🚀 SYSTEM")

while True:
    check_allegro()
    time.sleep(30)