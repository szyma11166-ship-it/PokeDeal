import requests
import time

# ========================
# ⚙️ KONFIG
# ========================

TOKEN = "TWÓJ_TOKEN"
CHAT_ID = "TWÓJ_CHAT_ID"

MAX_PRICE = 150  # 🔥 LIMIT CENY

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ========================
# 🧠 FILTRY (TYLKO KONKRET)
# ========================

BAD_KEYWORDS = [
    "korea", "korean", "jp", "japan",
    "bulk", "mix", "losowe", "random",
    "100 kart", "200 kart", "500 kart",
    "common", "uncommon", "energy",
    "fake", "replika",
    "uszkodz", "na części", "części",
    "etui", "ładowarka", "kabel"
]

def is_trash(title):
    t = title.lower()
    return any(b in t for b in BAD_KEYWORDS)

def should_send(item):
    title = item["title"]
    price = item["price"]

    # 🔥 twardy limit
    if price > MAX_PRICE:
        return False

    # 🔥 wywal śmieci
    if is_trash(title):
        return False

    return True

# ========================
# 📤 TELEGRAM
# ========================

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text
        }, timeout=10)
    except Exception as e:
        print("❌ Telegram error:", e)

# ========================
# 🧾 FORMAT
# ========================

def format_msg(item, source):
    return f"""🔥 OKAZJA

📦 {item['title']}

💰 {item['price']} zł

🔗 {item['url']}
📍 {source}
"""

# ========================
# 🟢 OLX
# ========================

def fetch_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}"
        res = requests.get(url, headers=HEADERS, timeout=10)

        try:
            data = res.json()
        except:
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
# 🟣 VINTED
# ========================

def fetch_vinted():
    try:
        url = "https://www.vinted.pl/api/v2/catalog/items"
        res = requests.get(url, headers=HEADERS, timeout=10)

        try:
            data = res.json()
        except:
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
    print("🚀 FINAL SNIPER BOT v3.2 START")
    send_telegram("🚀 BOT START")

    while True:
        try:
            all_items = []

            print("🟢 OLX...")
            for q in ["psp", "gameboy", "3ds", "pokemon"]:
                all_items += [(i, "OLX") for i in fetch_olx(q)]

            print("🟣 VINTED...")
            all_items += [(i, "VINTED") for i in fetch_vinted()]

            print(f"📦 TOTAL: {len(all_items)}")

            sent = 0

            for item, source in all_items:
                print(f"👉 {item['title']} | {item['price']}")

                if should_send(item):
                    print("✅ WYSYŁAM")
                    send_telegram(format_msg(item, source))
                    sent += 1
                else:
                    print("❌ ODRZUCONE")

            print(f"📤 WYSŁANO: {sent}")

            time.sleep(60)

        except Exception as e:
            print("❌ LOOP ERROR:", e)
            time.sleep(10)

# ========================
# ▶️ START
# ========================

if __name__ == "__main__":
    run_bot()