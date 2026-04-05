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
    "spelkonsol", "konsoll",
    "herní konzole", "konzole", "konzola",
    "játékkonzol", "konzol",
    "pelikonsoli", "konsoli",
    "spelcomputer",
    "spielkonsole", "konsole",
    "console de jeu", "console di gioco",
]

ACCESSORY_STANDALONE = [
    # PL
    "ładowarka", "ladowarka", "kabel", "zasilacz", "adapter",
    "etui", "rysik", "pokrowiec", "stojak", "uchwyt", "case", "ekran",
    # EN
    "charger", "charging cable", "power supply", "power adapter",
    "stylus", "carry case", "stand", "grip",
    # SV
    "laddare", "nätaggregat", "fodral", "skärm",
    # CS
    "nabíječka", "napájení", "pouzdro",
    # SK
    "nabíjačka", "napájanie", "puzdro",
    # HU
    "töltő", "töltőkábel", "kijelző",
    # FI
    "laturi", "kaapeli", "kotelo", "näyttö",
    # DA
    "oplader", "skærm",
    # NL
    "oplader", "voeding", "hoesje",
    # DE
    "ladekabel", "ladegerät", "netzteil", "tasche",
    # FR
    "chargeur", "câble", "alimentation", "étui", "stylet",
    # IT
    "caricatore", "cavo", "alimentatore", "custodia",
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
    if any(x in t for x in [
        "karta pamięci", "memory card", "memory stick", "karta ms", "karta sd",
        "minneskort",
        "paměťová karta",
        "pamäťová karta",
        "memóriakártya",
        "muistikortti",
        "geheugenkaart",
        "speicherkarte",
        "carte mémoire",
        "scheda di memoria",
    ]):
        if not has_console(t):
            return True
    return False

ACCESSORY_PHRASES = [
    # PL
    r"\bsam(a|e|ego|emu|ą)?\s+(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|ekran|rysik|case|pokrowiec)",
    r"\b(tylko|sam(a)?)\s+(kabel|ładowark|zasilacz|adapter|bater|etui|obudow|rysik)",
    r"^(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|rysik|pokrowiec|case|stojak|uchwyt)\b",
    # EN
    r"^(charger|cable|power supply|power adapter|stylus|carry case|stand|grip)\b",
    r"\b(only|just)\s+(the\s+)?(charger|cable|adapter|stylus|case|stand)",
    r"\b(charger|cable)\s+only\b",
    # SV
    r"^(laddare|kabel|nätaggregat|fodral|skärm)\b",
    r"\bendast\s+(laddare|kabel|adapter|fodral)",
    # CS
    r"^(nabíječka|kabel|napájení|pouzdro)\b",
    r"\bjen\s+(nabíječka|kabel|adapter)",
    # SK
    r"^(nabíjačka|kábel|napájanie|puzdro)\b",
    # HU
    r"^(töltő|töltőkábel|adapter|kijelző)\b",
    r"\bcsak\s+(töltő|kábel|adapter)",
    # FI
    r"^(laturi|kaapeli|kotelo|näyttö)\b",
    r"\bvain\s+(laturi|kaapeli|adapter)",
    # DE
    r"^(ladekabel|ladegerät|netzteil|tasche)\b",
    r"\bnur\s+(ladekabel|ladegerät|netzteil|kabel|adapter)",
    # FR
    r"^(chargeur|câble|alimentation|étui|stylet)\b",
    r"\bseulement\s+(le\s+)?(chargeur|câble|adaptateur)",
    # IT
    r"^(caricatore|cavo|alimentatore|custodia)\b",
    r"\bsolo\s+(il\s+)?(caricatore|cavo|adattatore)",
    # NL
    r"^(oplader|kabel|voeding|hoesje)\b",
    r"\balleen\s+(de\s+)?(oplader|kabel|adapter)",
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

    trash_absolute = [
        # --- KLONY / CHIŃSZCZYZNA ---
        "r36s", "miyoo", "anbernic", "powkiddy",

        # --- UBRANIA / MERCH ---
        "koszulka", "bluza", "t-shirt", "tshirt", "bluzka",
        "sweatshirt", "hoodie", "shirt", "clothing", "clothes",
        "czapka", "skarpety", "socks",

        # --- AKCESORIA EKRANOWE ---
        "szkło hartowane", "szklo hartowane", "tempered glass",
        "screen protector", "folia ochronna", "folia na ekran",
        "glass screen", "protective glass",

        # --- MEDIA / DRUKI ---
        "bajka", "dvd", "książka", "komiks",
        "serietidning", "comic",
        "kniha", "časopis",
        "könyv", "képregény",
        "kirja", "sarjakuva", "elokuva",
        "bog", "tegneserie",
        "boek", "stripboek",
        "buch",
        "livre", "bande dessinée",
        "libro", "fumetto",

        # --- PŁYTA / PLAKAT ---
        "płyta", "plyta", "plakat", "ink",
        "skiva", "affisch",
        "deska", "plakát",
        "lemez", "poszter",
        "levy", "juliste",

        # --- SAMO PUDEŁKO / BEZ KONSOLI ---
        "samo pudełko", "samo pudelko", "samo opakowanie",
        "tylko opakowanie", "bez konsoli", "bez gry",
        "bara lådan", "utan konsol", "utan spel", "tom låda",
        "jen krabice", "pouze krabice", "bez konzole", "bez hry", "prázdná krabice",
        "len škatuľa", "iba škatuľa", "bez konzoly", "prázdna škatuľa",
        "csak doboz", "konzol nélkül", "játék nélkül", "üres doboz",
        "pelkkä kotelo", "ilman konsolia", "ilman peliä", "tyhjä kotelo",
        "uden konsol", "uden spil", "tom kasse",
        "zonder console", "zonder spel", "lege doos",
        "ohne konsole", "ohne spiel", "leere hülle", "leere box",
        "boîte vide", "sans console", "sans jeu",
        "senza console", "senza gioco", "scatola vuota",
        "empty box", "box only", "without console", "no console", "no game",
        "housing only", "faceplate",

        # --- OBUDOWY / SHELL ---
        "obudowa", "obudowa konsoli",
        "replacement shell", "replacement housing", "shell only",
        "acrylic shell",
        "hölje",
        "kryt",
        "puzdro",
        "ház",
        "kuori",
        "behuizing",
        "gehäuse",
        "boîtier",
        "scocca",

        # --- AKRYL / STOJAKI ---
        "akryl", "akrylowy stojak", "spelstall",
        "acrylic stand", "acrylic case", "acrylic display",

        # --- AKCESORIA ELEKTRONICZNE ---
        "r4i", "r4", "bateria", "battery", "w595",

        # --- POKÉMON TCG: LUZEM / SINGLE ---
        "luźne karty", "luzne karty",
        "pojedyncza karta", "pojedyncze karty",
        "karty pokemon", "karta pokemon",
        "pokemon karty", "karty z pokemon",
        "pojedynczy booster", "jeden booster", "1 booster",
        "lösa kort", "enskilt kort", "pokemon kort", "enstaka kort",
        "volné karty", "jednotlivá karta", "jednotlivý booster",
        "voľné karty", "jednotlivý booster",
        "egyes kártya", "pokemon kártyák", "egy booster", "egyedi booster",
        "yksittäinen kortti", "irralliset kortit", "pokemon kortit", "yksi boosteri",
        "løse kort", "enkelt kort",
        "losse kaarten", "enkele kaart", "pokemon kaarten", "losse booster",
        "einzelne karte", "lose karten", "pokemon karten", "einzelner booster",
        "cartes seules", "carte seule", "cartes pokemon", "booster unique",
        "carta singola", "carte singole", "carte pokemon", "booster singolo",
        "single card", "loose cards", "pokemon cards bulk", "1 booster pack",
        "single booster", "bulk cards", "common cards", "random cards", "card lot", "pokemon card",
    ]
    if any(x in t_f for x in trash_absolute):
        return False, "TRASH"

    if is_accessory_phrase(t_f):
        return False, "ACCESSORY"

    if is_standalone_accessory(t_f):
        return False, "ACCESSORY"

    if is_standalone_memory_card(t_f):
        return False, "MEMORY_CARD"

    # --- FILTR POJEDYNCZEJ GRY ---
    has_game_word = bool(re.search(r'\b(gra|game|spel|hra|játék|peli)\b', t_f))
    has_console_word = any(x in t_f for x in [
        "konsola", "console", "boy", "gear", "station", "cube",
        "watch", "advance", "color", "dsi", "vita", "psp", "3ds", "2ds", "ds",
        "spelkonsol", "konzole", "konzola", "konzol", "pelikonsoli", "spielkonsole",
    ])
    has_set_word = any(x in t_f for x in [
        "zestaw", "lot", "komplet", "kilka", "gry", "games",
        "samling", "bundle", "collection", "sammlung", "collezione",
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
        elif any(x in t_f for x in [
            "kolekcja", "zestaw kart", "zestaw boosterów", "sealed",
            "samling", "collection", "collezione", "sammlung", "tin",
        ]):
            cat = "TCG_ETB"

    # Konsole
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f or "vita slim" in t_f:
            cat = "VITA"
        elif "psp" in t_f or "playstation portable" in t_f:
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
            "komórkowy", "komorkowy", "mobilny", "mobiltelefon",
            "puhelin", "telefoon", "handy", "téléphone", "telefono",
        ])
        if is_sony and not is_phone and any(x in t_f for x in ["walkman", "wm-"]):
            cat = "WALKMAN"
        elif is_sony and not is_phone and any(x in t_f for x in ["discman", "d-e", "d-j", "d-ej", "d-ne", "d-nf", "d-nx", "cd player"]):
            cat = "DISCMAN"
        elif "ipod nano" in t_f or ("ipod" in t_f and "nano" in t_f):
            cat = "IPOD_NANO"

    if not cat:
        return False, "NO_CAT"

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

# Vinted — wielojęzyczne, ale bez duplikatów (nazwy konsol są uniwersalne)
QUERIES_VINTED = [
    # PSP — "psp" działa wszędzie, modele też
    "psp", "psp 1000", "psp 2000", "psp 3000",
    # PS Vita — nazwa uniwersalna
    "ps vita", "ps vita slim", "psvita",
    # 3DS — nazwa universalna, tylko "new" może być w różnych językach
    "nintendo 3ds", "new 3ds", "new 3ds xl",
    # 2DS
    "nintendo 2ds", "new 2ds xl",
    # DS — "ds lite" i "dsi" są uniwersalne
    "nintendo ds", "ds lite", "nintendo dsi",
    # Game Boy — nazwy uniwersalne
    "game boy advance", "gba sp", "game boy color", "game boy pocket", "game boy",
    # Pokémon TCG — angielskie nazwy produktów są uniwersalne na całym Vinted
    "pokemon elite trainer box", "pokemon booster box",
    "pokemon etb", "pokemon bundle", "pokemon tin",
    "first partner pack", "pokemon collection box",
    # Sony Walkman — "sony walkman" uniwersalne, dodajemy tylko lokalne słowa kluczowe
    "sony walkman", "walkman cassette", "walkman kaseta",
    "sony wm-",
    # Sony Discman — "sony discman" uniwersalne
    "sony discman", "sony portable cd player",
    # iPod — uniwersalne
    "ipod nano",
]

# OLX + Allegro Lokalnie — tylko polski, bo to lokalne serwisy
QUERIES_PL = [
    # PSP
    "psp konsola", "psp 1000", "psp 2000", "psp 3000",
    # PS Vita
    "ps vita", "ps vita slim",
    # 3DS
    "nintendo 3ds", "new 3ds", "new 2ds xl", "nintendo 2ds",
    # DS
    "nintendo ds konsola", "ds lite", "dsi konsola",
    # Game Boy
    "gameboy advance", "gba sp", "gameboy color", "game boy",
    # Pokémon TCG
    "pokemon etb", "pokemon elite trainer box",
    "pokemon booster box", "pokemon display",
    "pokemon bundle", "first partner pack",
    "pokemon kolekcja sealed", "pokemon zestaw sealed",
    # Sony Audio
    "sony walkman", "walkman kaseta", "sony discman",
    # iPod
    "ipod nano",
]

# ---------------------------------------------------------------------------
# GŁÓWNA PĘTLA
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log_debug("🚀 SNIPER v43.7 | osobne listy zapytań, ~5 min cykl")

    vinted_init()

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            log_debug("🌙 Cisza nocna — pauza 30 min")
            time.sleep(1800)
            continue

        v_list = QUERIES_VINTED.copy()
        pl_list = QUERIES_PL.copy()
        random.shuffle(v_list)
        random.shuffle(pl_list)

        # Przeplatamy Vinted z OLX/Allegro żeby nie hammować jednego serwisu
        for i, q_v in enumerate(v_list):
            scrape_vinted(q_v)
            time.sleep(3)

            if i < len(pl_list):
                q_pl = pl_list[i]
                scrape_olx(q_pl)
                time.sleep(2)
                scrape_allegro_lokalnie(q_pl)
                time.sleep(random.randint(3, 5))

        # Pozostałe polskie zapytania których nie obsłużyliśmy w pętli powyżej
        for q_pl in pl_list[len(v_list):]:
            scrape_olx(q_pl)
            time.sleep(2)
            scrape_allegro_lokalnie(q_pl)
            time.sleep(random.randint(3, 5))

        if IS_FIRST_RUN:
            IS_FIRST_RUN = False
            log_debug("✅ Pierwszy przebieg zakończony — od teraz wysyłam powiadomienia")

        log_debug("💤 Koniec pętli. Przerwa 5 min.")
        time.sleep(300)