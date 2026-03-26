import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import base64
import json

# =========================

# CONFIG

# =========================

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"

HEADERS = {
“User-Agent”: (
“Mozilla/5.0 (Windows NT 10.0; Win64; x64) “
“AppleWebKit/537.36 (KHTML, like Gecko) “
“Chrome/124.0.0.0 Safari/537.36”
),
“Accept”: “text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8”,
“Accept-Language”: “pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7”,
“Accept-Encoding”: “gzip, deflate, br”,
“Connection”: “keep-alive”,
“Upgrade-Insecure-Requests”: “1”,
“Cache-Control”: “max-age=0”,
}

print(“🚀 SNIPER V9.0 START”)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

SENT_FILE = “sent_links.txt”
AI_CACHE_FILE = “ai_cache.json”  # NOWE: cache decyzji AI

# =========================

# STORAGE

# =========================

def load_sent_links():
if not os.path.exists(SENT_FILE):
return set()
with open(SENT_FILE, “r”) as f:
return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
with open(SENT_FILE, “a”) as f:
f.write(link + “\n”)

def load_ai_cache():
“”“Wczytaj cache decyzji AI z pliku JSON.”””
if not os.path.exists(AI_CACHE_FILE):
return {}
try:
with open(AI_CACHE_FILE, “r”, encoding=“utf-8”) as f:
return json.load(f)
except Exception:
return {}

def save_ai_cache(cache):
“”“Zapisz cache decyzji AI do pliku JSON.”””
try:
with open(AI_CACHE_FILE, “w”, encoding=“utf-8”) as f:
json.dump(cache, f, ensure_ascii=False, indent=2)
except Exception as e:
print(f”⚠️ Błąd zapisu cache AI: {e}”)

def make_cache_key(title, price):
“”“Klucz cache na podstawie tytułu + przedziału cenowego (nie dokładnej ceny).”””
t = re.sub(r”\s+”, “ “, title).strip().lower()
# Zaokrąglamy cenę do przedziałów po 20zł, żeby np. 89 i 91zł trafiały w ten sam bucket
price_bucket = int(price // 20) * 20
return f”{t}|{price_bucket}”

sent_links = load_sent_links()
ai_cache = load_ai_cache()

# =========================

# CLEAN / HELPERS

# =========================

def clean(text):
return re.sub(r”\s+”, “ “, text).strip().lower()

def safe_text(el):
return el.text.strip() if el else “”

def olx_title(item):
for selector in [“h6”, “h4”, “h3”, “[data-cy=‘ad-card-title’]”, “a”]:
el = item.select_one(selector)
if el and el.text.strip():
return el.text.strip()
for line in item.get_text(separator=”\n”).splitlines():
line = line.strip()
if len(line) > 5:
return line
return “”

def allegro_title(item):
for selector in [“h2”, “h3”, “h4”, “[class*=‘title’]”, “[class*=‘name’]”, “a”]:
el = item.select_one(selector)
if el and el.text.strip():
return el.text.strip()
for line in item.get_text(separator=”\n”).splitlines():
line = line.strip()
if len(line) > 5:
return line
return “”

def allegro_link(item):
a = item.select_one(“a”)
if not a:
return None
href = a.get(“href”, “”)
if href.startswith(“http”):
return href
return “https://allegrolokalnie.pl” + href

# =========================

# PRICE

# =========================

def get_price(text):
text = text.lower()
text = re.sub(r”\d+\s*gb”, “”, text)
text = re.sub(r”\d+%”, “”, text)
matches = re.findall(r”(\d{1,5}(?:[.,]\d{1,2})?)\s*zł”, text)
if not matches:
return None
prices = [float(m.replace(”,”, “.”)) for m in matches]
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
“gra “, “gry “, “ game”, “ games”,
“fifa”, “lego “, “mario “, “zelda “,
“littlebigplanet”, “god of war”, “monster hunter”,
“crisis core”, “final fantasy”, “metal gear”
]
return any(g in t for g in game_words)

