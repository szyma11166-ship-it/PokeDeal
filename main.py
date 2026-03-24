import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os

# =========================

# CONFIG — uzupełnij zmienne środowiskowe lub wpisz ręcznie

# =========================

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

HEADERS = {
“User-Agent”: (
“Mozilla/5.0 (Windows NT 10.0; Win64; x64) “
“AppleWebKit/537.36 (KHTML, like Gecko) “
“Chrome/124.0.0.0 Safari/537.36”
)
}

print(“🚀 SNIPER V7.2 START”)

# Persystentny zestaw wysłanych linków (plik tekstowy)

SENT_FILE = “sent_links.txt”

def load_sent_links():
if not os.path.exists(SENT_FILE):
return set()
with open(SENT_FILE, “r”) as f:
return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
with open(SENT_FILE, “a”) as f:
f.write(link + “\n”)

sent_links = load_sent_links()

# =========================

# CLEAN

# =========================

def clean(text):
return re.sub(r”\s+”, “ “, text).strip().lower()

# =========================

# PRICE

# =========================

def get_price(text):
text = text.lower()
text = re.sub(r”\d+\s*gb”, “”, text)
text = re.sub(r”\d+%”, “”, text)

```
matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)

if not matches:
    return None

prices = [float(m.replace(",", ".")) for m in matches]
return min(prices)
```

# =========================

# GAME DETECTION

# =========================

def is_game(text):
t = clean(text)
game_words = [
“gra”, “gry”, “game”, “games”,
“fifa”, “lego”,
“pokemon”, “mario”, “zelda”
]
return any(g in t for g in game_words)

def is_game_bundle(text):
t = clean(text)
bundle_words = [
“zestaw”, “pakiet”, “bundle”,
“kolekcja”, “lot”
]
many_games = re.search(r”\d+\s*(gier|games)”, t)
return any(b in t for b in bundle_words) or many_games

# =========================

# GLOBAL FILTER

# =========================

def is_valid(title, full_text):
full = clean(full_text)

```
banned_global = [
    "uszkodz", "na części", "części",
    "konto", "psn", "steam",
    "bulk", "mix", "random",
    "japanese", "korea", "korean",
    "de ", "fr ", "it ",
    "zamiennik", "replacement"
]

if any(b in full for b in banned_global):
    return False

accessory_words = [
    "kabel", "ładowark", "charger",
    "case", "pokrowiec", "etui",
    "adapter", "dock", "stacja",
    "pad", "joystick", "kontroler"
]

console_keywords = [
    "psp",
    "nintendo 3ds",
    "3ds",
    "gameboy",
    "game boy",
    "gba",
    "gameboy advance",
    "sp",
    "konsola",
    "konsol"
]

has_console = any(k in full for k in console_keywords)

if not has_console and any(a in full for a in accessory_words):
    return False

return True
```

# =========================

# CONSOLE FILTER

# =========================

def console_filter(query, title, price, full_text):
full = clean(full_text)
query = query.lower()

```
fake_consoles = [
    "powkiddy", "anbernic", "sup",
    "gamebox", "r36s", "emulator",
    "retro console", "handheld console"
]

if any(f in full for f in fake_consoles):
    return False

if is_game(full):
    if not is_game_bundle(full):
        return False
    if price > 150:
        return False

if "psp" in query:
    return "psp" in full and price <= 200

if "3ds" in query:
    return "3ds" in full and price <= 400

if "gameboy" in query:
    real = [
        "gameboy", "game boy",
        "gba", "gameboy advance",
        "sp"
    ]
    return any(r in full for r in real) and price <= 300

return False
```

# =========================

# POKEMON FILTER

# =========================

def pokemon_filter(title, price):
t = clean(title)

```
if "pokemon" not in t:
    return False

banned = [
    "bulk", "mix", "random",
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
```

# =========================

# TELEGRAM

# =========================

def send(title, price, link, source):
if not link or “http” not in link:
return

```
if link in sent_links:
    return

sent_links.add(link)
save_sent_link(link)

msg = (
    f"🔥 OKAZJA\n\n"
    f"📦 {title[:80]}\n\n"
    f"💰 {price} zł\n"
    f"📍 {source}\n\n"
    f"🔗 {link}"
)

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

try:
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg
    }, timeout=10)
except Exception as e:
    print(f"❌ TELEGRAM ERROR: {e}")
```

