from curl_cffi import requests as curl_requests
import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
SENT_URLS = set()
IS_FIRST_RUN = True
VINTED_LAST_INIT = 0
VINTED_INIT_INTERVAL = 2 * 3600

VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
VINTED_SESSION.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://www.vinted.pl/catalog",
    "Origin": "https://www.vinted.pl",
})

OLX_SESSION = requests.Session()
OLX_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

ALLEGRO_SESSION = requests.Session()
ALLEGRO_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
})

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
    except:
        pass

# --- INICJALIZACJA SESJI VINTED ---
def vinted_init():
    global VINTED_LAST_INIT
    try:
        log_debug("🔄 Inicjalizuję sesję Vinted...")
        browsers = ["chrome120", "chrome116", "safari15_5", "edge101"]
        VINTED_SESSION.impersonate = random.choice(browsers)
        VINTED_SESSION.cookies.clear()
        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        if r.status_code == 200:
            log_debug(f"✅ Sesja Vinted gotowa ({VINTED_SESSION.impersonate})")
            VINTED_LAST_INIT = time.time()
            return True
        else:
            log_debug(f"⚠️ Vinted init status: {r.status_code}")
            return False
    except Exception as e:
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def vinted_ensure():
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

# --- VINTED ---
def scrape_vinted(query):
    if not vinted_ensure():
        return
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={q_enc}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)

        if r.status_code in [401, 403]:
            log_debug(f"🔄 Vinted {r.status_code} — reset sesji...")
            time.sleep(15)
            if vinted_init():
                r = VINTED_SESSION.get(url, timeout=20)
            else:
                return

        if r.status_code == 200:
            try:
                data = r.json()
            except:
                log_debug("⚠️ Vinted — odpowiedź nie jest JSON")
                return
            items = data.get("items", [])
            new_count = 0
            for item in items:
                title = item.get("title", "")
                price_raw = item.get("price", 0)
                if isinstance(price_raw, dict):
                    price = float(price_raw.get("amount", 0))
                else:
                    price = float(price_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"):
                    item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED"):
                    new_count += 1
            log_debug(f"✅ Vinted [{query}]: {len(items)} ofert, {new_count} nowych")
        else:
            log_debug(f"⚠️ Vinted status: {r.status_code}")
    except Exception as e:
        log_debug(f"💥 Błąd Vinted: {e}")

# --- OLX ---
def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if p_val:
                    if process_item(o['title'], o['url'], float(p_val), "OLX"):
                        new_count += 1
            log_debug(f"✅ OLX [{query}]: nowych {new_count}")
        else:
            log_debug(f"⚠️ OLX status: {r.status_code}")
    except Exception as e:
        log_debug(f"💥 Błąd OLX: {e}")

# --- ALLEGRO LOKALNIE ---
def scrape_allegro_lokalnie(query):
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://allegrolokalnie.pl/oferty?phrase={q_enc}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200:
            log_debug(f"⚠️ Allegro Lokalnie status: {r.status_code}")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        new_count = 0
        items = soup.select("article[data-testid='listing-ad'], div[class*='mlc-itemcard'], article[class*='offer-card']")
        if not items:
            items = soup.select("a[href*='/oferta/']")

        for item in items:
            try:
                link = item if item.name == 'a' else item.find("a", href=lambda h: h and "/oferta/" in h)
                if not link:
                    continue
                item_url = link.get("href", "")
                if not item_url.startswith("http"):
                    item_url = f"https://allegrolokalnie.pl{item_url}"

                title_el = item.find(["h2", "h3", "span"], class_=re.compile(r"title|name|heading", re.I))
                title = title_el.get_text(strip=True) if title_el else item.get_text(separator=" ")[:60]

                price_text = item.get_text(separator=" ")
                price_match = re.search(r"(\d[\d\s]*(?:[,\.]\d{1,2})?)\s*zł", price_text)
                if not price_match:
                    continue
                price = float(price_match.group(1).replace(" ", "").replace(",", "."))

                if title and price:
                    if process_item(title.strip(), item_url, price, "ALLEGRO"):
                        new_count += 1
            except:
                continue

        log_debug(f"✅ Allegro Lokalnie [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd Allegro Lokalnie: {e}")

# ---------------------------------------------------------------------------
# FILTRY
# ---------------------------------------------------------------------------

CONSOLE_WORDS = [
    "vita", "psp", "konsola", "zestaw", "console",
    "3ds", "2ds", "dsi", "ds lite", "gameboy", "game boy", "gba",
    "nintendo", "playstation",
]

ACCESSORY_STANDALONE = [
    "ładowarka", "ladowarka", "kabel", "zasilacz", "adapter",
    "bateria", "etui", "obudowa", "rysik", "pokrowiec",
    "stojak", "uchwyt", "case", "ekran",
]

def has_console(title):
    t = title.lower()
    return any(w in t for w in CONSOLE_WORDS)

def is_standalone_accessory(title):
    t = title.lower()
    if any(x in t for x in ACCESSORY_STANDALONE):
        if not has_console(t):
            return True
    return False

def is_standalone_memory_card(title):
    t = title.lower()
    if any(x in t for x in ["karta pamięci", "memory card", "karta ms", "karta sd"]):
        if not has_console(t):
            return True
    return False

ACCESSORY_PHRASES = [
    r"\bsam(a|e|ego|emu|ą)?\s+(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|ekran|rysik|case|pokrowiec)",
    r"\b(tylko|sam(a)?)\s+(kabel|ładowark|zasilacz|adapter|bater|etui|obudow|rysik)",
    r"^(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|rysik|pokrowiec|case|stojak|uchwyt)\b",
]

def is_accessory_phrase(title):
    t = title.lower()
    for pattern in ACCESSORY_PHRASES:
        if re.search(pattern, t):
            return True
    return False

# ---------------------------------------------------------------------------
# GŁÓWNY FILTR
# ---------------------------------------------------------------------------
def is_interesting_item(title, price):
    t_f = title.lower()

    # --- TWARDE ŚMIECI ---
    
    trash_absolute = [
        
        # --- KLONY / CHIŃSZCZYZNA ---
        "r36s", "miyoo", "anbernic", "powkiddy",

        # --- MEDIA / DRUKI ---
        "bajka", "film", "dvd", "książka", "komiks",        # PL
        "bok", "serietidning", "comic",                      # SV
        "kniha", "časopis",                                  # CS
        "könyv", "képregény",                                # HU
        "kirja", "sarjakuva", "elokuva",                     # FI
        "bog", "tegneserie",                                 # DA
        "boek", "stripboek",                                 # NL
        "buch",                                              # DE
        "livre", "bande dessinée",                           # FR
        "libro", "fumetto",                                  # IT/ES

        # --- PŁYTA / PLAKAT ---
        "płyta", "plyta", "plakat", "ink",                  # PL
        "skiva", "affisch",                                  # SV
        "deska", "plakát",                                   # CS/SK
        "lemez", "poszter",                                  # HU
        "levy", "juliste",                                   # FI

        # --- SAMO PUDEŁKO / BEZ KONSOLI ---
        "samo pudełko", "samo pudelko", "samo opakowanie",  # PL
        "tylko opakowanie", "bez konsoli", "bez gry",
        "bara lådan", "endast lådan", "utan konsol", "utan spel", "tom låda", "tomt fodral",  # SV
        "jen krabice", "pouze krabice", "bez konzole", "bez hry", "prázdná krabice",          # CS
        "len škatuľa", "iba škatuľa", "bez konzoly", "prázdna škatuľa",                      # SK
        "csak doboz", "konzol nélkül", "játék nélkül", "üres doboz",                         # HU
        "pelkkä kotelo", "vain kotelo", "ilman konsolia", "ilman peliä", "tyhjä kotelo",      # FI
        "kun kassen", "uden konsol", "uden spil", "tom kasse",                               # DA
        "alleen doos", "zonder console", "zonder spel", "lege doos",                         # NL
        "nur hülle", "ohne konsole", "ohne spiel", "leere hülle", "leere box",               # DE
        "boîte vide", "sans console", "sans jeu", "juste la boîte",                          # FR
        "solo scatola", "senza console", "senza gioco", "scatola vuota",                     # IT
        "empty box", "box only", "case only", "without console", "no console",               # EN
        "no game", "housing only", "faceplate",

        # --- OBUDOWY / SHELL ---
        "obudowa", "obudowa konsoli",                        # PL
        "shell", "replacement shell", "replacement housing", "console shell", "shell only",  # EN
        "acrylic shell",                                     # EN
        "skal", "hölje",                                     # SV
        "kryt", "pouzdro",                                   # CS
        "puzdro",                                            # SK
        "ház", "tok",                                        # HU
        "kuori",                                             # FI
        "hoes", "behuizing",                                 # NL
        "gehäuse",                                           # DE
        "coque", "boîtier",                                  # FR
        "scocca", "custodia",                                # IT

        # --- AKRYL / STOJAKI ---
        "akryl", "akrylowy stojak", "spelstall",             # PL/SV
        "acrylic", "acrylic stand", "acrylic case", "acrylic display",  # EN

        # --- AKCESORIA ELEKTRONICZNE ---
        "r4i", "r4", "bateria", "battery",

        # --- POKÉMON TCG: LUZEM / SINGLE ---
        "luźne karty", "luzne karty",                        # PL
        "pojedyncza karta", "pojedyncze karty",
        "karty pokemon", "karta pokemon",
        "pokemon karty", "karty z pokemon",
        "pojedynczy booster", "jeden booster", "1 booster",
        "lösa kort", "enskilt kort", "pokemon kort", "ett boosterpack", "enstaka kort", "löst kort",  # SV
        "volné karty", "jednotlivá karta", "jednotlivý booster",                                       # CS
        "voľné karty", "jednotlivý booster",                                                           # SK
        "egyes kártya", "loose kártyák", "pokemon kártyák", "egy booster", "egyedi booster",          # HU
        "yksittäinen kortti", "irralliset kortit", "pokemon kortit", "yksi boosteri", "yksittäinen boosteri",  # FI
        "løse kort", "enkelt kort", "en booster",                                                      # DA
        "losse kaarten", "enkele kaart", "pokemon kaarten", "één booster", "losse booster",           # NL
        "einzelne karte", "lose karten", "pokemon karten", "ein booster", "einzelner booster",        # DE
        "cartes seules", "carte seule", "cartes pokemon", "un booster", "booster unique",             # FR
        "carta singola", "carte singole", "carte pokemon", "booster singolo",                         # IT
        "single card", "loose cards", "pokemon cards bulk", "one booster", "1 booster pack",         # EN
        "single booster", "bulk cards", "common cards", "random cards", "card lot", "pokemon card",
    ]
    
    if any(x in t_f for x in trash_absolute):
        return False, "TRASH"

    # --- AKCESORIA STANDALONE ---
    if is_accessory_phrase(t_f):
        return False, "ACCESSORY"

    if is_standalone_accessory(t_f):
        return False, "ACCESSORY"

    # --- KARTA PAMIĘCI STANDALONE ---
    if is_standalone_memory_card(t_f):
        return False, "MEMORY_CARD"

    # --- FILTR POJEDYNCZEJ GRY ---
    has_game_word = bool(re.search(r'\b(gra|game)\b', t_f))
    has_console_word = any(x in t_f for x in [
        "konsola", "console", "boy", "gear", "station", "cube",
        "watch", "advance", "color", "dsi", "vita", "psp", "3ds", "2ds", "ds"
    ])
    has_set_word = any(x in t_f for x in [
        "zestaw", "lot", "komplet", "kilka", "zestaw gier", "+ gier",
        "gry", "games",
    ])

    if has_game_word and not has_console_word and not has_set_word:
        return False, "SINGLE_GAME"

    # --- KATEGORYZACJA ---
    cat = None

    # Pokémon TCG
    if "pokemon" in t_f or "pokémon" in t_f:
        if "first partner" in t_f:
            cat = "FIRST_PARTNER"
        elif any(x in t_f for x in ["etb", "elite trainer"]):
            cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "boosterbox"]):
            cat = "TCG_BB"
        elif any(x in t_f for x in ["bundle", "booster bundle"]):
            cat = "TCG_BUNDLE"
        elif any(x in t_f for x in ["kolekcja", "zestaw kart", "zestaw boosterów", "sealed"]):
            cat = "TCG_ETB"

    # Konsole
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f or "vita slim" in t_f or "ps vita 2000" in t_f:
            cat = "VITA"
        elif "psp" in t_f or "playstation portable" in t_f or "play station portable" in t_f:
            cat = "PSP"
        elif "new 3ds" in t_f or "new3ds" in t_f:
            cat = "3DS"
        elif "3ds" in t_f:
            cat = "3DS"
        elif "new 2ds" in t_f or "2ds xl" in t_f:
            cat = "2DS"
        elif "2ds" in t_f:
            cat = "2DS"
        elif any(x in t_f for x in ["nintendo ds", "nds", "ds lite", "ds xl", "dsi xl", "dsi"]):
            cat = "DS_OLD"
        elif "gba sp" in t_f or "game boy advance sp" in t_f:
            cat = "RETRO"
        elif "gameboy advance" in t_f or "game boy advance" in t_f or "gba" in t_f:
            cat = "RETRO"
        elif "game boy color" in t_f or "gameboy color" in t_f or "gbc" in t_f:
            cat = "RETRO"
        elif "game boy pocket" in t_f or "gameboy pocket" in t_f:
            cat = "RETRO"
        elif "game boy" in t_f or "gameboy" in t_f or "dmg" in t_f:
            cat = "RETRO"

    # --- SONY AUDIO & APPLE AUDIO ---
        if not cat:
            is_sony = "sony" in t_f
            is_phone = any(x in t_f for x in [
                "telefon", "smartfon", "smartphone", "phone", "mobile",
                "xperia", "android", "iphone",
                "komórkowy", "komorkowy",
                "mobilny", "mobiltelefon",
                "puhelin",
                "telefoon",
                "handy",
                "téléphone",
                "telefono",
            ])

            if is_sony and not is_phone and any(x in t_f for x in ["walkman", "wm-"]):
                cat = "WALKMAN"
            elif is_sony and not is_phone and any(x in t_f for x in ["discman", "d-e", "d-j", "d-ej", "d-ne", "d-nf", "d-nx", "cd player"]):
                cat = "DISCMAN"
            elif "ipod nano" in t_f or ("ipod" in t_f and "nano" in t_f):
                cat = "IPOD_NANO"

    if not cat:
        return False, "NO_CAT"

    # --- LIMITY CENOWE ---
    limits = {
        "PSP":           250,
        "VITA":          600,
        "3DS":           500,
        "2DS":           350,
        "DS_OLD":        170,
        "RETRO":         300,
        "TCG_ETB":       280,
        "TCG_BB":        650,
        "TCG_BUNDLE":    160,
        "FIRST_PARTNER": 150,
        "WALKMAN":       400,
        "DISCMAN":       100,
        "IPOD_NANO":     150,
    }

    if 30 < price <= limits.get(cat, 1000):
        return True, cat

    return False, "PRICE"

