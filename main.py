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
REDIS_URL = os.getenv("REDIS_URL")

r_db = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        r_db = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r_db.ping()
    except: r_db = None

SENT_CACHE = set()
SENT_IDS = set()
IS_FIRST_RUN = True

# SESJE
VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
OLX_SESSION = curl_requests.Session(impersonate="chrome120")
ALLEGRO_SESSION = requests.Session()

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

# --- TWOJE ORYGINALNE FILTRY ---
JUNK_RE = re.compile(r"\b(ps[45]|xbox|series\s*[sx]|one\s*[sx])\b", re.I)
PARTS_RE = re.compile(r"\b(ekran|lcd|obudow|shell|housing|rysik|stylus|kabel|cable|ładowark|charger|zasilacz|bateria|battery|etui|pokrowiec|torb|bag|folia|szkło|przyciski|głośnik|taśm|ribbon|akryl|sleeve|koszulk)\b", re.I)
ADAPTER_MAIN_RE = re.compile(r"^(adapter|zasilacz|ac\s*adapter|power\s*adapter|przejściówka)\b", re.I)
CLONE_RE = re.compile(r"\b(r36s?|miyoo|anbernic|retroid|trimui|powkiddy|rg\d+|rk\d+|rgb\d+|pxp|sup\s*game|bittboy)\b", re.I)
BUNDLE_RE = re.compile(r"\b(bundle|zestaw|komplet|lot|x[2-9]|[2-9]\s*x\b|\d+\s*gier|\d+\s*sztuk)\b", re.I)
CONSOLE_MAIN_RE = re.compile(r"\b(konsola|console|psp|psv|3ds|ds\s*lite|dsi|game\s*boy|gameboy|gba|gbc)\b", re.I)

def is_interesting_item(title, price):
    t_f = title.lower()
    if JUNK_RE.search(t_f): return False, "JUNK"
    if CLONE_RE.search(t_f): return False, "CLONE"
    
    # Oryginalna logika części
    is_part = bool(PARTS_RE.search(t_f)) or bool(ADAPTER_MAIN_RE.search(t_f))
    has_konsola = bool(CONSOLE_MAIN_RE.search(t_f))
    if is_part and not has_konsola: return False, "PART"

    hw_cat = None
    if "psp" in t_f: hw_cat = "PSP"
    elif "vita" in t_f or "psv" in t_f: hw_cat = "VITA"
    elif "3ds" in t_f: hw_cat = "3DS"
    elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): hw_cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): hw_cat = "RETRO"
    elif any(x in t_f for x in ["walkman", "discman", "minidisc"]): hw_cat = "WALKMAN"

    if not hw_cat: return False, "NO_CAT"

    # Twój oryginalny filtr na gry (SINGLE_GAME)
    if not (has_konsola or BUNDLE_RE.search(t_f)) and price > 40:
        return False, "SINGLE_GAME"

    # Twoje limity (dokładnie takie jak chciałeś)
    limits = {
        "PSP": (50, 200),
        "VITA": (200, 500),
        "3DS": (100, 500),
        "DS": (50, 170),
        "RETRO": (50, 250),
        "WALKMAN": (35, 100)
    }
    lo, hi = limits.get(hw_cat, (50, 1000))
    return (True, hw_cat) if lo <= price <= hi else (False, "PRICE")

def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN
    if item_id and item_id in SENT_IDS: return False
    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower()}_{int(price)}".encode()).hexdigest()
    
    if content_hash in SENT_CACHE: return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title}\n💰 `{price:.2f} zł`"
            if src == "OLX":
                oid = re.search(r'-ID([a-zA-Z0-9]+)\.html', clean_url)
                kb = {"inline_keyboard": [[{"text": "📱 App", "url": f"olx://listing/{oid.group(1)}" if oid else clean_url}, {"text": "🌐 WWW", "url": clean_url}]]}
                payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "reply_markup": json.dumps(kb)}
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=payload)
            else:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": f"{msg}\n🔗 {clean_url}", "parse_mode": "Markdown"})
            log_debug(f"🎯 WYSŁANO: {title[:40]}")
        SENT_CACHE.add(content_hash)
        if item_id: SENT_IDS.add(item_id)
        return True
    log_debug(f"⛔ [{res}] {title[:40]} ({price} zł)")
    return False

def scrape_vinted(query):
    try:
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={urllib.parse.quote_plus(query)}&order=newest_first"
        r = VINTED_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("items", []):
                process_item(item.get("title", ""), "https://www.vinted.pl" + item.get("url", ""), float(item.get("price", {}).get("amount", 0)), "VINTED", item_id=str(item.get("id")))
    except: pass

def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                price = 0
                for p in o.get('params', []):
                    if p.get('key') == 'price':
                        price = float(p.get('value', {}).get('value', 0))
                process_item(o['title'], o['url'], price, "OLX", item_id=str(o.get('id')))
    except: pass

if __name__ == "__main__":
    log_debug("🚀 SNIPER ORIGINAL v2 | OLX FIX")
    queries = ["psp", "ps vita", "nintendo 3ds", "nintendo ds", "gameboy", "walkman"]
    while True:
        for q in queries:
            scrape_vinted(q)
            time.sleep(5)
            scrape_olx(q)
            time.sleep(5)
        IS_FIRST_RUN = False
        time.sleep(300)
