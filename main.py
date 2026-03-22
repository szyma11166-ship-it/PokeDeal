import requests
import time

# ========================
# ⚙️ KONFIG
# ========================

TOKEN = "TWÓJ_TOKEN"
CHAT_ID = "TWÓJ_CHAT_ID"

MAX_PRICE = 150  # 🔥 LIMIT

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

# ========================
# 🧠 FILTRY
# ========================

BAD_KEYWORDS = [
    "korea", "korean", "jp", "japan",
    "bulk", "mix", "losowe", "random",
    "100 kart", "200 kart", "500 kart",
    "common", "uncommon", "energy",
    "fake", "replika"
]

GOOD_KEYWORDS = [
    "zestaw", "kolekcja", "pakiet", "lot",
    "psp", "gameboy", "3ds",
    "pokemon", "etb"
]

def is_price_ok(price):
    return price <= MAX_PRICE

def is_trash(title):
    t = title.lower()
    return any(b in t for b in BAD_KEYWORDS)

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
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        data = {
            "chat_id": CHAT_ID,
            "text": text,
            "disable_web_page_preview": False
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("❌ Telegram error:", e)

# ========================
# 🧾 FORMAT
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
# 🛡 SAFE JSON
# ========================

def safe_json(res):
    try:
        return res.json()
    except:
        return None

# ========================
# 🟢 OLX
# ========================

def fetch_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}"
        res = requests.get(url, headers=HEADERS, timeout=10)

        data = safe_json(res)
        if not data:
            return []

        items = []

        for ad in data.get("data", []):
            try:
                items.append({
                    "title": ad["title"],
                    "price": float(ad["price"]["value"]),
                    "url": ad["url"]
                })
            except:
                continue

        return items

    except Exception as e:
        print("❌ OLX error:", e)
        return []

# ========================
# 🟠 ALLEGRO (NAPRAWIONE)
# ========================

def fetch_allegro():
    url = "https://allegrolokalnie.pl/api/offers"

    try:
        res = requests.get(url, headers=HEADERS, timeout=10)

        if res.status_code != 200:
            print("❌ Allegro status:", res.status_code)
            return []

        data = safe_json(res)
        if not data:
            print("❌ Allegro blokuje (brak JSON)")
            return []

        items = []

        for ad in data.get("items", []):
            try:
                items.append({
                    "title": ad["name"],
                    "price": float(ad["sellingMode"]["price"]["amount"]),
                    "url": ad.get("url", "brak linku")
                })
            except:
                continue

        return items

    except Exception as e:
        print("❌ Allegro error:", e)
        return []

# ========================
# 🟣 VINTED
# ========================

def fetch_vinted():
    try:
        url = "https://www.vinted.pl/api/v2/catalog/items"
        res = requests.get(url, headers=HEADERS, timeout=10)

        data = safe_json(res)
        if not data:
            return []

        items = []

        for ad in data.get("items", []):
            try:
                items.append({
                    "title": ad["title"],
                    "price": float(ad["price"]),
                    "url": ad["url"]
                })
            except:
                continue

        return items

    except Exception as e:
        print("❌ Vinted error:", e)
        return []

# ========================
# 🔁 LOOP
# ========================

def run_bot():
    print("🚀 FINAL SNIPER BOT v3.1 START")

    while True:
        try:
            all_items = []

            # OLX
            print("🟢 OLX...")
            for q in ["psp", "gameboy", "3ds", "pokemon"]:
                items = fetch_olx(q)
                all_items += [(i, "OLX") for i in items]

            # ALLEGRO
            print("🟠 ALLEGRO...")
            allegro_items = fetch_allegro()
            if allegro_items:
                all_items += [(i, "ALLEGRO") for i in allegro_items]

            # VINTED
            print("🟣 VINTED...")
            vinted_items = fetch_vinted()
            if vinted_items:
                all_items += [(i, "VINTED") for i in vinted_items]

            # FILTER + SEND
            for item, source in all_items:
                if should_send(item):
                    msg = format_msg(item, source)
                    send_telegram(msg)

            time.sleep(60)

        except Exception as e:
            print("❌ LOOP ERROR:", e)
            time.sleep(10)

# ========================
# ▶️ START
# ========================

if __name__ == "__main__":
    run_bot()