def is_game_bundle(text):
t = clean(text)
many_games = re.search(r”([3-9]|\d{2,})\s*(gier|games|gry)”, t)
return bool(many_games)

# =========================

# GLOBAL FILTER

# =========================

def is_valid(title, full_text):
t = clean(title)
full = clean(full_text)

```
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
    "nagrywarka", "r4i", "r4 gold",
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
```

# =========================

# CONSOLE FILTER

# =========================

PSP_MODELS = [
“psp 1000”, “psp 2000”, “psp 3000”, “psp 3004”,
“psp go”, “psp street”, “psp slim”, “psp-1000”,
“psp-2000”, “psp-3000”, “psp-3004”, “pspgo”,
“sony psp”, “konsola psp”
]

DS_MODELS = [
“nintendo 3ds”, “3ds xl”, “3ds ll”, “new 3ds”,
“new 3ds xl”, “2ds”, “2ds xl”, “new 2ds”,
“nintendo ds”, “nintendo dsi”, “dsi xl”,
“konsola 3ds”, “konsola ds”
]

GB_MODELS = [
“game boy”, “gameboy”, “game boy advance”,
“gameboy advance”, “gba sp”, “game boy sp”,
“gameboy sp”, “game boy color”, “gameboy color”,
“gbc”, “gba”
]

FAKE_CONSOLES = [
“powkiddy”, “anbernic”, “sup game”, “gamebox”,
“r36s”, “rg35”, “rg353”, “fc3000”,
“miyoo”, “trimui”, “retroid”, “ayaneo”,
“emulator”, “retro console”, “handheld console”,
“psp x”, “psp x7”, “psp x6”, “psp x9”,
“clone”, “klon konsoli”
]

PSP_GAME_TITLES = [
“yu-gi-oh”, “lego star wars”, “lord of arcana”,
“crisis core”, “metal gear”, “gran turismo”,
“need for speed”, “pro evolution”, “pes “,
“wipeout”, “tekken”, “ridge racer”,
“invizimals”, “buzz”, “sudoku”, “singstar”,
“buzz master”, “go sudoku”, “exit “,
“medieval”, “lumines”, “pursuit force”,
“burnout”, “colin mcrae”, “dirt “,
“flatout”, “smackdown”, “nba “, “nfl “,
“fight night”, “mortal kombat”, “street fighter”,
“god of war”, “gta “, “grand theft”,
“resistance”, “killzone”, “medal of honor”,
“call of duty”, “battlefield”, “tomb raider”,
“avatar”, “daxter”, “everybody’s golf”, “ben 10”,
“little big planet”, “littlebigplanet”,
“fifa”, “nba 2k”, “ufc”,
]

DS_GAME_TITLES = [
“mario kart”, “mario bros”, “super mario”,
“zelda”, “pokemon mystery”, “luigi mansion”,
“animal crossing”, “professor layton”,
“super smash”, “rayman”, “disney infinity”,
“hello kitty”, “lego jurassic”, “lego star”,
“new zealand story”, “yo-kai watch”,
“mario sonic”, “pes 20”, “zoo resort”,
“transformers”, “kirby”, “sonic “,
“inazuma”, “dragon quest”, “final fantasy”,
“harvest moon”, “rune factory”, “shin megami”,
“ace attorney”, “rhythm heaven”, “picross”,
“brain age”, “nintendogs”, “brain training”,
“scribblenauts”, “cooking mama”, “doa “,
“star fox”, “donkey kong”, “metroid”,
“disney”, “kung fu”, “naruto”,
“big hero”, “tintin”, “ravenhearst”, “hamsterz”,
“puzzle master”, “mystery stories”, “joc nintendo”,
“paket med”, “sonic lost”, “paper mario”,
“lego movie”, “lego hobbit”, “lego batman”,
“return to”, “adventures of”, “super mario maker”,
“mario sticker”, “lego the”, “tinker bell”,
“winx”, “barbie”, “bratz”, “my little pony”,
“monster hunter”, “need for speed”,
“metal gear solid”, “mystery case”,
]

