from curl_cffi import requests as curl_requests
import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os, json
import urllib.parse

try:
    import redis as redis_lib
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
HISTORY_FILE = "sent_history.txt"
REDIS_URL = os.getenv("REDIS_URL")

# --- REDIS ---
r_db = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        if REDIS_URL.startswith("rediss://"):
            r_db = redis_lib.from_url(
                REDIS_URL,
                decode_responses=True,
                ssl_cert_reqs=None
            )
        else:
            r_db = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r_db.ping()
        print("🚀 Redis aktywny (trwała pamięć)")
    except Exception as e:
        print(f"⚠️ Redis niedostępny: {e} — fallback na plik")
        r_db = None

# --- PAMIĘĆ LOKALNA ---
SENT_CACHE = set()
SENT_IDS = set()
IS_FIRST_RUN = True
VINTED_LAST_INIT = 0
VINTED_INIT_INTERVAL = 2 * 3600

if not r_db and os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                val = line.strip()
                if val:
                    SENT_CACHE.add(val)
    except: pass

# --- SESJE ---
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

def extract_olx_id(url):
    """Wyciąga ID ogłoszenia z URL OLX do deep linka."""
    match = re.search(r'-ID([a-zA-Z0-9]+)\.html', url)
    return match.group(1) if match else None

def send_telegram(msg, reply_markup=None):
    try:
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            timeout=15
        )
        return r.status_code == 200
    except: return False

def is_duplicate(clean_url, content_hash):
    key = f"{clean_url}_{content_hash}"
    if key in SENT_CACHE: return True
    if r_db:
        try:
            if r_db.exists(f"sent:{content_hash}"): return True
        except: pass
    return False

def save_to_memory(clean_url, content_hash):
    SENT_CACHE.add(f"{clean_url}_{content_hash}")
    if r_db:
        try:
            r_db.setex(f"sent:{content_hash}", 172800, clean_url)
        except: pass
    else:
        try:
            with open(HISTORY_FILE, "a") as f:
                f.write(f"{clean_url}\n")
        except: pass

# ---------------------------------------------------------------------------
# VINTED
# ---------------------------------------------------------------------------
def vinted_init():
    global VINTED_LAST_INIT
    try:
        log_debug("🔄 Inicjalizuję sesję Vinted...")
        chosen = random.choice(["chrome120", "chrome116", "safari15_5", "edge101"])
        VINTED_SESSION.impersonate = chosen
        VINTED_SESSION.cookies.clear()
        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        if r.status_code == 200:
            log_debug(f"✅ Sesja Vinted gotowa ({chosen})")
            VINTED_LAST_INIT = time.time()
            return True
        log_debug(f"💥 Vinted init: {r.status_code}")
        return False
    except Exception as e:
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def vinted_ensure():
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

def scrape_vinted(query):
    if not vinted_ensure(): return
    try:
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={urllib.parse.quote_plus(query)}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code in [401, 403]:
            log_debug(f"🔄 Vinted {r.status_code} [{query}] — reset...")
            time.sleep(random.uniform(10, 20))
            if vinted_init():
                r = VINTED_SESSION.get(url, timeout=20)
            else:
                return
        if r.status_code == 200:
            items = r.json().get("items", [])
            new_count = 0
            for item in items:
                item_id = str(item.get("id", ""))
                if item_id and item_id in SENT_IDS: continue
                title = item.get("title", "")
                p_raw = item.get("price", 0)
                price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED", item_id=item_id): new_count += 1
            log_debug(f"✅ Vinted [{query}]: {len(items)} ofert, {new_count} nowych")
        else:
            log_debug(f"⚠️ Vinted [{query}]: {r.status_code}")
    except Exception as e:
        log_debug(f"💥 Błąd Vinted [{query}]: {e}")

def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if not p_val: continue
                olx_id = f"olx_{o.get('id', '')}"
                if process_item(o['title'], o['url'], float(p_val), "OLX", item_id=olx_id): new_count += 1
            log_debug(f"✅ OLX [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd OLX: {e}")

