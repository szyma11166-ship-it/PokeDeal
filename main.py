import requests
from bs4 import BeautifulSoup
import time
import re

# ========================
# ⚙️ KONFIG
# ========================

TOKEN = "TWÓJ_TOKEN"
CHAT_ID = "TWÓJ_CHAT_ID"

MAX_PRICE = 150

seen_links = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ========================
# ❌ BLACKLIST
# ========================

BAD_KEYWORDS = [
    "korea", "korean", "jp", "japan",
    "bulk", "mix", "losowe", "random",
    "100 kart", "200 kart", "500 kart",
    "common", "uncommon", "energy",
    "fake", "replika",
    "uszkodz", "na części", "części",
    "etui", "ładowarka", "kabel",
    "zamienię", "za darmo"
]

def is_trash(title):
    t = title.lower()
    return any(b in t for b in BAD_KEYWORDS)

# ========================
# 💸 PRICE
# ========================

def extract_price(text):
    try:
        text = text.replace(",", ".")
        prices = re.findall(r"\d+\.\d+|\d+", text)

        for p in prices:
            val = float(p)
            if 5 < val < 10000:
                return val
    except:
        return None

    return None

# ========================
# 🆕 NEW FILTER
# ========================

def is_new(link):
    if link in seen_links:
        return False
    seen_links.add(link)
    return True

# ========================
# 📤 TELEGRAM
# ========================

def send(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        }, timeout=10)
    except Exception as e:
        print("❌ Telegram error:", e)

# ========================
# 🧾 FORMAT
# ========================

def format_msg(title, price, link):
    return f"""🔥 OKAZJA

📦 {title[:100]}

💰 {price} zł

🔗 {link}
"""

# ========================
# 🟢 OLX (HTML – DZIAŁA)
# ========================

def check_olx(query):
    print(f"🟢 OLX {query}...")

    url = f"https://www.olx.pl/oferty/q-{query}/"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        items = soup.select("div[data-cy='l-card']")
        print(f"📦 ZNALEZIONO: {len(items)}")

        sent = 0

        for item in items:
            try:
                text = item.get_text(" ").lower()
                a_tag = item.find("a")

                if not a_tag:
                    continue

                link = a_tag["href"]

                if not link.startswith("http"):
                    link = "https://www.olx.pl" + link

                if not is_new(link):
                    continue

                if is_trash(text):
                    continue

                price = extract_price(text)
                if not price:
                    continue

                if price > MAX_PRICE:
                    continue

                msg = format_msg(text, price, link)
                send(msg)

                sent += 1

            except:
                continue

        print(f"📤 WYSŁANO: {sent}")

    except Exception as e:
        print("❌ OLX error:", e)

# ========================
# ▶️ START
# ========================

print("🚀 FINAL STABLE BOT START")
send("🚀 BOT START")

while True:
    check_olx("pokemon")
    time.sleep(15)

    check_olx("psp")
    time.sleep(15)

    check_olx("gameboy")
    time.sleep(15)

    check_olx("3ds")
    time.sleep(30)