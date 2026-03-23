import requests
from bs4 import BeautifulSoup
import re
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = "-1003743099672"

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
# 🚫 GLOBAL FILTER
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
# 🚫 GAME FILTER (NOWE)
# =========================
def is_game(title):
    t = clean(title)

    game_words = [
        "gra", "game", "fifa", "lego", "pokemon y",
        "pokemon x", "mario", "zelda"
    ]

    return any(g in t for g in game_words)


# =========================
# 🎮 CONSOLE FILTER
# =========================
def console_filter(query, title, price):
    t = clean(title)

    # musi zawierać słowo konsola/sprzęt
    if not any(x in t for x in ["konsol", "console", "psp", "3ds", "gameboy"]):
        return False

    # wywal gry
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
# 📤 TELEGRAM
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

    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    })


# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX {query}")

    url = f"https://www.olx.pl/oferty/q-{query}/"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")

    count = 0

    for item in items:
        if count >= 5:
            break

        try:
            title = item.select_one("h6").text
            link = item.select_one("a")["href"]
            price = get_price(item.get_text())

            if not price or not is_valid(title):
                continue

            if not console_filter(query, title, price):
                continue

            send(title, price, link, "OLX")
            count += 1

        except:
            continue


# =========================
# VINTED (FIX LINK)
# =========================
def vinted_search(query):
    print(f"\n🟣 VINTED {query}")

    url = f"https://www.vinted.pl/catalog?search_text={query}"
    r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select