def scrape_allegro_lokalnie(query):
    try:
        url = f"https://allegrolokalnie.pl/oferty?phrase={urllib.parse.quote_plus(query)}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200: return
        soup = BeautifulSoup(r.text, "html.parser")
        new_count = 0
        items = soup.select("article[data-testid='listing-ad'], div[class*='mlc-itemcard'], article[class*='offer-card']")
        for item in items:
            try:
                link = item if item.name == 'a' else item.find("a", href=lambda h: h and "/oferta/" in h)
                if not link: continue
                item_url = link.get("href", "")
                if not item_url.startswith("http"): item_url = f"https://allegrolokalnie.pl{item_url}"
                title_el = item.find(["h2", "h3", "span"], class_=re.compile(r"title|name|heading", re.I))
                title = title_el.get_text(strip=True) if title_el else item.get_text(separator=" ")[:60]
                price_match = re.search(r"(\d[\d\s]*(?:[,\.]\d{1,2})?)\s*zł", item.get_text(separator=" "))
                if price_match and process_item(title.strip(), item_url, float(price_match.group(1).replace(" ", "").replace(",", ".")), "ALLEGRO"):
                    new_count += 1
            except: continue
        log_debug(f"✅ Allegro [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd Allegro: {e}")

# ---------------------------------------------------------------------------
# FILTRY
# ---------------------------------------------------------------------------

# Miotła na śmieci z wyszukiwarek — omijają logowanie całkowicie
JUNK_RE = re.compile(r"""
    \b(
        ps[1-5]|playstation\s*[1-5]|xbox|xbox\s*360|xbox\s*one|xbox\s*series|
        wii|wii\s*u|switch|nintendo\s*switch|
        tur|ładowacz|ciągnik|koparka|silnik|maszyny\s*rolnicze|skrzynia\s*biegów|
        klacz|koń|
        pks|pck|pkp|bilet|bilety|kalendarz|kalendarzyk|
        iveco|mercedes|audi|bmw|suzuki\s*dl|land\s*rover|
        pc\s*cd|gry\s*pc|gra\s*pc
    )\b
""", re.I | re.VERBOSE)

PARTS_RE = re.compile(r"""
    (
        # Ekrany
        \bekran\b|\bscreen\b|\blcd\b|
        # Obudowy — prefix match (obudowa/obudowie/obudowy itd.)
        \bobudow|\bshell\b|\bhousing\b|\bcasing\b|\bfaceplate\b|
        # Rysiki
        \brysik\b|\bstylus\b|
        # Kable i zasilanie — prefix match + wielojęzyczne
        \bkabel\b|\bcable\b|\bprzewód\b|\bładowark|\bcharger\b|\bzasilacz\b|
        \bpower\s*supply\b|
        \bpunjač\b|\bnabíječ|\bnabíjačk|\blader\b|\bladegerät\b|  # serbski/czeski/słowacki/szwedzki/niemiecki
        \bcharger\b|\boplader\b|\blaturi\b|\btöltő\b|              # duński/rumuński/węgierski
        # Baterie — prefix match
        \bbateria\b|\bbattery\b|\bakumulator\b|
        # Torby i etui — prefix match
        \betui\b|\bpokrowiec\b|\btorb|\bbag\b|
        # Ochrona ekranu — prefix match
        \bszkło\s*hartowane\b|\bscreen\s*protector\b|\bfolia\b|
        # Elektronika wewnętrzna
        \bprzyciski\b|\bbuttons\b|\btrigger\b|\bgłośnik\b|\bspeaker\b|
        \btaśm|\bribbon\b|\bflex\b|\bobiektyw\b|\blens\b|
        # Audio akcesoria
        \bremote\s*control\b|\bpilot\b|\btelecommand\b|
        \bheadphones?\b|\bsłuchawk|\bearphones?\b|
        # TCG akcesoria — prefix match
        \bakryl\b|\bacrylic\b|\bgablotk|\bcard\s*case\b|\bcard\s*holder\b|
        \bsleeve\b|\bkoszulk|\bcoin|
        # Dyski MiniDisc (bez odtwarzacza) — prefix match
        \brecordable\s*md\b|\bblank\s*md\b|\bkaseta\s*md|\btaśma\s*md\b|
        \bminidisc\s*74\b|\bminidisc\s*80\b|\bmd\s*74\b|\bmd\s*80\b|
        \brecordable\b.*\bmd\b
    )
""", re.I | re.VERBOSE)