# =========================

# CORE

# =========================

def process_items(items, query, source, get_title, get_link, full_text):
count = 0

```
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

        text_clean = clean(text)
        old_words = [
            "wczoraj", "2 dni temu", "3 dni temu",
            "tydzień temu", "7 dni temu"
        ]

        if any(o in text_clean for o in old_words):
            continue

        if query == "pokemon":
            if not pokemon_filter(title, price):
                continue
        else:
            if not console_filter(query, title, price, text):
                continue

        send(title, price, link, source)
        count += 1

    except Exception as e:
        print(f"⚠️ błąd item ({source} / {query}): {e}")
        continue
```

# =========================

# OLX

# =========================

def olx_search(query):
print(f”\n🟢 OLX: {query}”)

```
query_url = query.replace(" ", "-")
url = (
    f"https://www.olx.pl/oferty/q-{query_url}/"
    f"?search%5Border%5D=created_at:desc&_={random.randint(1, 9999999)}"
)

try:
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)} ofert")

    process_items(
        items, query, "OLX",
        lambda i: (i.select_one("h6") or i.select_one("h4") or i.select_one("a") or type("", (), {"text": ""})()).text.strip(),
        lambda i: ("https://www.olx.pl" + i.select_one("a")["href"])
                  if i.select_one("a") and not i.select_one("a")["href"].startswith("http")
                  else (i.select_one("a")["href"] if i.select_one("a") else None),
        lambda i: i.get_text()
    )
except Exception as e:
    print(f"❌ OLX ERROR: {e}")
```

# =========================

# VINTED

# — Uwaga: Vinted blokuje zwykłe scrapery (wymaga sesji/cookies).

# Poniższy kod może zwracać 0 wyników. Do poprawy z Selenium/Playwright.

# =========================

def vinted_search(query):
print(f”\n🟣 VINTED: {query}”)

```
params = {
    "search_text": query,
    "order": "newest_first"
}

try:
    r = requests.get(
        "https://www.vinted.pl/catalog",
        params=params,
        headers=HEADERS,
        timeout=10
    )
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div.feed-grid__item")
    print(f"📦 {len(items)} ofert (Vinted może blokować — sprawdź)")

    process_items(
        items, query, "VINTED",
        lambda i: i.get_text(separator=" ").strip()[:100],
        lambda i: ("https://www.vinted.pl" + i.select_one("a")["href"])
                  if i.select_one("a") else None,
        lambda i: i.get_text()
    )
except Exception as e:
    print(f"❌ VINTED ERROR: {e}")
```

# =========================

# ALLEGRO LOKALNIE

# =========================

def allegro_local(query):
print(f”\n🟠 ALLEGRO LOKALNIE: {query}”)

```
query_url = query.replace(" ", "%20")
url = f"https://allegrolokalnie.pl/oferty/q/{query_url}?order=newest"

try:
    r = requests.get(url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("article")
    print(f"📦 {len(items)} ofert")

    filtered = [i for i in items if "Promowane" not in i.get_text()]

    process_items(
        filtered, query, "ALLEGRO",
        lambda i: (i.select_one("h2") or type("", (), {"text": ""})()).text.strip(),
        lambda i: ("https://allegrolokalnie.pl" + i.select_one("a")["href"])
                  if i.select_one("a") else None,
        lambda i: i.get_text()
    )
except Exception as e:
    print(f"❌ ALLEGRO ERROR: {e}")
```

# =========================

# GŁÓWNA PĘTLA

# =========================

print(“🔁 LOOP START”)

QUERIES = [“psp”, “nintendo 3ds”, “gameboy”, “pokemon”]

while True:
try:
print(”\n🚀 NOWY CYKL”)

```
    for q in QUERIES:
        olx_search(q)
        time.sleep(random.uniform(1.5, 3.0))

        vinted_search(q)
        time.sleep(random.uniform(1.5, 3.0))

        allegro_local(q)
        time.sleep(random.uniform(1.5, 3.0))

    print("⏳ 60s przerwa...\n")
    time.sleep(60)

except Exception as e:
    print(f"❌ LOOP ERROR: {e}")
    time.sleep(30)
```