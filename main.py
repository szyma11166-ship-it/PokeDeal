import requests
from bs4 import BeautifulSoup
import re

# =========================
# 🔐 TELEGRAM
# =========================
TOKEN = "TU_WKLEJ_TOKEN"
CHAT_ID = "-1003743099672"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MAX_PRICE = 400   # 🔥 limit ceny
MAX_SEND = 5      # 🔥 max wysyłek na cykl
sent_count = 0


# =========================
# 🔧 CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# 💰 CENA
# =========================
def get_price(text):
    text = text.lower()

    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)

    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

    if not matches:
        return None

    prices = [float(m.replace(",", ".")) for m in matches]
    return min(prices)


# =========================
# 🚫 FILTRY
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części",
        "obudow", "za sztuk", "każda",
        "1 szt", "pojedyncz", "etui",
        "ładowark", "kabel", "adapter",
        "bez gry", "brak gry",
        "nie działa", "do naprawy"
    ]

    return not any(b in t for b in banned)


# =========================
# 📤 OUTPUT (TELEGRAM)
# =========================
def send(title, price, link, source):
    global sent_count

    if sent_count >= MAX_SEND:
        return

    if price > MAX_PRICE:
        return

    msg = f"""🔥 OKAZJA

📦 {title[:80]}

💰 {price} zł
📍 {source}

🔗 {link}
"""

    print(msg)
    send_telegram(msg)

    sent_count += 1


# =========================
# 🟢 OLX
# =========================
def olx_search(query, label):
    print(f"\n🟢 OLX {label}...")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)}")

    for item in items:
        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]

            price = get_price(item.get_text())

            if not price:
                continue

            if not is_valid(title):
                continue

            send(title, price, link, f"OLX {label}")

        except:
            continue


# =========================
# 🟣 VINTED
# =========================
def vinted_search(query):
    print("\n🟣 VINTED...")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print(f"📦 {len(items)}")

    for item in items:
        try:
            text = item.get_text()
            price = get_price(text)

            if not price:
                continue

            if not is_valid(text):
                continue

            send(text[:80], price, "brak linku", "VINTED")

        except:
            continue


# =========================
# 🟠 ALLEGRO
# =========================
def allegro_local(query):
    print("\n🟠 ALLEGRO...")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    print(f"📦 {len(items)}")

    for item in items:
        try:
            title = item.get_text()
            price = get_price(title)

            if not price:
                continue

            if not is_valid(title):
                continue

            send(title[:80], price, "brak linku", "ALLEGRO")

        except:
            continue


# =========================
# 🚀 START
# =========================
print("🚀 FINAL SNIPER BOT")
print("📤 START")

# ❌ USUNIĘTY POKEMON (spamował)

# ✅ TYLKO KONSOLE
olx_search("psp", "PSP")
olx_search("nintendo 3ds", "3DS")
olx_search("gameboy", "GAMEBOY")

vinted_search("psp")
vinted_search("nintendo 3ds")
vinted_search("gameboy")

allegro_local("psp")
allegro_local("nintendo 3ds")
allegro_local("gameboy")

print(f"\n📤 WYSŁANO: {sent_count}")