ADAPTER_MAIN_RE = re.compile(r"^(adapter|zasilacz|ac\s*adapter|power\s*adapter|przejściówka)\b", re.I)

PHONE_WALKMAN_RE = re.compile(r"\b(ericsson|xperia|nokia|samsung|iphone|motorola|htc|huawei|xiaomi)\b", re.I)

CLONE_RE = re.compile(r"\b(r36s?|miyoo|anbernic|retroid|trimui|powkiddy|rg\d+|rk\d+|rgb\d+|rgxx|rg cube|gameforce|chi\s*li|pxp|sup\s*game|retromini|bittboy|pocketgo)\b", re.I)
DICTAPHONE_RE = re.compile(r"\b(dyktafon|voice\s*recorder|tcm[-\s]\d|icd[-\s]|nagrywarka|voice\s*memo|dictaphone|diktafon|sanelukone)\b", re.I)
JAPANESE_RE = re.compile(r"\b(japanese|japan|japoński|japońskie|jp\s*version|jp\s*ed|japanese\s*ed|nihon|nippon|\bjp\b(?=\s*(ver|ed|version|edition)))\b", re.I)

BUNDLE_RE = re.compile(r"""
    \b(
        # Polski
        bundle|zestaw|komplet|lot|
        # Angielski
        x[2-9]|[2-9]\s*x\b|
        \d+\s*gier|\d+\s*gry|\d+\s*sztuk|\d+\s*szt\b|
        \d+\s*games?|
        # Słowiańskie
        hry\s*\d|\d+\s*hry|                  # czeski/słowacki
        gry\s*na|gry\s*do|kilka\s*gier|par[eę]\s*gier|
        # Inne języki
        \d+\s*spel\b|\d+\s*spiele?\b|        # szwedzki/niemiecki
        \d+\s*jeux?\b|                       # francuski
        \d+\s*juegos?\b|                     # hiszpański
        \d+\s*giochi?\b|                     # włoski
        \d+\s*igr[aei]\b|                    # rosyjski/serbski
        \d+\s*joc[uri]*\b|                   # rumuński
        \d+\s*játék\b|                       # węgierski
        \d+\s*žaidim\w+|                     # litewski
        paketti\b|pakket\b|                  # fiński/niderlandzki
        pack(?!\s*art)
    )\b
""", re.I | re.VERBOSE)

CONSOLE_MAIN_RE = re.compile(r"""
    \b(
        # Polski
        konsola|
        # Angielski
        console|handheld|
        playstation\s*portable|              # PSP pełna nazwa
        # Inne języki europejskie (szwedzki, fiński, czeski, słowacki, rumuński, węgierski, litewski, łotewski)
        konsol\b|konsolę|konsoli|            # szwedzki/nordycki "konsol"
        konzol\b|konzole\b|konzolę\b|        # czeski/słowacki
        consolă\b|consolă\b|                 # rumuński
        konzole\b|spielkonsole\b|            # niemiecki
        pelikonsoli\b|pelikonsole\b|         # fiński
        spelkonsol\b|                        # szwedzki
        mängukonsool\b|                      # estoński
        # PSP modele
        psp\s*(fat|slim|go|street|1000|2000|3000|value\s*pack)|
        psp[-\s]?\d{4}|                      # PSP-1004, PSP 2004, PSP3004
        psp[-\s]?e\d{4}|                     # PSP-E1004, PSP E1004
        psp[-\s]?\d{4}[a-z]|                 # PSP-1004K itd
        sony\s*e\d{4}|                       # SonyE1004 bez spacji
        # PS Vita
        ps\s*vita\b|psvita\b|playstation\s*vita\b|  # samo PS Vita
        pch-?\d{4}|
        vita\s*(slim|fat|1000|2000|pch|oled|tv)|
        # 3DS/DS
        new\s*3ds|old\s*3ds|3ds\s*xl|3ds\s*ll|2ds\s*xl|
        nintendo\s*3ds|nintendo\s*2ds|
        nintendo\s*ds\b|                     # samo Nintendo DS (fat)
        ds\s*lite|dsi\s*xl|\bdsi\b|
        \bdsi\s*(black|white|red|blue|pink|purple|yellow|green|32gb|16gb|cfw)|
        # Game Boy — z i bez spacji (Gameboy/Game Boy)
        game\s*boy\s*(advance\s*sp|color|pocket|light|original|classic)|
        gameboy\s*(color|advance|sp|pocket|light|classic)|
        gba\s*sp|\bgbc\b|\bgba\b             # skróty
    )\b
""", re.I | re.VERBOSE)