GB_GAME_TITLES = [
“pokemon red”, “pokemon blue”, “pokemon yellow”,
“pokemon gold”, “pokemon silver”, “pokemon crystal”,
“tetris”, “super mario land”, “metroid”,
“zelda”, “donkey kong”, “kirby”, “wario”,
“mega man”, “castlevania”, “contra”,
“final fantasy”, “dragon warrior”,
]

def console_filter(query, title, price, full_text):
t = clean(title)
full = clean(full_text)
query = query.lower()

```
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
```

# =========================

# POKEMON FILTER

# =========================

def pokemon_filter(title, price):
t = clean(title)

```
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
```

# =========================

# IS UNCERTAIN — kiedy wołać AI

# =========================

def is_uncertain(title, query):
“””
AI jest OSTATECZNOŚCIĄ — wywołuj tylko gdy:
1. Żaden znany model konsoli nie pasuje do tytułu
2. Tytuł nie zawiera słów jednoznacznie go klasyfikujących
Jeśli filtr przepuścił i mamy pewność — nie wołaj AI.
“””
t = clean(title)

```
# Dla Pokemon: zawsze pewne jeśli zawiera znane słowa kluczowe TCG
if query == "pokemon":
    tcg_words = ["booster", "etb", "blister", "bundle", "trainer box",
                 "first partner", "pokemon day"]
    return not any(w in t for w in tcg_words)

# Dla PSP: pewne jeśli zawiera pełny model (np. "psp 3000")
if "psp" in query:
    certain = any(m in t for m in PSP_MODELS)
    # Dodatkowo: jeśli tytuł zawiera "konsola" + "psp" — pewne
    if "konsola" in t and "psp" in t:
        certain = True
    return not certain

# Dla 3DS: pewne jeśli zawiera znany model
if "3ds" in query:
    certain = any(m in t for m in DS_MODELS)
    if "konsola" in t and ("3ds" in t or "ds" in t):
        certain = True
    return not certain

# Dla Game Boy: pewne jeśli zawiera znany model
if "gameboy" in query:
    certain = any(m in t for m in GB_MODELS)
    return not certain

return False
```

# =========================

# GEMINI AI — ostateczność

# =========================

GEMINI_URL = (
“https://generativelanguage.googleapis.com/v1beta/models/”
“gemini-2.0-flash:generateContent?key=” + GEMINI_API_KEY
)

AI_SYSTEM_PROMPT = “”“Jestes asystentem do filtrowania ofert z polskich serwisow ogloszenowych.
Uzytkownik szuka TYLKO:

1. Konsol do gier (nie gier!):
- PSP oryginalne Sony (PSP-1000/2000/3000/Go/Street)
- Nintendo 3DS / 2DS / DS / DSi (wszystkie warianty)
- Game Boy / GBA / GBC oryginalne Nintendo
1. Zestawow konsola + gry (konsola musi byc wymieniona)
1. Pokemon TCG: boostery, ETB, booster bundle, blistery 3-pack, First Partner, Pokemon Day

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
REASON: uzasadnienie po polsku (max 10 slow)”””

def fetch_image_base64(img_url):
try:
r = SESSION.get(img_url, timeout=8)
if r.status_code == 200:
return base64.b64encode(r.content).decode(“utf-8”), r.headers.get(“content-type”, “image/jpeg”)
except Exception:
pass
return None, None

def ai_review(title, full_text, price, img_url=None):
“””
Wywołaj Gemini AI. Używaj TYLKO gdy is_uncertain() zwróci True.
Wyniki są cache’owane — ta sama oferta nie będzie analizowana dwa razy.
Exponential backoff przy 429.
“””
if not GEMINI_API_KEY:
return False, “brak klucza AI — odrzucam”

