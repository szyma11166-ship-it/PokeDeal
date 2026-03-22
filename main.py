import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BOT_TOKEN = "TU_MASZ_SWÓJ_TOKEN"
CHAT_ID = "-1003743099672"

sent_links = set()

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
# 🚫 FILTRY ŚMIECI
# =========================
def is_valid(text):
    t = clean(text)

    banned = [
        "bulk", "losowa", "random", "1 karta", "pojedyncza",
        "proxy", "fake", "drukowana",
        "japanese", "korean", "korea", "jp", "kr",
        "deutsch", "german", "francais", "italiano"
    ]

    return not any(b in t for b in banned)


# =========================
# 🎯 LOGIKA PRODUKTU
# =========================
def is_target(title, price):
    t = clean(title)

    if "elite trainer box" in t and price <= 300:
        return "ETB"

    if "booster" in t and price <= 20:
        return "BOOSTER"

    if "bundle" in t and price <= 200:
        return "BUNDLE"

    if "illustration" in t:
        return "ILLUSTRATION"

    if "first partner" in t and price <= 150:
        return "FIRST PARTNER"

    if "pokemon day" in t and "2026" in t and price <= 70:
        return "POKEMON DAY"

    return None


# =========================
# 📤 TELEGRAM
# =========================
def send(title, price, link, tag, source):
    if link in sent_links:
        return

    sent_links.add(link)

    msg = f"""🔥 OKAZJA ({tag})

📦 {title}

💰 {price} zł
📍 {source}

🔗 {link}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })
    except:
        pass


# =========================
# 🟢 OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        if sent >= 5:
            break

        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]

            full = item.get_text()

            if "promowane" in clean(full):
                continue

            price = get_price(full)
            if not price:
                continue

            if not is_valid(title):
                continue

            tag = is_target(title, price)
            if not tag:
                continue

            send(title, price, link, tag, "OLX")
            sent += 1

        except:
            continue


# =========================
# 🟣 VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div.feed-grid__item")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        if sent >= 5:
            break

        try:
            text = item.get_text()
            link_tag = item.find("a")

            if not link_tag:
                continue

            link = "https://www.vinted.pl" + link_tag.get("href")

            price = get_price(text)
            if not price:
                continue

            if not is_valid(text):
                continue

            tag = is_target(text, price)
            if not tag:
                continue

            send(text[:80], price, link, tag, "VINTED")
            sent += 1

        except:
            continue


# =========================
# 🟠 ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("article")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        if sent >= 5:
            break

        try:
            text = item.get_text()

            if "promowane" in clean(text):
                continue

            link_tag = item.find("a")
            if not link_tag:
                continue

            link = "https://allegrolokalnie.pl" + link_tag.get("href")

            price = get_price(text)
            if not price:
                continue

            if not is_valid(text):
                continue

            tag = is_target(text, price)
            if not tag:
                continue

            send(text[:80], price, link, tag, "ALLEGRO")
            sent += 1

        except:
            continue


# =========================
# 🚀 LOOP
# =========================
print("🚀 SNIPER START")

while True:
    try:
        olx_search("pokemon")
        vinted_search("pokemon")
        allegro_local("pokemon")

    except Exception as e:
        print("ERROR:", e)

    time.sleep(60)