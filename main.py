from curl_cffi import requests as curl_requests
import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse
import redis

# --- KONFIGURACJA ŚRODOWISKA ---
os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- USTAWIENIA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
REDIS_URL = os.getenv("REDIS_URL")

# Inicjalizacja Redis (Pamięć na Railway)
r_db = None
if REDIS_URL:
    try:
        r_db = redis.from_url(REDIS_URL, decode_responses=True)
        print("🚀 Połączono z Redis (Trwała pamięć aktywna)")
    except:
        print("⚠️ Brak połączenia z Redis - bot będzie miał amnezję po restarcie")

# Lokalna pamięć pomocnicza
SENT_CACHE = set()
IS_FIRST_RUN = True
VINTED_LAST_INIT = 0
VINTED_INIT_INTERVAL = 2 * 3600

# Sesje
VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
OLX_SESSION = requests.Session()
ALLEGRO_SESSION = requests.Session()

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def send_telegram(msg):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15
        )
        return r.status_code == 200
    except: return False

# --- LOGIKA PAMIĘCI ---
def is_duplicate(url, content_hash):
    """Sprawdza czy oferta była już wysłana (w tej sesji lub w Redis)."""
    if f"{url}_{content_hash}" in SENT_CACHE: return True
    if r_db:
        if r_db.exists(f"sent:{content_hash}"): return True
    return False

def save_to_memory(url, content_hash):
    """Zapisuje ofertę do pamięci."""
    SENT_CACHE.add(f"{url}_{content_hash}")
    if r_db:
        # Pamięta ofertę przez 48 godzin
        r_db.setex(f"sent:{content_hash}", 172800, url)

# --- SCRAPERY ---
def vinted_init():
    global VINTED_LAST_INIT
    try:
        VINTED_SESSION.impersonate = random.choice(["chrome120", "chrome116", "safari15_5"])
        VINTED_SESSION.cookies.clear()
        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        if r.status_code == 200:
            VINTED_LAST_INIT = time.time()
            return True
    except: pass
    return False

def scrape_vinted(query):
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL: vinted_init()
    try:
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={urllib.parse.quote_plus(query)}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for item in items:
                title = item.get("title", "")
                p_raw = item.get("price", 0)
                price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                process_item(title, item_url, price, "VINTED")
    except: pass

def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if p_val: process_item(o['title'], o['url'], float(p_val), "OLX")
    except: pass

def scrape_allegro_lokalnie(query):
    try:
        url = f"https://allegrolokalnie.pl/oferty?phrase={urllib.parse.quote_plus(query)}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200: return
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article[data-testid='listing-ad'], div[class*='mlc-itemcard']"):
            try:
                link = item.find("a", href=lambda h: h and "/oferta/" in h)
                if not link: continue
                item_url = "https://allegrolokalnie.pl" + link.get("href") if not link.get("href").startswith("http") else link.get("href")
                title = item.find(["h2", "h3", "span"], class_=re.compile(r"title|name", re.I)).get_text(strip=True)
                price_match = re.search(r"(\d[\d\s]*(?:[,\.]\d{1,2})?)\s*zł", item.get_text())
                if price_match: process_item(title, item_url, float(price_match.group(1).replace(" ", "").replace(",", ".")), "ALLEGRO")
            except: continue
    except: pass

# --- FILTRY ---
POKEMON_GAMES = ["silver", "gold", "blue", "red", "yellow", "crystal", "ruby", "sapphire", "emerald", "fire red", "leaf green", "soul silver", "heart gold", "diamond", "pearl", "platinum", "black", "white", "black 2", "white 2", "x", "y", "sun", "moon"]
PARTS_RE = re.compile(r"\b(ekran|lcd|obudow|shell|rys|kabel|ładowark|zasilacz|bateria|etui|pokrowiec|szkło|przyciski|taśm|słuchawk|instrukcja|box|manual)\b", re.I)
FOLIA_RE = re.compile(r"(^folia\b|folia\s*ochronna)", re.I)
BUNDLE_RE = re.compile(r"\b(zestaw|komplet|bundle|lot|x\d|\d+x|\d+\s*gier|\d+\s*szt)\b", re.I)
CONSOLE_MAIN_RE = re.compile(r"\b(konsola|console|handheld|psp\b|vita|nintendo|3ds|2ds|dsi|gameboy|gba|gbc|sp)\b", re.I)

def classify_tcg(t_f):
    if not any(x in t_f for x in ["pokemon", "pokémon"]): return None
    if "etb" in t_f or "elite trainer" in t_f: return ("TCG_ETB", 280)
    if "booster box" in t_f or ("display" in t_f and "pokemon" in t_f): return ("TCG_BOX", 600)
    if any(x in t_f for x in ["tin", "bundle", "blister", "booster"]): return ("TCG_SEALED", 150)
    return None

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. TCG
    tcg = classify_tcg(t_f)
    if tcg:
        subcat, max_p = tcg
        return (20 <= price <= max_p), subcat

    # 2. Pokemon Games Filter
    is_pkmn_game = any(f" {g}" in t_f for g in POKEMON_GAMES)
    has_console_word = any(x in t_f for x in ["konsola", "console", "zestaw", "gameboy", "gba", "3ds", "nintendo"])
    if is_pkmn_game and not has_console_word: return False, "PKMN_GAME"

    # 3. Części / Folia
    if PARTS_RE.search(t_f) or FOLIA_RE.search(t_f): return False, "PART"

    # 4. Kategorie i TWOJE LIMITU
    hw_cat = None
    if "vita" in t_f: hw_cat = "VITA"
    elif "psp" in t_f: hw_cat = "PSP"
    elif "3ds" in t_f: hw_cat = "3DS"
    elif "ds lite" in t_f or "dsi" in t_f or "nintendo ds" in t_f: hw_cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): hw_cat = "RETRO"
    elif "walkman" in t_f: hw_cat = "WALKMAN"

    if not hw_cat: return False, "NO_CAT"
    
    # Blokada gier (nie dotyczy walkmanów)
    if hw_cat != "WALKMAN":
        if not CONSOLE_MAIN_RE.search(t_f) and not BUNDLE_RE.search(t_f): return False, "SINGLE_GAME"

    # TWOJE ORYGINALNE LIMITY
    limits = {
        "PSP": (50, 200), "VITA": (200, 500), "3DS": (100, 500),
        "DS": (50, 170), "RETRO": (50, 250), "WALKMAN": (35, 100)
    }
    lo, hi = limits.get(hw_cat, (35, 1000))
    return (lo <= price <= hi), hw_cat

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower()}_{int(price)}".encode()).hexdigest()

    if is_duplicate(clean_url, content_hash): return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:40]} ({price} zł)")
        save_to_memory(clean_url, content_hash)
        return True
    return False

# --- PĘTLA ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER v54.0 | Redis Memory + Original Limits")
    vinted_init()
    
    queries = ["psp", "ps vita", "nintendo 3ds", "nintendo ds lite", "game boy advance", "game boy color", "pokemon etb", "pokemon booster box", "sony walkman"]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800); continue

        random.shuffle(queries)
        for q in queries:
            scrape_vinted(q); time.sleep(random.uniform(4, 7))
            scrape_olx(q); time.sleep(random.uniform(2, 4))
            scrape_allegro_lokalnie(q); time.sleep(random.uniform(3, 5))

        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 5 min.")
        time.sleep(300)