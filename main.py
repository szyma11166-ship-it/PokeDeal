import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import base64

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

print("🚀 SNIPER V8.6 START")

SENT_FILE = "sent_links.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
    with open(SENT_FILE, "a") as f:
        f.write(link + "\n")

sent_links = load_sent_links()


# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# HELPERS
# =========================
def safe_text(el):
    return el.text.strip() if el else ""


def olx_title(item):
    for selector in ["h6", "h4", "h3", "[data-cy='ad-card-title']", "a"]:
        el = item.select_one(selector)
        if el and el.text.strip():
            return el.text.strip()
    for line in item.get_text(separator="\n").splitlines():
        line = line.strip()
        if len(line) > 5:
            return line
    return ""


def allegro_title(item):
    for selector in ["h2", "h3", "h4", "[class*='title']", "[class*='name']", "a"]:
        el = item.select_one(selector)
        if el and el.text.strip():
            return el.text.strip()
    for line in item.get_text(separator="\n").splitlines():
        line = line.strip()
        if len(line) > 5:
            return line
    return ""


def allegro_link(item):
    a = item.select_one("a")
    if not a:
        return None
    href = a.get("href", "")
    if href.startswith("http"):
        return href
    return "https://allegrolokalnie.pl" + href


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
    prices = [p for p in prices if p >= 5]

    if not prices:
        return None

    return min(prices)


# =========================
# GAME DETECTION
# =========================
def is_game(text):
    t = clean(text)
    game_words = [
        "gra ", "gry ", " game", " games",
        "fifa", "lego ", "mario ", "zelda ",
        "littlebigplanet", "god of war", "monster hunter",
        "crisis core", "final fantasy", "metal gear"
    ]
    return any(g in t for g in game_words)


def is_game_bundle(text):
    t = clean(text)
    many_games = re.search(r"([3-9]|\d{2,})\s*(gier|games|gry)", t)
    return bool(many_games)


# =========================
# GLOBAL FILTER
# =========================
def is_valid(title, full_text):
    t = clean(title)
    full = clean(full_text)

    banned_title = [
        "pudelko", "pudełko", "opakowanie", "box only",
        "samo pudelko", "samo opakowanie", "idealne pudelko",
        "oryginalne opakowanie", "sam box", "karton",
        "umd", "umd movie", "umd film", "film umd", "umd video",
        "elokuva", "peli", " film", "movie", "žaidimai",
        "gra psp", "gra na psp", "gra do psp",
        "gra 3ds", "gra na 3ds", "gra do 3ds",
        "gra gameboy", "gra gba",
        "konto", "psn", "steam", "kod",
        "kabel", "ladowarka", "charger", "bateria", "akumulator",
        "case", "pokrowiec", "etui", "folia", "szklo",
        "adapter", "dock", "stacja", "uchwyt",
        "x7", "x7 slim", "x6 slim", "x9",
        "1000 gier", "10000 gier", "ponad 1000 gier",
    ]

    if any(b in t for b in banned_title):
        return False

    banned_global = [
        "uszkodz", "na czesci", "czesci zamienne",
        "japanese import", "korea", "korean",
        "zamiennik", "replacement",
        "blu-ray", " dvd ",
        "bulk", "random lot",
    ]

    if any(b in full for b in banned_global):
        return False

    return True


# =========================
# CONSOLE FILTER
# =========================
PSP_MODELS = [
    "psp 1000", "psp 2000", "psp 3000", "psp 3004",
    "psp go", "psp street", "psp-1000", "psp-2000",
    "psp-3000", "psp-3004", "pspgo",
    "sony psp", "konsola psp"
]

DS_MODELS = [
    "nintendo 3ds", "3ds xl", "3ds ll", "new 3ds",
    "new 3ds xl", "2ds", "2ds xl", "new 2ds",
    "nintendo ds", "nintendo dsi", "dsi xl",
    "konsola 3ds", "konsola ds"
]

GB_MODELS = [
    "game boy", "gameboy", "game boy advance",
    "gameboy advance", "gba sp", "game boy sp",
    "gameboy sp", "game boy color", "gameboy color",
    "gbc", "gba"
]

