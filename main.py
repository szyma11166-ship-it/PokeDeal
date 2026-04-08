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
HISTORY_FILE = "sent_history.txt"

SENT_HASHES = set()
SENT_URLS = set()
SENT_IDS = set()
IS_FIRST_RUN = True
VINTED_LAST_INIT = 0
VINTED_INIT_INTERVAL = 2 * 3600

# Wczytanie Twardej Pamięci przy starcie
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                val = line.strip()
                if val:
                    SENT_URLS.add(val)
                    SENT_HASHES.add(val)
    except: pass

VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
VINTED_SESSION.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
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
    except: pass

def append_to_history(val):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{val}\n")

# ---------------------------------------------------------------------------
# INICJALIZACJA SESJI VINTED
# Krok 1: strona główna (DataDome ustawia pierwsze cookies)
# Krok 2: strona katalogu (DataDome weryfikuje i ustawia właściwe cookies)
# Krok 3: sprawdzenie czy datadome cookie jest obecne
# ---------------------------------------------------------------------------
def vinted_init():
    global VINTED_LAST_INIT
    browsers = ["chrome120", "chrome116", "safari15_5", "edge101"]
    chosen = random.choice(browsers)

    try:
        log_debug(f"🔄 Inicjalizuję sesję Vinted ({chosen})...")

        # Nowa sesja z losowym impersonation
        global VINTED_SESSION
        VINTED_SESSION = curl_requests.Session(impersonate=chosen)
        VINTED_SESSION.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

        # Krok 1: strona główna
        r1 = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        log_debug(f"  Step1 (homepage): {r1.status_code}")
        if r1.status_code != 200:
            log_debug(f"💥 Vinted init failed at homepage: {r1.status_code}")
            return False
        time.sleep(random.uniform(3, 6))

        # Krok 2: katalog — DataDome weryfikuje zachowanie przeglądarki
        VINTED_SESSION.headers.update({
            "Referer": "https://www.vinted.pl/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        })
        r2 = VINTED_SESSION.get("https://www.vinted.pl/catalog", timeout=20)
        log_debug(f"  Step2 (catalog): {r2.status_code}")
        if r2.status_code != 200:
            log_debug(f"💥 Vinted init failed at catalog: {r2.status_code}")
            return False
        time.sleep(random.uniform(2, 4))

        # Krok 3: sprawdź czy mamy datadome cookie
        dd_cookie = VINTED_SESSION.cookies.get("datadome")
        if not dd_cookie:
            log_debug("⚠️ Brak datadome cookie — sesja może być niestabilna")
        else:
            log_debug(f"✅ DataDome cookie present")

        # Ustaw nagłówki API po udanej inicjalizacji
        VINTED_SESSION.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9",
            "Referer": "https://www.vinted.pl/catalog",
            "Origin": "https://www.vinted.pl",
            "X-Requested-With": "XMLHttpRequest",
        })

        log_debug(f"✅ Sesja Vinted gotowa ({chosen})")
        VINTED_LAST_INIT = time.time()
        return True

    except Exception as e:
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def vinted_ensure():
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

# ---------------------------------------------------------------------------
# SCRAPERY
# ---------------------------------------------------------------------------
def scrape_vinted(query):
    if not vinted_ensure(): return
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={q_enc}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)

        if r.status_code in [401, 403]:
            log_debug(f"🔄 Vinted {r.status_code} na [{query}] — reset sesji...")
            # Dłuższe czekanie przed retry — DataDome rate limit
            time.sleep(random.uniform(30, 60))
            if vinted_init():
                time.sleep(random.uniform(3, 6))
                r = VINTED_SESSION.get(url, timeout=20)
            else:
                return

        if r.status_code == 200:
            items = r.json().get("items", [])
            new_count = 0
            for item in items:
                item_id = str(item.get("id", ""))
                if item_id and item_id in SENT_IDS:
                    continue
                title = item.get("title", "")
                p_raw = item.get("price", 0)
                price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED", item_id=item_id): new_count += 1
            log_debug(f"✅ Vinted [{query}]: {len(items)} ofert, {new_count} nowych")
        else:
            log_debug(f"⚠️ Vinted [{query}]: status {r.status_code}")

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
                if p_val and process_item(o['title'], o['url'], float(p_val), "OLX"): new_count += 1
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
        log_debug(f"✅ Allegro Lokalnie [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd Allegro: {e}")

