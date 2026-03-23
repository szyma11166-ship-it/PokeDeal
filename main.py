import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# 🔑 TELEGRAM
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = -1003743099672

print("🚀 SNIPER V5 START")

sent_links = set()

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

    prices = [float(m.replace(",", ".")) for m in matches]
    return min(prices)


# =========================
# GLOBAL FILTER
# =========================
def is_valid(title):
    t = clean(title)

    banned = [
        "uszkodz", "części", "na części",
        "etui", "ładowark", "kabel",
        "konto", "psn", "steam",
        "bulk", "lot", "mix", "random",
        "japanese", "korea", "korean",
        "de ", "fr ", "it "
    ]

    return not any(b in t for b in banned)


# =========================
# GAME FILTER
# =========================
def is_game(title):
    t = clean(title)

    game_words = [
        "gra", "game", "fifa", "lego",
        "pokemon y", "pokemon x",
        "mario", "zelda"
    ]

    return any(g in t for g in game_words)


# =========================
# 🎮 CONSOLE FILTER
# =========================
def console_filter(query, title, price):
    t = clean(title)

    if not any(x in t for x in ["konsol", "console", "psp", "3ds", "gameboy", "nintendo"]):
        return False

    if is_game(title):
        return False

    if "psp" in query:
        return price <= 200

    if "3ds" in query:
        return price <= 400

    if "gameboy" in query:
        return price <= 300

    return False


# =========================
# 🧢 POKEMON FILTER (FINAL)
# =========================
def pokemon_filter(title, price):
    t = clean(title)

    if "pokemon" not in t:
        return False

    # ❌ śmieci
    banned = [
        "bulk", "lot", "mix", "random",
        "energy", "kod", "online",
        "korea", "japanese",
        "de ", "fr ", "it "
    ]

    if any(b in t for b in banned):
        return False

    # BOOSTER
    if "booster" in t:
        return price <= 20

    # ETB
    if "etb" in t or "elite trainer box" in t:
        return price <= 300

    # FIRST PARTNER
    if "first partner" in t:
        return price <= 150

    # POKEMON DAY
    if "pokemon day" in t:
        return price <= 70

    # BUNDLE / ZESTAW
    if any(x in t for x in ["zestaw", "bundle", "pakiet", "kolekcja"]):
        return price <= 300

    return False


# =========================
# TELEGRAM
# =========================
def send(title, price, link, source):
    if not link or "http" not in link:
        return

    if link in sent_links:
        return

    sent_links.add(link)

    msg = f"""🔥 OKAZJA

📦 {title[:80]}

💰 {price} zł
📍 {source}

🔗 {link}
"""

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        r = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        })

        print("📨", r.status_code)

    except Exception as e:
        print("❌ TELEGRAM ERROR:", e)


# =========================
# CORE SEARCH
# =========================
def process_items(items, query, source, get_title, get_link, full_text):
    count = 0

    for item in items:
        if count >= 5:
            break

        try:
            title = get_title(item)
            link = get_link(item)
            text = full_text(item)

            price = get_price(text)

            if not price or not is_valid(title):
                continue

            # 🔥 wybór filtra
            if query == "pokemon":
                if not pokemon_filter(title, price):
                    continue
            else:
                if not console_filter(query, title, price):
                    continue

            send(title, price, link, source)
            count += 1

        except:
            continue


# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print("📦", len(items))

    process_items(
        items,
        query,
        "OLX",
        lambda i: i.select_one("h6").text,
        lambda i: i.select_one("a")["href"],
        lambda i: i.get_text()
    )


# =========================
# VINTED
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div.feed-grid__item")
    print("📦", len(items))

    process_items(
        items,
        query,
        "VINTED",
        lambda i: i.get_text(),
        lambda i: "https://www.vinted.pl" + i.select_one("a")["href"] if i.select_one("a") else None,
        lambda i: i.get_text()
    )


# =========================
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("article")
    print("📦", len(items))

    process_items(
        [i for i in items if "Promowane" not in i.get_text()],
        query,
        "ALLEGRO",
        lambda i: i.select_one("h2").text if i.select_one("h2") else "",
        lambda i: "https://allegrolokalnie.pl" + i.select_one("a")["href"] if i.select_one("a") else None,
        lambda i: i.get_text()
    )


# =========================
# LOOP
# =========================
print("🔁 LOOP START")

while True:
    try:
        print("\n🚀 NOWY CYKL")

        # 🎮 KONSOLE
        olx_search("psp")
        vinted_search("psp")
        allegro_local("psp")

        olx_search("nintendo 3ds")
        vinted_search("nintendo 3ds")
        allegro_local("nintendo 3ds")

        olx_search("gameboy")
        vinted_search("gameboy")
        allegro_local("gameboy")

        # 🧢 POKEMON
        olx_search("pokemon")
        vinted_search("pokemon")
        allegro_local("pokemon")

        print("⏳ 60s...\n")
        time.sleep(60)

    except Exception as e:
        print("❌ LOOP ERROR:", e)
        time.sleep(30)