FAKE_CONSOLES = [
    "powkiddy", "anbernic", "sup game", "gamebox",
    "r36s", "rg35", "rg353", "fc3000",
    "miyoo", "trimui", "retroid", "ayaneo",
    "emulator", "retro console", "handheld console",
    "psp x", "psp x7", "psp x6", "psp x9",
    "clone", "klon konsoli"
]

PSP_GAME_TITLES = [
    "yu-gi-oh", "lego star wars", "lord of arcana",
    "crisis core", "metal gear", "gran turismo",
    "need for speed", "pro evolution", "pes ",
    "wipeout", "tekken", "ridge racer",
    "invizimals", "buzz", "sudoku", "singstar",
    "buzz master", "go sudoku", "exit ",
    "medieval", "lumines", "pursuit force",
    "burnout", "colin mcrae", "dirt ",
    "flatout", "smackdown", "nba ", "nfl ",
]

DS_GAME_TITLES = [
    "mario kart", "mario bros", "super mario",
    "zelda", "pokemon mystery", "luigi mansion",
    "animal crossing", "professor layton",
    "super smash", "rayman", "disney infinity",
    "hello kitty", "lego jurassic", "lego star",
    "new zealand story", "yo-kai watch",
    "mario sonic", "pes 20", "zoo resort",
    "transformers", "kirby", "sonic ",
    "inazuma", "dragon quest", "final fantasy",
    "harvest moon", "rune factory", "shin megami",
    "ace attorney", "rhythm heaven", "picross",
    "brain age", "nintendogs", "brain training",
    "scribblenauts", "cooking mama", "doa ",
    "star fox", "donkey kong", "metroid",
    "disney", "kung fu", "naruto",
]

GB_GAME_TITLES = [
    "pokemon red", "pokemon blue", "pokemon yellow",
    "pokemon gold", "pokemon silver", "pokemon crystal",
    "tetris", "super mario land", "metroid",
    "zelda", "donkey kong", "kirby", "wario",
    "mega man", "castlevania", "contra",
    "final fantasy", "dragon warrior",
]


def console_filter(query, title, price, full_text):
    t = clean(title)
    full = clean(full_text)
    query = query.lower()

    if any(f in full for f in FAKE_CONSOLES):
        return False
    if any(f in t for f in FAKE_CONSOLES):
        return False

    if is_game(t):
        if not is_game_bundle(t):
            return False
        if price > 150:
            return False

    if "psp" in query:
        if any(g in t for g in PSP_GAME_TITLES):
            return False
        has_model = any(m in t for m in PSP_MODELS)
        has_psp = "psp" in t
        return (has_model or has_psp) and price <= 200

    if "3ds" in query:
        if any(g in t for g in DS_GAME_TITLES):
            return False
        has_model = any(m in t for m in DS_MODELS)
        has_ds = "3ds" in t or "nintendo ds" in t
        return (has_model or has_ds) and price <= 400

    if "gameboy" in query:
        if any(g in t for g in GB_GAME_TITLES):
            return False
        has_model = any(m in t for m in GB_MODELS)
        has_gba = (
            "gameboy" in t or "game boy" in t or
            "gba" in t or "gbc" in t or
            ("sp" in t and ("game" in t or "nintendo" in t or "boy" in t))
        )
        return (has_model or has_gba) and price <= 300

    return False


# =========================
# POKEMON FILTER
# =========================
def pokemon_filter(title, price):
    t = clean(title)

    if "pokemon" not in t and "pokémon" not in t:
        return False

    banned = [
        "bulk", "mix", "random",
        "energy", "kod", "online",
        "korea", "japanese",
        "de ", "fr ", "it ",
        "karta", "karty", "card", "cards",
        "single", "holo", "reverse",
        "cm /", "mies.", "lat ·", "rozm",
        "bluzk", "koszulk", "spodnie", "bluza", "t-shirt",
        "mystery dungeon", "ranger", "snap",
        "stadium", "colosseum", "gale of darkness",
    ]

    if any(b in t for b in banned):
        return False

    if "etb" in t or "elite trainer box" in t:
        return price <= 300

    if "booster bundle" in t:
        return price <= 120

    if "blister" in t or "3-pack" in t or "3 pack" in t or "triple pack" in t:
        return price <= 80

    if "booster" in t:
        return price <= 25

    if "first partner" in t:
        return price <= 200

    if "pokemon day" in t or "pokémon day" in t:
        return price <= 120

    if len(t.split()) <= 3 and 15 <= price <= 500:
        return True

    return False