# ---------------------------------------------------------------------------
# FILTRY
# ---------------------------------------------------------------------------

# --- CZĘŚCI, KOMPONENTY, AKCESORIA — blokada absolutna ---
PARTS_RE = re.compile(r"""
    \b(
        # Ekrany i optyka
        ekran|screen|lcd|display|obiektyw|lens|

        # Obudowy i części mechaniczne
        obudow|shell|housing|casing|faceplate|

        # Kable i zasilanie
        kabel|cable|przewód|ładowark|charger|zasilacz|
        power\s*supply|adapter|

        # Baterie
        bateria|battery|akumulator|

        # Akcesoria do noszenia/przechowywania
        etui|pokrowiec|torb|bag|

        # Narzędzia montażowe i rysiki
        rysik|stylus|

        # Ochrona ekranu
        szkło\s*hartowane|screen\s*protector|folia|

        # Elektronika wewnętrzna
        przyciski|buttons|trigger|głośnik|speaker|
        taśm|ribbon|flex|

        # Akcesoria Walkman/audio
        remote\s*control|pilot|telecommand|strap|carry\s*case|
        headphones?|słuchawk|earphones?|

        # Akryl i gablotki (Pokemon TCG)
        akryl|acrylic|gablotk|display\s*case|card\s*case|card\s*holder|
        sleeve|koszulk|

        # Dyski MiniDisc (bez odtwarzacza)
        \bmd\s*disc|\bminidisc\s*disc|recordable\s*md|blank\s*md|
        kaseta\s*md|taśma\s*md
    )\b
""", re.I | re.VERBOSE)

# --- KLONY I ŚMIECI ---
CLONE_RE = re.compile(r"\b(r36s|miyoo|anbernic|retroid|trimui|powkiddy|rg\d+|rk\d+)\b", re.I)

# --- DYKTAFONY ---
DICTAPHONE_RE = re.compile(r"\b(dyktafon|voice\s*recorder|tcm[-\s]\d|icd[-\s]|nagrywarka|voice\s*memo)\b", re.I)

# --- JAPOŃSKI TCG — blokada ---
JAPANESE_RE = re.compile(r"\b(japanese|japan|japoński|japońskie|jp\s*version|jp\s*ed|japanese\s*ed)\b", re.I)

# --- BUNDLE — whitelist zestawów 2+ sztuk ---
BUNDLE_RE = re.compile(r"""
    \b(
        bundle|zestaw|komplet|lot|
        x[2-9]|[2-9]\s*x\b|
        \d+\s*gier|\d+\s*gry|\d+\s*sztuk|\d+\s*szt\b|
        \d+\s*games?|
        hry\s*\d|\d+\s*hry|
        gry\s*na|gry\s*do|kilka\s*gier|pare\s*gier|parę\s*gier|
        pack(?!\s*art)   # "pack" ale nie "pack art"
    )\b
""", re.I | re.VERBOSE)

# --- KONSOLA JAKO GŁÓWNY PRZEDMIOT (nie gra) ---
# Jeśli tytuł zawiera te frazy — to oferta konsoli, nie gry
CONSOLE_MAIN_RE = re.compile(r"""
    \b(
        konsola|console|handheld|
        psp\s*(fat|slim|go|street|1000|2000|3000|value\s*pack)|
        vita\s*(slim|fat|1000|2000|pch)|
        new\s*3ds|old\s*3ds|3ds\s*xl|3ds\s*ll|2ds\s*xl|
        ds\s*lite|dsi\s*xl|
        game\s*boy\s*(advance\s*sp|color|pocket|light|original|classic)|
        gba\s*sp
    )\b
""", re.I | re.VERBOSE)

