import requests
import time

# ========================
# ⚙️ KONFIG
# ========================

TOKEN = "TWÓJ_TOKEN_TELEGRAM"
CHAT_ID = "TWÓJ_CHAT_ID"

MAX_PRICE = 150  # 🔥 TWÓJ LIMIT

# ========================
# 🧠 FILTRY
# ========================

BAD_KEYWORDS = [
    "korea", "korean", "jp", "japan", "chiń",
    "bulk", "mix", "losowe", "random",
    "100 kart", "200 kart", "500 kart", "1000 kart",
    "common", "uncommon", "energy",
    "fake", "replika"
]

GOOD_KEYWORDS = [
    "zestaw", "kolekcja", "pakiet", "lot",
    "psp", "gameboy", "3ds",
    "pokemon", "etb", "elite trainer"
]

def is_price_ok(price):
    return price <= MAX_PRICE

def is_trash(title):
    t = title.lower()
    return any(bad in t for bad in BAD_KEYWORDS)

def is_good(title):
    t = title.lower()
    return any(g in t for g in GOOD_KEYWORDS)

def estimate_price(title, price):
    t = title.lower()

    if "zestaw" in t or "lot" in t:
        return price * 1.4
    if "gameboy" in t or "psp" in t:
        return price * 1.3
    if "pokemon" in t:
        return price * 1.25

    return price * 1.2

def should_send(item):
    title = item["title"]
    price = item["price"]

    if not is_price_ok(price):
        return False

    if is_trash(title):
        return False

    if not is_good(title):
        return False

    return True

# ========================
# 📤 TELEGRAM
# ========================

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": False
    }
    requests.post(url, data=data)

# ========================
# 🧾 FORMAT WIADOMOŚCI
# ========================

def format_msg(item, source):
    title = item["title"]
    price = item["price"]
    link = item.get("url", "brak linku")

    est = estimate_price(title, price)
    profit = int(est - price)

    return f"""🔥 OKAZJA

📦 {title}

💰 {price} zł
📊 ~{int(est)} zł
📈 +{profit} zł

🔗 {link}
📍 {source}
"""

# ========================
# 🟢 OLX SCRAPER
# ========================

def fetch_olx(query):
    url = f"https://www.olx.pl/api/v1/offers/?query={query}"
    res = requests.get(url).json()

    items = []

    for ad in res.get("data", []):
        try:
            items.append({
                "title": ad["title"],
                "price": float(ad["price"]["value"]),
                "url": ad["url"]
            })
        except:
            continue

    return items

# ========================
# 🟠 ALLEGRO LOKALNIE
# ========================

def fetch_allegro():
    url = "https://allegrolokalnie.pl/api/offers"
    res = requests.get(url).json()

    items = []

    for ad in res.get("items", []):
        try:
            items.append({
                "title": ad["name"],
                "price": float(ad["sellingMode"]["price"]["amount"]),
                "url": ad["url"]
            })
        except:
            continue

    return items

# ========================
# 🟣 VINTED (PROSTE)
# ========================

def fetch_vinted():
    url = "https://www.vinted.pl/api/v2/catalog/items"
    res = requests.get(url).json()

    items = []

    for ad in res.get("items", []):
        try:
            items.append({
                "title": ad["title"],
                "price": float(ad["price"]),
                "url": ad["url"]
            })
        except:
            continue

    return items

# ========================
# 🔁 BOT LOOP
# ========================

def run_bot():
    print("🚀 FINAL SNIPER BOT v3 START")

    while True:
        try:
            all_items = []

            # OLX
            print("🟢 OLX...")
            all_items += [(i, "OLX") for i in fetch_olx("psp")]
            all_items += [(i, "OLX") for i in fetch_olx("gameboy")]
            all_items += [(i, "OLX") for i in fetch_olx("3ds")]
            all_items += [(i, "OLX") for i in fetch_olx("pokemon")]

            # ALLEGRO
            print("🟠 ALLEGRO...")
            all_items += [(i, "ALLEGRO") for i in fetch_allegro()]

            # VINTED
            print("🟣 VINTED...")
            all_items += [(i, "VINTED") for i in fetch_vinted()]

            for item, source in all_items:
                if should_send(item):
                    msg = format_msg(item, source)
                    send_telegram(msg)

            time.sleep(60)

        except Exception as e:
            print("❌ ERROR:", e)
            time.sleep(10)

# ========================
# ▶️ START
# ========================

if __name__ == "__main__":
    run_bot()