```
# --- CACHE CHECK ---
cache_key = make_cache_key(title, price)
if cache_key in ai_cache:
    cached = ai_cache[cache_key]
    print(f"  💾 cache AI: {'✅' if cached['accept'] else '❌'} {cached['reason']}")
    return cached["accept"], cached["reason"]

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

MAX_RETRIES = 5
for attempt in range(MAX_RETRIES):
    try:
        resp = requests.post(GEMINI_URL, json=payload, timeout=15)

        if resp.status_code == 429:
            # Exponential backoff: 10s, 20s, 40s, 80s, 160s
            wait = 10 * (2 ** attempt) + random.uniform(0, 3)
            print(f"⏳ 429 rate limit — czekam {wait:.0f}s (próba {attempt+1}/{MAX_RETRIES})")
            if attempt == MAX_RETRIES - 1:
                # Po wszystkich próbach — NIE odrzucaj, zwróć None (do kolejki)
                return None, "rate limit — do sprawdzenia później"
            time.sleep(wait)
            continue

        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        accept = "ACCEPT" in text.upper()
        reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE)
        reason = reason_match.group(1).strip() if reason_match else text[:60]

        # --- ZAPISZ DO CACHE ---
        ai_cache[cache_key] = {"accept": accept, "reason": reason}
        save_ai_cache(ai_cache)

        return accept, reason

    except Exception as e:
        print(f"⚠️ AI ERROR (próba {attempt+1}): {e}")
        if attempt == MAX_RETRIES - 1:
            return None, "blad AI — pomijam (nie odrzucam)"
        time.sleep(5 * (attempt + 1))

return None, "blad AI — pomijam"
```

# =========================

# TELEGRAM

# =========================

SOURCE_EMOJI = {
“OLX”: “🟢”,
“VINTED”: “🟣”,
“ALLEGRO”: “🟠”
}

def send(title, price, link, source):
if not link or “http” not in link:
return

```
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
```

# =========================

# CORE

# =========================

# Kolejka ofert których AI nie zdążył sprawdzić (rate limit)

ai_pending_queue = []

def process_items(items, query, source, get_title, get_link, get_full_text, get_img_url=None):
count = 0

```
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

        # AI tylko gdy naprawdę niepewne
        if is_uncertain(title, query):
            accept, reason = ai_review(title, text, price, img_url)
            print(f"  🤖 AI: {'✅' if accept else ('⏳' if accept is None else '❌')} {reason} | {title[:50]}")
            time.sleep(2)  # krótszy delay bo AI wywoływane rzadziej

            if accept is None:
                # Rate limit — dodaj do kolejki zamiast odrzucać
                ai_pending_queue.append({
                    "title": title, "price": price, "link": link,
                    "source": source, "text": text, "img_url": img_url
                })
                print(f"  ⏳ dodano do kolejki AI: {title[:40]}")
                continue
            if not accept:
                continue
        else:
            print(f"  ✅ pewna oferta — pomijam AI | {title[:50]}")

        send(title, price, link, source)
        count += 1

    except Exception as e:
        print(f"⚠️ blad item ({source} / {query}): {e}")
        continue
```

def process_ai_queue():
“”“Przetwórz oferty czekające na AI (np. po rate limicie).”””
if not ai_pending_queue:
return

```
print(f"\n🔄 Przetwarzam kolejkę AI: {len(ai_pending_queue)} ofert")
time.sleep(30)  # daj API chwilę oddechu

still_pending = []
for item in ai_pending_queue[:]:
    accept, reason = ai_review(
        item["title"], item["text"], item["price"], item.get("img_url")
    )
    if accept is None:
        still_pending.append(item)
        continue
    print(f"  🤖 kolejka AI: {'✅' if accept else '❌'} {reason} | {item['title'][:40]}")
    if accept:
        send(item["title"], item["price"], item["link"], item["source"])

ai_pending_queue.clear()
ai_pending_queue.extend(still_pending)
```

# =========================

# OLX — API JSON zamiast HTML scraping

# =========================

def olx_search(query):
print(f”\n🟢 OLX: {query}”)

