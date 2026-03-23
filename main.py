import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = -1003743099672

print("🚀 SNIPER V6 START")

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
# GLOBAL FILTER (SMART)
# =========================
def is_valid(title, full_text):
    t = clean(title)
    full = clean(full_text)

    # ❌ śmieci totalne
    banned_global = [
        "uszkodz", "na części", "części",
        "konto", "psn", "steam",
        "bulk", "lot", "mix", "random",
        "japanese", "korea", "korean",
        "de ", "fr ", "it ",
        "zamiennik", "replacement"
    ]

    if any(b in full for b in banned_global):
        return False

    # ❌ tylko akcesoria (ale nie zestawy!)
    accessory_words = [
        "kabel", "ładowark", "charger",
        "case", "pokrowiec", "etui",
        "adapter", "dock", "stacja",
        "pad", "joystick", "kontroler"
    ]

    has_console = any(x in full for x in [
        "psp", "3ds", "gameboy", "nintendo", "konsol"
    ])

    # jeśli NIE ma konsoli i są akcesoria → odrzucamy
    if not has_console and any(a in full for a in accessory_words):
        return False

    return True


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
# CONSOLE FILTER
# =========================
def console_filter(query, title, price):
    t = clean(title)
    query = query.lower()

    # ❌ fake konsole
    fake_consoles = [
        "powkiddy", "anbernic", "sup",
        "gamebox", "r36s", "emulator",
        "retro console", "handheld console"
    ]

    if any(f in t for f in fake_consoles):
        return False

    if is_game(title):
        return False

    # 🎯 PSP
    if "psp" in query:
        return "psp" in t and price <= 200

    # 🎯 3DS
    if "3ds" in query:
        return ("3ds" in t or "nintendo 3ds" in t) and price <= 400

    # 🎯 GAMEBOY (bardziej dokładnie)
    if "gameboy" in query:
        real = [
            "gameboy", "game boy",
            "gbc", "gameboy color",
            "gba", "gameboy advance",
            "sp"
        ]
        return any(r in t for r in real) and price <= 300

    return False


# =========================
# POKEMON FILTER
# =========================
def pokemon_filter(title, price):
    t = clean(title)

    if "pokemon" not in t:
        return False

    banned = [
        "bulk", "lot", "mix", "random",
        "energy", "kod", "online",
        "korea", "japanese",
        "de ", "fr ", "it "
    ]

    if any(b in t for b in banned):
        return False

    if "booster" in t:
        return price <= 20

    if "etb" in t or "elite trainer box" in t:
        return price <= 300

    if "first partner" in t:
        return price <= 150

    if "pokemon day" in t:
        return price <= 70

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
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg
        }, timeout=10)

    except Exception as e:
        print("❌ TELEGRAM ERROR:", e)


# =========================
# CORE
# =========================
def process_items(items, query, source, get_title, get_link, full_text):
    count = 0

    for item in items:
        if count >= 15:
            break

        try:
            title = get_title(item)
            link = get_link(item)
            text = full_text(item)

            price = get_price(text)

            if not price:
                continue

            if not is_valid(title, text):
                continue

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

    url = f"https://www.olx.pl/oferty/q-{query}/?search%5Border%5D=created_at:desc"
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div[data-cy='l-card']")
    print("📦", len(items))

    process_items(
        items, query, "OLX",
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
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("div.feed-grid__item")
    print("📦", len(items))

    process_items(
        items, query, "VINTED",
        lambda i: i.get_text(),
        lambda i: "https://www.vinted.pl" + i.select_one("a")["href"] if i.select_one("a") else None,
        lambda i: i.get_text()
    )


# =========================
# ALLEGRO
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO {query}")

    url = f"https://allegrolokalnie.pl/oferty/q/{query}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("article")
    print("📦", len(items))

    process_items(
        [i for i in items if "Promowane" not in i.get_text()],
        query, "ALLEGRO",
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

        for q in ["psp", "nintendo 3ds", "gameboy", "pokemon"]:
            olx_search(q)
            vinted_search(q)
            allegro_local(q)

        print("⏳ 60s...\n")
        time.sleep(60)

    except Exception as e:
        print("❌ LOOP ERROR:", e)
        time.sleep(30)