TCG_EMPTY_RE = re.compile(r"""
    \b(
        # Puste opakowanie — wielojęzyczne
        empty|pusty|puste|pusta|puszka|
        tomma?\b|                            # szwedzki: tomma/tom = pusty
        tyhj[äa]\b|tyhjä\b|                 # fiński: tyhjä = pusty
        leer\b|leere\b|                      # niemiecki
        prázdný|prázdné|prazdny|            # czeski/słowacki
        ures\b|üres\b|                       # węgierski
        golos\b|                             # rosyjski/ukraiński
        vuota\b|vuote\b|                     # włoski
        vacía\b|vacío\b|                     # hiszpański
        vide\b|vides\b|                      # francuski
        tom\s*boks|tomt\b|                   # norweski/duński: tom = pusty
        # Otwarte/używane — wielojęzyczne
        used\s*tin|empty\s*tin|
        avattuja\b|avattu\b|                 # fiński: avattuja = otwarte
        opened?\b|otwart\w+|                 # angielski/polski
        ouverte?\b|                          # francuski: ouverte = otwarte
        geöffnet\b|                          # niemiecki: geöffnet = otwarte
        aperto\b|                            # włoski: aperto = otwarte
        abierto\b|                           # hiszpański: abierto = otwarte
        otevřen\w+|                          # czeski: otevřená = otwarta
        # Luźne karty
        loose|luzem|luzne|luźne|
        single|singles|pojedyncz|
        # Holo/rare luźne
        holo\s*rare|reverse\s*holo|
        # Języki — blokada nieangielskich wersji
        chinese|korean|chinois|coréen|chinesisch|koreanisch|
        # Bulk — zbiorcze zestawy luźnych kart
        bulk\b|
        # Akryl — gablotki/osłony
        akryl\w*|acrylic|
        # Mystery — losowe zestawy
        mystery\b|
        # Liczby kart — sygnał luźnych
        \d+\s*cards?\b|
        \d+\s*kort\w*\b|                     # szwedzki/duński: kort = karta
        \d+\s*kortti\w*\b|                   # fiński: korttia = kart
        \d+\s*kart\w*\b|                     # polski: kart/karty
        cards?\s*lot|cards?\s*bundle|
        # Kolekcje luźnych
        mixed\s*collection|mixed\s*set|
        card\s*collection|
        \bkart\b
    )\b
""", re.I | re.VERBOSE)

def classify_tcg(t_f):
    if "pokemon" not in t_f and "pokémon" not in t_f:
        return None
    if JAPANESE_RE.search(t_f):
        return None

    if TCG_EMPTY_RE.search(t_f):
        return None

    sealed_keywords = [
        "etb", "elite trainer", "booster box", "display", "bundle",
        "tin", "blister", "first partner", "collection box",
        "premium collection", "booster pack", "booster",
    ]
    if not any(k in t_f for k in sealed_keywords):
        return None
    if "etb" in t_f or "elite trainer" in t_f:
        return ("TCG_ETB", 280)
    if "booster box" in t_f or ("display" in t_f and "pokemon" in t_f):
        return ("TCG_BOX", 600)
    if "first partner" in t_f:
        return ("TCG_FIRST_PARTNER", 150)
    if "bundle" in t_f:
        return ("TCG_BUNDLE", 150)
    if any(x in t_f for x in ["mini tin", "mini-tin", "small tin"]):
        return ("TCG_MINI_TIN", 50)
    if "tin" in t_f:
        return ("TCG_TIN", 100)
    if "blister" in t_f:
        return ("TCG_BLISTER", 70)
    if "booster pack" in t_f or (
        "booster" in t_f and not any(x in t_f for x in ["box", "bundle", "display"])
    ):
        return ("TCG_BOOSTER", 25)
    return None