```
# OLX ma publiczne API — dużo stabilniejsze niż scraping HTML
api_url = "https://www.olx.pl/api/v1/offers/"
params = {
    "query": query,
    "sort_by": "created_at:desc",
    "limit": 40,
    "offset": 0,
}

try:
    r = SESSION.get(api_url, params=params, timeout=12)
    print(f"  📡 OLX API status: {r.status_code}")

    if r.status_code != 200:
        # Fallback do HTML scraping jeśli API nie działa
        print(f"  ⚠️ OLX API niedostępne — próbuję HTML")
        olx_search_html(query)
        return

    data = r.json()
    offers = data.get("data", [])
    print(f"📦 {len(offers)} ofert z API")

    count = 0
    for offer in offers:
        if count >= 15:
            break
        try:
            title = offer.get("title", "")
            link = offer.get("url", "")
            price_data = offer.get("price", {}) or {}
            price_value = price_data.get("value", {}) or {}
            price = float(price_value.get("amount", 0) or 0)

            # Zbuduj pełny tekst z dostępnych pól
            params_list = offer.get("params", []) or []
            params_text = " ".join(
                str(p.get("value", {}).get("label", ""))
                for p in params_list if p.get("value")
            )
            full_text = f"{title} {params_text} {price} zł"

            # Obrazek
            photos = offer.get("photos", []) or []
            img_url = photos[0].get("link", "").replace("{width}", "400").replace("{height}", "300") if photos else None

            if link:
                link_clean = link.split("?")[0].rstrip("/")
                if link_clean in sent_links:
                    continue

            print(f"  💲 cena: {price} | {title[:40]}")
            if not price or price < 5:
                continue

            if not is_valid(title, full_text):
                print(f"  🚫 is_valid odrzucił: {title[:40]}")
                continue

            if query == "pokemon":
                passes_filter = pokemon_filter(title, price)
            else:
                passes_filter = console_filter(query, title, price, full_text)

            if not passes_filter:
                print(f"  🔍 filtr odrzucił: {title[:40]}")
                continue

            if is_uncertain(title, query):
                accept, reason = ai_review(title, full_text, price, img_url)
                print(f"  🤖 AI: {'✅' if accept else ('⏳' if accept is None else '❌')} {reason} | {title[:50]}")
                time.sleep(2)
                if accept is None:
                    ai_pending_queue.append({
                        "title": title, "price": price, "link": link,
                        "source": "OLX", "text": full_text, "img_url": img_url
                    })
                    continue
                if not accept:
                    continue
            else:
                print(f"  ✅ pewna oferta — pomijam AI | {title[:50]}")

            send(title, price, link, "OLX")
            count += 1

        except Exception as e:
            print(f"⚠️ blad oferty OLX: {e}")
            continue

except Exception as e:
    print(f"❌ OLX API ERROR: {e}")
    olx_search_html(query)
```

def olx_search_html(query):
“”“Fallback HTML scraping dla OLX.”””
query_url = query.replace(” “, “-”)
url = (
f”https://www.olx.pl/oferty/q-{query_url}/”
f”?search%5Border%5D=created_at:desc&_={random.randint(1, 9999999)}”
)

```
try:
    r = SESSION.get(url, timeout=10)
    print(f"  📡 OLX HTML status: {r.status_code} | dlugosc: {len(r.text)}")
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("div[data-cy='l-card']")
    print(f"📦 {len(items)} ofert (HTML fallback)")

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
    print(f"❌ OLX HTML ERROR: {e}")
```

# =========================

# VINTED

# =========================

def vinted_search(query):
if query == “pokemon”:
print(f”\n🟣 VINTED: {query} — pominięto (zła struktura HTML)”)
return

```
print(f"\n🟣 VINTED: {query}")

params = {
    "search_text": query,
    "order": "newest_first"
}

try:
    r = SESSION.get(
        "https://www.vinted.pl/catalog",
        params=params,
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
    r = SESSION.get(url, timeout=10)
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
```

# =========================

# GŁÓWNA PĘTLA

# =========================

print(“🔁 LOOP START”)

QUERIES = [“konsola psp”, “nintendo 3ds”, “konsola gameboy”, “pokemon”]

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

    # Po każdym cyklu — przetwórz kolejkę AI jeśli coś czeka
    process_ai_queue()

    print("⏳ 60s przerwa...\n")
    time.sleep(60)

except Exception as e:
    print(f"❌ LOOP ERROR: {e}")
    time.sleep(30)
