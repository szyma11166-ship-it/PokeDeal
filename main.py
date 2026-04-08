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
SENT_IDS = set()  # Vinted item ID deduplication
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
    except: pass

def append_to_history(val):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{val}\n")

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
        return False
    except Exception as e:
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def vinted_ensure():
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

# --- SCRAPERY ---
def scrape_vinted(query):
    if not vinted_ensure(): return
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={q_enc}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code in [401, 403]:
            log_debug(f"🔄 Vinted {r.status_code} — reset sesji...")
            time.sleep(random.uniform(10, 20))
            if vinted_init(): r = VINTED_SESSION.get(url, timeout=20)
            else: return
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
    except Exception as e: log_debug(f"💥 Błąd Vinted: {e}")

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
    except Exception as e: log_debug(f"💥 Błąd OLX: {e}")

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
    except Exception as e: log_debug(f"💥 Błąd Allegro: {e}")

# ---------------------------------------------------------------------------
# FILTRY
# ---------------------------------------------------------------------------

# --- KOMPONENTY I CZĘŚCI — blokada absolutna ---
# Nawet jeśli tytuł zawiera nazwę konsoli, te słowa = część = blokada
PARTS_RE = re.compile(r"""
    \b(
        ekran|screen|lcd|display|
        obudow|shell|housing|casing|faceplate|replacement\s*shell|
        rysik|stylus|
        kabel|cable|przewód|
        ładowark|charger|zasilacz|power\s*supply|adapter|
        bateria|battery|akumulator|
        etui|case|pokrowiec|torb|bag|
        stojak|stand|uchwyt|holder|
        szkło\s*hartowane|screen\s*protector|folia|
        przyciski|buttons|trigger|
        głośnik|speaker|
        taśm|ribbon|flex|
        obiektyw|lens
    )\b
""", re.I | re.VERBOSE)

# --- KLONY I ŚMIECI ---
CLONE_RE = re.compile(r"\b(r36s|miyoo|anbernic|retroid|trimui|powkiddy|rg\d+|rk\d+)\b", re.I)

# --- DYKTAFONY — blokada w kategorii Walkman ---
DICTAPHONE_RE = re.compile(r"\b(dyktafon|voice\s*recorder|tcm[-\s]\d|icd[-\s]|nagrywarka|voice\s*memo)\b", re.I)

# --- JĘZYK JAPOŃSKI — blokada dla TCG ---
JAPANESE_RE = re.compile(r"\b(japanese|japan|japoński|japońskie|jp\s*version|jp\s*ed|japanese\s*ed|holo\s*rare\s*jp)\b", re.I)

# --- BUNDLE KONSOL/GIER — whitelist (2+ sztuki) ---
# Tytuł musi zawierać wyraźny sygnał zestawu
BUNDLE_RE = re.compile(r"""
    \b(
        bundle|zestaw|komplet|lot|pack|
        x[2-9]|[2-9]\s*x\s*\w|
        \d+\s*gier|\d+\s*gry|\d+\s*sztuk|\d+\s*szt|
        hry\s*\d|\d+\s*hry|          # słowackie/czeskie "hry" = gry
        [2-9]\s*games?|
        collection(?!\s*illustration)  # "collection" ale nie "illustration collection" (to TCG)
    )\b
""", re.I | re.VERBOSE)

# ---------------------------------------------------------------------------
# TCG — KATEGORYZACJA POKEMON
# ---------------------------------------------------------------------------
# Podkategorie z osobnymi limitami cenowymi (tylko angielskie)
# Kolejność sprawdzania ma znaczenie — od najbardziej specyficznych