# =========================
# GEMINI AI REVIEW
# =========================
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY
)

AI_SYSTEM_PROMPT = """Jestes asystentem do filtrowania ofert z polskich serwisow ogloszenowych.
Uzytkownik szuka TYLKO:
1. Konsol do gier (nie gier!):
   - PSP oryginalne Sony (PSP-1000/2000/3000/Go/Street)
   - Nintendo 3DS / 2DS / DS / DSi (wszystkie warianty)
   - Game Boy / GBA / GBC oryginalne Nintendo
2. Zestawow konsola + gry (konsola musi byc wymieniona)
3. Pokemon TCG: boostery, ETB, booster bundle, blistery 3-pack, First Partner, Pokemon Day

BEZWZGLEDNIE ODRZUC:
- Pojedyncze gry (nawet jesli maja PSP/DS w nazwie)
- Filmy UMD
- Chinske klony (Anbernic, Powkiddy, R36S itp.)
- Akcesoria (kable, ladowarki, etui, szkla)
- Puste pudelka
- Konta PSN/Steam/kody
- Pojedyncze karty Pokemon
- Ubrania, figurki, zabawki z motywem Pokemon
- Gry video Pokemon (Mystery Dungeon, Ranger itp.)

AKCEPTUJ tylko jesli masz pewnosc ze to konsola lub zestaw z konsola lub produkt TCG Pokemon.
Przy watpliwosci — ODRZUC.

Odpowiedz TYLKO:
DECISION: ACCEPT lub REJECT
REASON: uzasadnienie po polsku (max 10 slow)"""


def fetch_image_base64(img_url):
    try:
        r = requests.get(img_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            return base64.b64encode(r.content).decode("utf-8"), r.headers.get("content-type", "image/jpeg")
    except Exception:
        pass
    return None, None


def ai_review(title, full_text, price, img_url=None):
    if not GEMINI_API_KEY:
        return False, "brak klucza AI — odrzucam"

    prompt = (
        f"Tytul oferty: {title}\n"
        f"Cena: {price} zl\n"
        f"Opis/tekst: {full_text[:500]}"
    )

    parts = [{"text": AI_SYSTEM_PROMPT + "\n\n" + prompt}]

    if img_url:
        img_data, mime = fetch_image_base64(img_url)
        if img_data:
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": img_data
                }
            })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 60
        }
    }

    for attempt in range(3):
        try:
            resp = requests.post(GEMINI_URL, json=payload, timeout=15)

            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"⏳ 429 rate limit — czekam {wait}s (próba {attempt+1}/3)")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            accept = "ACCEPT" in text.upper()
            reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else text[:60]

            return accept, reason

        except Exception as e:
            print(f"⚠️ AI ERROR: {e}")
            if attempt == 2:
                return False, "blad AI — odrzucam"
            time.sleep(5)

    return False, "blad AI — odrzucam"


# =========================
# TELEGRAM
# =========================
SOURCE_EMOJI = {
    "OLX": "🟢",
    "VINTED": "🟣",
    "ALLEGRO": "🟠"
}

def send(title, price, link, source):
    if not link or "http" not in link:
        return

    link_clean = link.split("?")[0].rstrip("/")

    if link_clean in sent_links:
        print(f"  ⏭️ duplikat — pomijam: {title[:40]}")
        return

    sent_links.add(link_clean)
    save_sent_link(link_clean)

    src_emoji = SOURCE_EMOJI.get(source, "📍")

    msg = (
        f"🔥 *NOWA OKAZJA*\n"
        f"{'─' * 28}\n"
        f"📦 {title[:80]}\n\n"
        f"💰 *{price} zł*\n"
        f"{src_emoji} {source}\n"
        f"{'─' * 28}\n"
        f"🔗 {link}"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }, timeout=10)
    except Exception as e:
        print(f"❌ TELEGRAM ERROR: {e}")