# ---------------------------------------------------------------------------
# TCG — KLASYFIKACJA POKEMON SEALED (tylko angielskie)
# ---------------------------------------------------------------------------
def classify_tcg(t_f):
    is_pkmn = "pokemon" in t_f or "pokémon" in t_f
    if not is_pkmn:
        return None

    # Blokada japońskich
    if JAPANESE_RE.search(t_f):
        return None

    # Musi zawierać sealed keyword — bez tego odrzuć
    sealed_keywords = [
        "etb", "elite trainer", "booster box", "display", "bundle",
        "tin", "blister", "first partner", "collection box",
        "premium collection", "booster pack", "booster",
    ]
    if not any(k in t_f for k in sealed_keywords):
        return None

    # ETB
    if "etb" in t_f or "elite trainer" in t_f:
        return ("TCG_ETB", 280)

    # Booster Box / Display (36 boosterów)
    if "booster box" in t_f or ("display" in t_f and "pokemon" in t_f):
        return ("TCG_BOX", 600)

    # First Partner Illustration Collection
    if "first partner" in t_f:
        return ("TCG_FIRST_PARTNER", 150)

    # Bundle (6 boosterów)
    if "bundle" in t_f:
        return ("TCG_BUNDLE", 150)

    # Mini Tin (2 boostery) — sprawdź przed zwykłym tinem
    if any(x in t_f for x in ["mini tin", "mini-tin", "small tin"]):
        return ("TCG_MINI_TIN", 50)

    # Tin (4 boostery)
    if "tin" in t_f:
        return ("TCG_TIN", 100)

    # Blister (3 boostery)
    if "blister" in t_f:
        return ("TCG_BLISTER", 70)

    # Pojedynczy booster pack (angielski)
    if "booster pack" in t_f or (
        "booster" in t_f and not any(x in t_f for x in ["box", "bundle", "display"])
    ):
        return ("TCG_BOOSTER", 25)

    return None

# ---------------------------------------------------------------------------
# GŁÓWNA FUNKCJA FILTROWANIA
# ---------------------------------------------------------------------------
def is_interesting_item(title, price):
    t_f = title.lower()

    # 1. Klony — absolutna blokada
    if CLONE_RE.search(t_f):
        return False, "CLONE"

    # 2. Części/akcesoria — absolutna blokada (bez wyjątków)
    if PARTS_RE.search(t_f):
        return False, "PART"

    # 3. Pokemon TCG
    if "pokemon" in t_f or "pokémon" in t_f:
        tcg = classify_tcg(t_f)
        if tcg:
            subcat, max_price = tcg
            if 10 <= price <= max_price:
                return True, subcat
            return False, "PRICE"
        # Pokemon ale nie sealed TCG — musi mieć nazwę konsoli żeby przejść
        has_console = any(c in t_f for c in [
            "vita", "psp", "3ds", "ds lite", "dsi", "nintendo ds",
            "gameboy", "gba", "gbc", "game boy"
        ])
        if not has_console:
            return False, "PKMN_JUNK"

    # 4. Blokada pojedynczych gier — LOGIKA ODWRÓCONA
    # Jeśli tytuł zawiera nazwę konsoli jako główny przedmiot (PSP Fat, DS Lite itp.)
    # to jest to oferta konsoli — przepuść do kategoryzacji
    # Jeśli NIE ma console_main ale jest w kategorii sprzętowej —
    # wymagamy BUNDLE_RE żeby przepuścić
    is_console_main = bool(CONSOLE_MAIN_RE.search(t_f))

    # Wykryj kategorię sprzętową
    hw_cat = None
    if "vita" in t_f: hw_cat = "VITA"
    elif "psp" in t_f: hw_cat = "PSP"
    elif "3ds" in t_f: hw_cat = "3DS"
    elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): hw_cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): hw_cat = "RETRO"

    if hw_cat and not is_console_main:
        # Tytuł ma nazwę platformy ale nie jest wyraźnie konsolą
        # Musi mieć bundle signal żeby przejść (zestaw gier)
        # LUB musi zawierać słowo "konsola"/"console"
        if "konsola" not in t_f and "console" not in t_f:
            if not BUNDLE_RE.search(t_f):
                return False, "SINGLE_GAME"

    # 5. Kategoryzacja
    cat = hw_cat  # użyj już wykrytej kategorii sprzętowej

    if not cat:
        if any(x in t_f for x in ["walkman", "discman", "minidisc", "mini disc", "md player", "cd walkman"]):
            if DICTAPHONE_RE.search(t_f): return False, "DICTAPHONE"
            cat = "WALKMAN"

    if not cat: return False, "NO_CAT"

    # 6. Limity cenowe
    limits = {
        "PSP":     (60, 250),
        "VITA":    (60, 600),
        "3DS":     (60, 500),
        "DS":      (60, 170),
        "RETRO":   (60, 300),
        "WALKMAN": (60, 100),
    }
    lo, hi = limits.get(cat, (60, 1000))
    if lo <= price <= hi: return True, cat
    return False, "PRICE"