def classify_tcg(t_f):
    """
    Zwraca (podkategoria, max_cena) lub None jeśli nie pasuje.
    Tylko angielskie produkty.
    """
    is_pkmn = "pokemon" in t_f or "pokémon" in t_f
    if not is_pkmn:
        return None

    # Blokada japońskich
    if JAPANESE_RE.search(t_f):
        return None

    # Blokada luźnych kart (single cards)
    # Jeśli nie ma żadnego ze słów kluczowych produktu sealed — odrzuć
    sealed_keywords = [
        "etb", "elite trainer", "booster box", "display", "bundle",
        "tin", "blister", "first partner", "collection box", "premium collection",
        "booster pack", "booster"
    ]
    if not any(k in t_f for k in sealed_keywords):
        return None

    # --- ETB (Elite Trainer Box) ---
    if "etb" in t_f or "elite trainer" in t_f:
        return ("TCG_ETB", 280)

    # --- BOOSTER BOX / DISPLAY (36 boosterów) ---
    if "booster box" in t_f or "display" in t_f:
        return ("TCG_BOX", 600)

    # --- FIRST PARTNER ILLUSTRATION COLLECTION ---
    if "first partner" in t_f:
        return ("TCG_FIRST_PARTNER", 150)

    # --- BUNDLE (6 boosterów) ---
    if "bundle" in t_f:
        return ("TCG_BUNDLE", 150)

    # --- TIN (4 boostery) ---
    if "tin" in t_f:
        # Mini tin (2 boostery) — słowa kluczowe
        if any(x in t_f for x in ["mini tin", "mini-tin", "small tin"]):
            return ("TCG_MINI_TIN", 50)
        return ("TCG_TIN", 100)

    # --- BLISTER (3 boostery) ---
    if "blister" in t_f:
        return ("TCG_BLISTER", 70)

    # --- POJEDYNCZY BOOSTER PACK (angielski) ---
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

    # 1. ABSOLUTNA BLOKADA — klony
    if CLONE_RE.search(t_f):
        return False, "CLONE"

    # 2. ABSOLUTNA BLOKADA — części i komponenty
    #    Nie ma wyjątków — nawet "ekran do Nintendo DS" = część
    if PARTS_RE.search(t_f):
        return False, "PART"

    # 3. POKEMON TCG
    if "pokemon" in t_f or "pokémon" in t_f:
        tcg = classify_tcg(t_f)
        if tcg:
            subcat, max_price = tcg
            if 10 <= price <= max_price:
                return True, subcat
            return False, "PRICE"
        # Pokemon ale nie TCG sealed — sprawdź czy to konsola z grą pokemon
        # Jeśli nie ma słowa kluczowego konsoli — odrzuć
        if not any(c in t_f for c in ["vita", "psp", "3ds", "ds lite", "dsi", "nintendo ds", "gameboy", "gba", "gbc", "game boy"]):
            return False, "PKMN_JUNK"

    # 4. BLOKADA POJEDYNCZYCH GIER
    #    Przepuszczamy TYLKO jeśli jest wyraźny sygnał bundla 2+ sztuk
    #    Heurystyka: tytuł wygląda jak gra jeśli NIE zawiera nazwy konsoli jako głównego przedmiotu
    console_as_main = any(x in t_f for x in [
        "konsola", "console", "handheld", "zestaw z konsolą",
        "psp fat", "psp slim", "psp go", "psp street",
        "vita slim", "vita fat",
        "3ds xl", "3ds ll", "new 3ds", "old 3ds",
        "ds lite", "dsi xl",
        "game boy advance sp", "game boy color", "game boy pocket", "game boy light",
        "gba sp",
    ])

    # Jeśli w tytule jest nazwa konsoli ale nie jako główny przedmiot — sprawdź bundle
    game_signal = any(x in t_f for x in [
        "gra ", "grę ", "gry ", "grach ", "game ", "games ", "gioco", "spiel",
        "hry ", "hra ", "igra ",  # słowiańskie
        "ufc", "fifa", "pes ", "nfs", "gta", "cod ", "minecraft",
        "god of war", "uncharted", "tekken", "mortal", "street fighter",
        "assassin", "lego ", "harry potter", "star wars", "batman",
        "spider", "sonic", "mario", "zelda", "kirby", "pokemon ",
        "sims ", "singstar", "guitar hero", "tony hawk", "burnout",
        "ridge racer", "wipeout", "patapon", "lumines", "resistance",
        "killzone", "ratchet", "daxter", "crash", "jak and",
        "metal gear", "final fantasy", "dragon quest", "dragon ball",
        "naruto", "one piece", "bleach", "dbz",
        "pro cycling", "pro evolution", "need for speed", "call of duty",
        "medal of honor", "toy story", "ben 10",
    ])

    if game_signal and not console_as_main:
        if not BUNDLE_RE.search(t_f):
            return False, "SINGLE_GAME"

    # 5. KATEGORYZACJA SPRZĘTU
    cat = None
    if "vita" in t_f: cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif "3ds" in t_f: cat = "3DS"
    elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): cat = "RETRO"
    elif any(x in t_f for x in ["walkman", "discman", "minidisc", "mini disc", "md player", "cd walkman"]):
        if DICTAPHONE_RE.search(t_f): return False, "DICTAPHONE"
        cat = "WALKMAN"

    if not cat: return False, "NO_CAT"

    # 6. LIMITY CENOWE
    limits = {
        "PSP":     (60, 250),
        "VITA":    (60, 600),
        "3DS":     (60, 500),
        "DS":      (60, 170),
        "RETRO":   (60, 300),
        "WALKMAN": (60, 100),  # zmniejszony limit
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

    # Deduplication: ID (Vinted), URL (wszystkie źródła), content hash
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
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_debug("🚀 SNIPER v47.0 | Full Filter Overhaul | No Parts | TCG Subcats | No 2DS")
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
            time.sleep(1800); continue

        v_list = Q_V.copy(); pl_list = Q_PL.copy()
        random.shuffle(v_list); random.shuffle(pl_list)

        for i, q_v in enumerate(v_list):
            scrape_vinted(q_v)
            time.sleep(random.uniform(3, 6))
            if i < len(pl_list):
                scrape_olx(pl_list[i])
                time.sleep(random.uniform(2, 4))
                scrape_allegro_lokalnie(pl_list[i])
                time.sleep(random.uniform(3, 5))

        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 4 min.")
        time.sleep(240)