def is_interesting_item(title, price):
    t_f = title.lower()

    if JUNK_RE.search(t_f):
        return False, "JUNK_EXCLUDE"

    if CLONE_RE.search(t_f):
        return False, "CLONE"

    if "pokemon" in t_f or "pokémon" in t_f:
        tcg = classify_tcg(t_f)
        if tcg:
            subcat, max_price = tcg
            if 10 <= price <= max_price:
                return True, subcat
            return False, "PRICE"
        has_console = any(c in t_f for c in [
            "vita", "psp", "3ds", "ds lite", "dsi", "nintendo ds",
            "gameboy", "gba", "gbc", "game boy"
        ])
        if not has_console:
            return False, "PKMN_JUNK"

    GAME_SIGNAL_RE = re.compile(r"""
        \b(
            ^gra\s+|                             # tytuł zaczyna się od "gra"
            \bgra\s+na\s+|                       # "gra na PSP/DS/GBA"
            \bna\s+(nintendo|psp|ds|gba|gbc|vita)\b|  # "na nintendo/psp/ds"
            \bgame\s+for\s+|                     # "game for PSP"
            \bjoc\s+|jogo\s+|juego\s+|jeu\s+|   # rumuński/port/hiszp/franc "gra"
            \bspel\s+till\s+|spil\s+til\s+       # szwedzki/duński "gra na"
        )
    """, re.I | re.VERBOSE)

    is_game_signal = bool(GAME_SIGNAL_RE.search(t_f))

    SCREEN_RE = re.compile(r"\b(ekran|screen|lcd|ecran|display\s*(ips|oled|tft|lcd)?|wyświetlacz)\b", re.I)
    if SCREEN_RE.search(t_f):
        return False, "PART"

    has_konsola_in_title = bool(CONSOLE_MAIN_RE.search(t_f)) or "konsola" in t_f or "console" in t_f
    has_bundle_signal = bool(BUNDLE_RE.search(t_f))

    if not has_konsola_in_title and not has_bundle_signal:
        if PARTS_RE.search(t_f):
            return False, "PART"
        if ADAPTER_MAIN_RE.search(t_f):
            return False, "PART"
    elif not has_konsola_in_title and has_bundle_signal:
        if ADAPTER_MAIN_RE.search(t_f):
            return False, "PART"
    else:
        if ADAPTER_MAIN_RE.search(t_f):
            return False, "PART"

    hw_cat = None
    if "vita" in t_f: hw_cat = "VITA"
    elif any(x in t_f for x in ["psp", "playstation portable"]): hw_cat = "PSP"
    elif "3ds" in t_f: hw_cat = "3DS"
    elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): hw_cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): hw_cat = "RETRO"

    if hw_cat:
        if is_game_signal:
            if not has_bundle_signal:
                return False, "SINGLE_GAME"
        elif not has_konsola_in_title:
            if not has_bundle_signal:
                return False, "SINGLE_GAME"

    if not hw_cat:
        if any(x in t_f for x in ["walkman", "discman", "minidisc", "mini disc", "md player", "cd walkman"]):
            if DICTAPHONE_RE.search(t_f): return False, "DICTAPHONE"
            if PHONE_WALKMAN_RE.search(t_f): return False, "PHONE"
            if not any(x in t_f for x in ["sony", "aiwa"]):
                return False, "NOT_SONY"
            hw_cat = "WALKMAN"

    if not hw_cat: return False, "NO_CAT"

    limits = {
        "PSP":     (50, 200),
        "VITA":    (200, 500),
        "3DS":     (100, 500),
        "DS":      (50, 170),
        "RETRO":   (50, 250),
        "WALKMAN": (35, 100),
    }
    lo, hi = limits.get(hw_cat, (50, 1000))
    if lo <= price <= hi: return True, hw_cat
    return False, "PRICE"