# ---------------------------------------------------------------------------
# DEDUPLIKACJA I WYSYŁKA
# ---------------------------------------------------------------------------
def process_item(title, url, price, src):
    global IS_FIRST_RUN

    clean_url = url.split("?")[0].rstrip("/")

    if clean_url in SENT_URLS:
        return False

    content_hash = hashlib.md5(f"{title[:40].lower().strip()}_{int(price)}".encode()).hexdigest()
    if content_hash in SENT_HASHES:
        return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:35]} ({price} zł) [{res}]")
        SENT_URLS.add(clean_url)
        SENT_HASHES.add(content_hash)
        return True

    return False

# ---------------------------------------------------------------------------
# ZAPYTANIA
# ---------------------------------------------------------------------------
QUERIES = [
    # PSP
    "psp konsola", "psp 1000", "psp 2000", "psp 3000",
    # PS Vita
    "ps vita", "ps vita slim",
    # 3DS / 2DS
    "nintendo 3ds", "new 3ds", "new 2ds xl", "nintendo 2ds",
    # DS klasyczne
    "nintendo ds konsola", "ds lite", "dsi konsola",
    # Game Boy
    "gameboy advance", "gba sp", "gameboy color", "game boy",
    # Pokémon TCG — tylko sealed produkty
    "pokemon etb", "pokemon elite trainer box",
    "pokemon booster box", "pokemon display",
    "pokemon bundle", "pokemon booster bundle",
    "first partner pack",
    "pokemon kolekcja sealed", "pokemon zestaw sealed",
    # Sony Audio
    "sony walkman", "walkman kaseta", "sony wm-",
    "sony discman", "discman cd",
    # Apple Audio
    "ipod nano",
]

# ---------------------------------------------------------------------------
# GŁÓWNA PĘTLA
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log_debug("🚀 SNIPER v43.3 | Walkman/Discman tylko Sony")

    vinted_init()

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            log_debug("🌙 Cisza nocna — pauza 30 min")
            time.sleep(1800)
            continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(2)
            scrape_vinted(q)
            time.sleep(3)
            scrape_allegro_lokalnie(q)
            time.sleep(random.randint(4, 8))

        if IS_FIRST_RUN:
            IS_FIRST_RUN = False
            log_debug("✅ Pierwszy przebieg zakończony — od teraz wysyłam powiadomienia")

        log_debug("💤 Koniec pętli. Przerwa 5 min.")
        time.sleep(300)