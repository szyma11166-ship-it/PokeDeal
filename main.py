import requests
from bs4 import BeautifulSoup
import re

# =========================
# 🔑 TELEGRAM
# =========================
BOT_TOKEN = "TWÓJ_TOKEN"
CHAT_ID = "-1003743099672"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("❌ TELEGRAM ERROR:", e)


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

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

    return min([float(m.replace(",", ".")) for m in matches])

# =========================
# 🚫 FILTRY
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
# 🎯 POKEMON LOGIKA
# =========================
def pokemon_filter(text, price):
    t = clean(text)

    if any(x in t for x in ["bulk", "100 kart", "200 kart", "losowe"]):
        return False

    if "booster" in t:
        return price <= 20

    if "etb" in t or "elite trainer box" in t:
        return price <= 300

    if "first partner" in t:
        return price <= 150

    if "pokemon day" in t or "2026" in t:
        return price <= 70

    if any(x in t for x in ["bundle", "box", "collection", "tin"]):
        return price <= 250

    return False

# =========================
# 📤 FORMAT (NAPRAWIONE)
# =========================
def format_msg(title, price, link, source):
    return (
        f"🔥 OKAZJA\n\n"
        f"📦 {title.strip()[:80]}\n\n"
        f"💰 {price} zł\n"
        f"📍 {source}\n\n"
        f"🔗 {link if link else 'brak linku'}"
    )

def send(title, price, link, source):
    msg = format_msg(title, price, link, source)
    print(msg + "\n")
    send_telegram(msg)

# =========================
# 🟢 OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    try:
        r = requests.get(f"https://www.olx.pl/oferty/q-{query}/", headers=HEADERS, timeout=5)
    except:
        print("❌ OLX error")
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

        except:
            continue

# =========================
# 🟣 VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    try:
        r = requests.get(f"https://www.vinted.pl/catalog?search_text={query}", headers=HEADERS, timeout=5)
    except:
        print("❌ Vinted error")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            text = item.get_text()
            price = get_price(text)

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

            send(text[:80], price, "brak linku", "VINTED")
            sent += 1

            if sent >= 5:
                break

        except:
            continue

# =========================
# 🟠 ALLEGRO LOKALNIE (FIX LINK)
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    try:
        r = requests.get(f"https://allegrolokalnie.pl/oferty/q/{query}", headers=HEADERS, timeout=5)
    except:
        print("❌ Allegro error")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")
    print(f"📦 {len(items)}")

    sent = 0

    for item in items:
        try:
            text = item.get_text()
            link_tag = item.find("a")

            link = "brak linku"
            if link_tag and link_tag.get("href"):
                link = "https://allegrolokalnie.pl" + link_tag.get("href")

            price = get_price(text)

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

            send(text[:80], price, link, "ALLEGRO")
            sent += 1

            if sent >= 5:
                break

        except:
            continue

# =========================
# 🚀 START
# =========================
print("🚀 SNIPER START")

queries = ["pokemon", "psp", "gameboy", "nintendo 3ds"]

for q in queries:
    olx_search(q)
    vinted_search(q)
    allegro_local(q)