# ---------------------------------------------------------------------------
# PROCESS ITEM
# ---------------------------------------------------------------------------
def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN
    if len(SENT_URLS) > 15000:
        SENT_URLS.clear()
        SENT_HASHES.clear()
        SENT_IDS.clear()

    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower().strip()}_{int(price)}".encode()).hexdigest()

    if item_id and item_id in SENT_IDS: return False
    if clean_url in SENT_URLS or content_hash in SENT_HASHES: return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:50]} ({price} zł) [{res}]")

        if item_id: SENT_IDS.add(item_id)
        SENT_URLS.add(clean_url)
        SENT_HASHES.add(content_hash)
        append_to_history(clean_url)
        return True
    else:
        log_debug(f"⛔ [{res}] {title[:50]} ({price} zł)")
    return False

# ---------------------------------------------------------------------------
# PĘTLA GŁÓWNA
# Vinted i OLX/Allegro mają osobne iteratory — eliminuje duplikaty OLX
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log_debug("🚀 SNIPER v48.0 | Vinted Fix + OLX Dedup + Game Filter + Acrylic/Walkman Block")
    vinted_init()

    Q_V = [
        "psp",
        "ps vita",
        "nintendo 3ds",
        "nintendo ds lite",
        "game boy advance",
        "game boy color",
        "pokemon etb",
        "pokemon booster box",
        "pokemon bundle",
        "pokemon tin",
        "pokemon blister",
        "sony walkman",
        "sony discman",
        "minidisc player",
    ]
    Q_PL = [
        "psp konsola",
        "ps vita konsola",
        "nintendo 3ds",
        "nintendo ds lite",
        "gameboy advance",
        "gameboy color",
        "pokemon etb",
        "pokemon booster box",
        "sony walkman",
        "sony discman",
    ]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800)
            continue

        v_list = Q_V.copy()
        pl_list = Q_PL.copy()
        random.shuffle(v_list)
        random.shuffle(pl_list)

        # Vinted — własna pętla
        for q_v in v_list:
            scrape_vinted(q_v)
            time.sleep(random.uniform(4, 8))

        # OLX + Allegro — osobna pętla, nie zależna od Vinted
        for q_pl in pl_list:
            scrape_olx(q_pl)
            time.sleep(random.uniform(2, 4))
            scrape_allegro_lokalnie(q_pl)
            time.sleep(random.uniform(3, 5))

        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 4 min.")
        time.sleep(240)