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
if hasattr(time, 'tzset'):
    time.tzset()

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
            r_db = redis_lib.from_url(REDIS_URL, decode_responses=True, ssl_cert_reqs=None)
        else:
            r_db = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r_db.ping()
        print("🚀 Redis aktywny (trwała pamięć)")
    except Exception as e:
        print(f"⚠️ Redis niedostępny: {e} — fallback na plik")
        r_db = None

# --- PAMIĘĆ ---
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
    except:
        pass

# --- SESJE ---
VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
VINTED_SESSION.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://www.vinted.pl/catalog",
    "Origin": "https://www.vinted.pl",
})

OLX_SESSION = curl_requests.Session(impersonate="chrome120")
OLX_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

ALLEGRO_SESSION = requests.Session()
ALLEGRO_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "pl-PL,pl;q=0.9",
})

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def extract_olx_id(url):
    m = re.search(r'-ID([a-zA-Z0-9]+)\.html', url)
    return m.group(1) if m else None

def send_telegram(msg, reply_markup=None):
    try:
        payload = {
            "chat_id": CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            timeout=15
        )
        return r.status_code == 200
    except:
        return False

# --- DUPLIKATY ---
def is_duplicate(clean_url, content_hash):
    key = f"{clean_url}_{content_hash}"
    if key in SENT_CACHE:
        return True
    if r_db:
        try:
            if r_db.exists(f"sent:{content_hash}"):
                return True
        except:
            pass
    return False

def save_to_memory(clean_url, content_hash):
    key = f"{clean_url}_{content_hash}"
    SENT_CACHE.add(key)
    if r_db:
        try:
            r_db.setex(f"sent:{content_hash}", 172800, clean_url)
        except:
            pass
    else:
        try:
            with open(HISTORY_FILE, "a") as f:
                f.write(key + "\n")
        except:
            pass

# ---------------------------------------------------------------------------
# VINTED
# ---------------------------------------------------------------------------
def vinted_init():
    global VINTED_LAST_INIT
    try:
        log_debug("🔄 Inicjalizuję sesję Vinted...")
        VINTED_SESSION.impersonate = random.choice(
            ["chrome120", "chrome116", "safari15_5", "edge101"]
        )
        VINTED_SESSION.cookies.clear()
        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        if r.status_code == 200:
            VINTED_LAST_INIT = time.time()
            log_debug("✅ Sesja Vinted gotowa")
            return True
        log_debug(f"💥 Vinted init: {r.status_code}")
        return False
    except Exception as e:
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def scrape_vinted(query):
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        if not vinted_init():
            return

    try:
        url = (
            "https://www.vinted.pl/api/v2/catalog/items"
            f"?search_text={urllib.parse.quote_plus(query)}"
            "&order=newest_first&per_page=30"
        )
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code != 200:
            log_debug(f"⚠️ Vinted [{query}] {r.status_code}")
            return

        for item in r.json().get("items", []):
            item_id = str(item.get("id", ""))
            if item_id in SENT_IDS:
                continue
            title = item.get("title", "")
            price = float(item.get("price", {}).get("amount", 0))
            url_item = item.get("url", "")
            if not url_item.startswith("http"):
                url_item = "https://www.vinted.pl" + url_item
            process_item(title, url_item, price, "VINTED", item_id)
    except Exception as e:
        log_debug(f"💥 Vinted error: {e}")

# ---------------------------------------------------------------------------
# FILTRY (skrócone do zmian)
# ---------------------------------------------------------------------------

SCREEN_RE = re.compile(r"\b(ekran|screen|lcd|display|wyświetlacz)\b", re.I)
CONSOLE_MAIN_RE = re.compile(r"\b(psp|vita|3ds|2ds|ds|gameboy|game boy|konsola|console)\b", re.I)
GAME_SIGNAL_RE = re.compile(r"\b(gra|gry|game|игр)\b", re.I)
PARTS_RE = re.compile(r"\b(ładowark|zasilacz|kabel|bateria|etui)\b", re.I)

def is_interesting_item(title, price):
    t = title.lower()

    has_console = bool(CONSOLE_MAIN_RE.search(t))
    is_game = bool(GAME_SIGNAL_RE.search(t))

    # FIX 1: ekran tylko jeśli nie ma konsoli
    if SCREEN_RE.search(t) and not has_console:
        return False, "PART"

    # FIX 2: SINGLE_GAME tylko gdy nie jest konsola
    if is_game and not has_console:
        return False, "SINGLE_GAME"

    # PARTS
    if PARTS_RE.search(t) and not has_console:
        return False, "PART"

    # KATEGORIE
    if "psp" in t:
        hw = "PSP"
        lo, hi = 50, 200
    elif "vita" in t:
        hw = "VITA"
        lo, hi = 200, 500
    elif "3ds" in t or "2ds" in t:
        hw = "3DS"
        lo, hi = 100, 500
    elif "ds" in t:
        hw = "DS"
        lo, hi = 50, 170
    elif "gameboy" in t or "gba" in t or "gbc" in t:
        hw = "RETRO"
        lo, hi = 50, 250
    else:
        return False, "NO_CAT"

    if lo <= price <= hi:
        return True, hw
    return False, "PRICE"

# ---------------------------------------------------------------------------
# PROCESS ITEM
# ---------------------------------------------------------------------------
def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN

    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:40].lower()}_{int(price)}".encode()).hexdigest()

    if is_duplicate(clean_url, h):
        return False

    valid, res = is_interesting_item(title, price)
    if not valid:
        log_debug(f"⛔ [{res}] {title[:50]} ({price} zł)")
        return False

    if not IS_FIRST_RUN:
        msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`"
        if src == "OLX":
            olx_id = extract_olx_id(clean_url)
            keyboard = {
                "inline_keyboard": [[
                    {"text": "📱 Otwórz w aplikacji OLX", "url": f"olx://listing/{olx_id}" if olx_id else clean_url},
                    {"text": "🌐 Przeglądarka", "url": clean_url}
                ]]
            }
            send_telegram(msg, keyboard)
        else:
            send_telegram(msg + f"\n🔗 [LINK]({clean_url})")

        log_debug(f"🎯 WYSŁANO: {title[:50]} ({price} zł) [{res}]")

    save_to_memory(clean_url, h)
    if item_id:
        SENT_IDS.add(item_id)
    return True

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    log_debug("🚀 SNIPER v70.1 | FIXED (NO LIMIT CHANGES)")
    vinted_init()

    QUERIES = [
        "psp", "psp 2004", "ps vita", "nintendo 3ds xl",
        "nintendo ds", "game boy",
        "pokemon etb", "sony walkman"
    ]

    while True:
        for q in QUERIES:
            scrape_vinted(q)
            time.sleep(5)
        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 5 min")
        time.sleep(300)