# ---------------------------------------------------------------------------
# PROCESS ITEM
# ---------------------------------------------------------------------------
def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN

    if item_id and item_id in SENT_IDS: return False

    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower().strip()}_{int(price)}".encode()).hexdigest()

    if is_duplicate(clean_url, content_hash): return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`"

            if src == "OLX":
                olx_id = extract_olx_id(clean_url)
                keyboard = {"inline_keyboard": [[
                    {"text": "📱 Otwórz w aplikacji OLX", "url": f"olx://listing/{olx_id}" if olx_id else clean_url},
                    {"text": "🌐 Przeglądarka", "url": clean_url},
                ]]}
                send_telegram(msg, reply_markup=keyboard)
            else:
                msg += f"\n🔗 [LINK]({clean_url})"
                send_telegram(msg)

            log_debug(f"🎯 WYSŁANO: {title[:50]} ({price} zł) [{res}]")
        if item_id: SENT_IDS.add(item_id)
        save_to_memory(clean_url, content_hash)
        return True
    else:
        if res != "JUNK_EXCLUDE":
            log_debug(f"⛔ [{res}] {title[:50]} ({price} zł)")
    return False

# ---------------------------------------------------------------------------
# PĘTLA GŁÓWNA
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log_debug("🚀 SNIPER v69.1 | OLX Deep Link")
    vinted_init()

    Q_V = [
        "psp fat", "psp slim", "psp go", "psp street", "psp konsola",
        "psp 1000", "psp 1001", "psp 1004",
        "psp 2000", "psp 2001", "psp 2004",
        "psp 3000", "psp 3001", "psp 3004",
        "psp e1000", "psp e1004",
        "ps vita slim", "ps vita konsola",
        "pch-1000", "pch-1001", "pch-1004",
        "pch-1100",
        "pch-2000", "pch-2001", "pch-2004",
        "new 3ds xl", "new 3ds ll", "old 3ds xl", "nintendo 3ds xl", "nintendo 3ds ll",
        "nintendo ds lite", "nintendo dsi", "nintendo dsi xl",
        "nintendo ds",
        "game boy advance sp", "game boy advance", "game boy color",
        "game boy pocket", "game boy light", "game boy classic",
        "gba sp", "gameboy color", "gameboy advance",
        "gameboy color", "gameboy pocket", "gameboy light",
        "pokemon etb", "pokemon elite trainer box",
        "pokemon booster box", "pokemon booster bundle",
        "pokemon tin", "pokemon mini tin", "pokemon blister",
        "sony walkman", "sony discman", "sony minidisc",
    ]
    Q_PL = [
        "psp fat", "psp slim", "psp go", "psp street",
        "psp 1004", "psp 2004", "psp 3004", "psp e1004",
        "ps vita konsola", "ps vita slim",
        "pch-1004", "pch-2004",
        "nintendo 3ds xl", "new 3ds xl",
        "nintendo ds lite", "nintendo dsi", "nintendo ds",
        "gameboy advance sp", "gameboy advance", "gameboy color",
        "game boy pocket", "game boy classic", "gameboy pocket",
        "pokemon etb", "pokemon booster box",
        "sony walkman", "sony discman",
    ]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800)
            continue

        v_list = Q_V.copy()
        pl_list = Q_PL.copy()
        random.shuffle(v_list)
        random.shuffle(pl_list)

        for q_v in v_list:
            scrape_vinted(q_v)
            time.sleep(random.uniform(4, 8))

        for q_pl in pl_list:
            scrape_olx(q_pl)
            time.sleep(random.uniform(2, 4))
            scrape_allegro_lokalnie(q_pl)
            time.sleep(random.uniform(3, 5))

        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 5 min.")
        time.sleep(300)