# =========================
# CORE
# =========================
def process_items(items, query, source, get_title, get_link, get_full_text, get_img_url=None):
    count = 0

    for item in items:
        if count >= 15:
            break

        try:
            title = get_title(item)
            link = get_link(item)
            text = get_full_text(item)
            img_url = get_img_url(item) if get_img_url else None

            if link:
                link_clean = link.split("?")[0].rstrip("/")
                if link_clean in sent_links:
                    continue

            price = get_price(text)
            print(f"  💲 cena: {price} | {title[:40]}")
            if not price:
                continue

            if not is_valid(title, text):
                print(f"  🚫 is_valid odrzucił: {title[:40]}")
                continue

            text_clean = clean(text)
            old_words = [
                "wczoraj", "2 dni temu", "3 dni temu",
                "tydzien temu", "7 dni temu"
            ]
            if any(o in text_clean for o in old_words):
                print(f"  ⏰ stara oferta: {title[:40]}")
                continue

            if query == "pokemon":
                passes_filter = pokemon_filter(title, price)
            else:
                passes_filter = console_filter(query, title, price, text)

            if not passes_filter:
                print(f"  🔍 filtr konsoli/pokemon odrzucił: {title[:40]}")
                continue

            accept, reason = ai_review(title, text, price, img_url)
            print(f"  🤖 AI: {'✅' if accept else '❌'} {reason} | {title[:50]}")
            time.sleep(4)

            if not accept:
                continue

            send(title, price, link, source)
            count += 1

        except Exception as e:
            print(f"⚠️ blad item ({source} / {query}): {e}")
            continue


# =========================
# OLX
# =========================
def olx_search(query):
    print(f"\n🟢 OLX: {query}")

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

        def get_img(i):
            img = i.select_one("img")
            return img["src"] if img and img.get("src") else None

        process_items(
            items, query, "OLX",
            lambda i: olx_title(i),
            lambda i: ("https://www.olx.pl" + i.select_one("a")["href"])
                      if i.select_one("a") and not i.select_one("a")["href"].startswith("http")
                      else (i.select_one("a")["href"] if i.select_one("a") else None),
            lambda i: i.get_text(),
            get_img
        )
    except Exception as e:
        print(f"❌ OLX ERROR: {e}")


# =========================
# VINTED
# =========================
def vinted_search(query):
    if query == "pokemon":
        print(f"\n🟣 VINTED: {query} — pominięto (zła struktura HTML)")
        return

    print(f"\n🟣 VINTED: {query}")

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
        print(f"📦 {len(items)} ofert (Vinted moze blokowac — sprawdz)")

        def get_img(i):
            img = i.select_one("img")
            return img["src"] if img and img.get("src") else None

        process_items(
            items, query, "VINTED",
            lambda i: i.get_text(separator=" ").strip()[:100],
            lambda i: ("https://www.vinted.pl" + i.select_one("a")["href"])
                      if i.select_one("a") else None,
            lambda i: i.get_text(),
            get_img
        )
    except Exception as e:
        print(f"❌ VINTED ERROR: {e}")


# =========================
# ALLEGRO LOKALNIE
# =========================
def allegro_local(query):
    print(f"\n🟠 ALLEGRO LOKALNIE: {query}")

    query_url = query.replace(" ", "%20")
    url = f"https://allegrolokalnie.pl/oferty/q/{query_url}?order=newest"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("article")
        print(f"📦 {len(items)} ofert")

        filtered = [i for i in items if "Promowane" not in i.get_text()]

        def get_img(i):
            img = i.select_one("img")
            return img["src"] if img and img.get("src") else None

        process_items(
            filtered, query, "ALLEGRO",
            lambda i: allegro_title(i),
            lambda i: allegro_link(i),
            lambda i: i.get_text(),
            get_img
        )
    except Exception as e:
        print(f"❌ ALLEGRO ERROR: {e}")


# =========================
# GLOWNA PETLA
# =========================
print("🔁 LOOP START")

QUERIES = ["konsola psp", "nintendo 3ds", "konsola gameboy", "pokemon"]

while True:
    try:
        print("\n🚀 NOWY CYKL")

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
