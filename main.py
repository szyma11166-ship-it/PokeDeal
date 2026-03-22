import requests
from bs4 import BeautifulSoup
import re
import time
import os

# =========================
# 🔑 TELEGRAM
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # z Railway Variables
CHAT_ID = "-1003743099672"  # na stałe

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": text
        }, timeout=5)

        print("📨 TELEGRAM STATUS:", r.status_code)
        print("📨 TELEGRAM RESPONSE:", r.text)

    except Exception as e:
        print("❌ TELEGRAM ERROR:", e)

# =========================
# HEADERS
# =========================
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()

# =========================
# PRICE
# =========================
def get_price(text):
    text = text.lower()

    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)

    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

    if not matches:
        return None

    return min([float(m.replace(",", ".")) for m in matches])

# =========================
# FILTER
# =========================
def is_valid(text):
    t = clean(text)

    banned = [
        "uszkodz", "na części", "etui", "kabel",
        "konto", "steam", "psn",
        "bez gry", "do naprawy",
        "fake", "replika"
    ]

    banned_lang = [" de ", " fr ", " it "]

    if any(b in t for b in banned):
        return False

    if any(l in t for l in banned_lang):
        return False

    return True

# =========================
# POKEMON FILTER
# =========================
def pokemon_filter(text, price):
    t = clean(text)

    # ❌ języki
    if any(x in t for x in ["korea", "korean", "japan", "jp", "china", "chi"]):
        return False

    # ❌ bulk
    if any(x in t for x in ["bulk", "100 kart", "200 kart", "losowe"]):
        return False

    # 🎯 booster
    if "booster" in t:
        return 8 <= price <= 20

    # 🎯 ETB
    if "etb" in t or "elite trainer box" in t:
        return price <= 300

    # 🎯 FIRST PARTNER
    if "first partner" in t:
        return price <= 150

    # 🎯 pokemon day
    if "pokemon day" in t or "2026" in t:
        return price <= 70

    # 🎯 box / bundle
    if any(x in t for x in ["box", "collection", "tin", "bundle"]):
        return price <= 250

    return False

# =========================
# SEND
# =========================
def send(title, price, link, source):

    if not title or len(title.strip()) < 5:
        return

    msg = (
        f"🔥 OKAZJA\n\n"
        f"📦 {title[:80]}\n\n"
        f"💰 {price} zł\n"
        f"📍 {source}\n\n"
        f"🔗 {link if link else 'brak linku'}"
    )

    print(msg + "\n")
    send_telegram(msg)

# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    try:
        r = requests.get(f"https://www.olx.pl/oferty/q-{query}/", headers=HEADERS, timeout=5)
    except:
        print("❌ OLX ERROR")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")

    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            text = item.get_text()

            price = get_price(text)
            if not price:
                continue

            full = title + " " + text

            if not is_valid(full):
                continue

            if "pokemon" in query:
                if not pokemon_filter(full, price):
                    continue
            else:
                if price < 100:
                    continue

            send(title, price, link, "OLX")
            sent += 1

            if sent >= 5:
                break

            time.sleep(1)

        except:
            continue

# =========================
# VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    try:
        r = requests.get(f"https://www.vinted.pl/catalog?search_text={query}", headers=HEADERS, timeout=5)
    except:
        print("❌ VINTED ERROR")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")

    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            title_tag = item.find("p")
            if not title_tag:
                continue

            title = title_tag.text
            text = title

            price = get_price(item.get_text())
            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(text, price):
                    continue
            else:
                if price < 100:
                    continue

            send(title, price, "brak linku", "VINTED")
            sent += 1

            if sent >= 5:
                break

            time.sleep(1)

        except:
            continue

# =========================
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    try:
        r = requests.get(f"https://allegrolokalnie.pl/oferty/q/{query}", headers=HEADERS, timeout=5)
    except:
        print("❌ ALLEGRO ERROR")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")

    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            title_tag = item.find("h2")
            if not title_tag:
                continue

            title = title_tag.text
            text = title

            link_tag = item.find("a")
            link = "brak linku"

            if link_tag and link_tag.get("href"):
                link = "https://allegrolokalnie.pl" + link_tag.get("href")

            price = get_price(item.get_text())
            if not price:
                continue

            if not is_valid(text):
                continue

            if "pokemon" in query:
                if not pokemon_filter(text, price):
                    continue
            else:
                if price < 100:
                    continue

            send(title, price, link, "ALLEGRO")
            sent += 1

            if sent >= 5:
                break

            time.sleep(1)

        except:
            continue

# =========================
# LOOP
# =========================
print("🚀 SNIPER START")
print("TOKEN:", BOT_TOKEN)

while True:
    try:
        queries = ["pokemon", "psp", "gameboy", "nintendo 3ds"]

        for q in queries:
            olx_search(q)
            vinted_search(q)
            allegro_local(q)

        print("⏳ SLEEP 60s\n")
        time.sleep(60)

    except Exception as e:
        print("❌ CRASH:", e)
        time.sleep(10)