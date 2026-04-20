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

# Ustawienie strefy czasowej
os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
REDIS_URL = os.getenv("REDIS_URL")

# --- REDIS (Trwała pamięć) ---
r_db = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        r_db = redis_lib.from_url(REDIS_URL, decode_responses=True)
        r_db.ping()
        print("✅ Redis połączony")
    except: r_db = None

SENT_CACHE = set()
SENT_IDS = set()
IS_FIRST_RUN = True

# --- SESJE (Naprawa blokad OLX i Vinted) ---
VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
OLX_SESSION = curl_requests.Session(impersonate="chrome120")
ALLEGRO_SESSION = requests.Session()

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def extract_olx_id(url):
    match = re.search(r'-ID([a-zA-Z0-9]+)\.html', url)
    return match.group(1) if match else None

def send_telegram(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
        requests.post(url, data=payload, timeout=15)
    except Exception as e:
        log_debug(f"❌ Błąd Telegram: {e}")

# --- TWOJE FILTRY I LOGIKA ---
JUNK_RE = re.compile(r"\b(ps[45]|xbox|series\s*[sx]|one\s*[sx]|tur|ciągnik|koparka|bilet|pkp|pks)\b", re.I)
PARTS_RE = re.compile(r"\b(ekran|lcd|obudow|shell|rysik|kabel|ładowark|zasilacz|bateria|etui|pokrowiec|folia|szkło|taśm|akryl)\b", re.I)
ADAPTER_MAIN_RE = re.compile(r"^(adapter|zasilacz|przejściówka)\b", re.I)
CLONE_RE = re.compile(r"\b(r36s?|miyoo|anbernic|retroid|powkiddy|rg\d+|rk\d+|sup\s*game)\b", re.I)
BUNDLE_RE = re.compile(r"\b(bundle|zestaw|komplet|lot|x[2-9]|\d+\s*gier|\d+\s*sztuk)\b", re.I)
CONSOLE_MAIN_RE = re.compile(r"\b(konsola|console|psp|psv|3ds|ds\s*lite|dsi|game\s*boy|gameboy|gba|gbc)\b", re.I)

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. Filtry wykluczające
    if JUNK_RE.search(t_f): return False, "JUNK"
    if CLONE_RE.search(t_f): return False, "CLONE"
    
    # 2. TCG (Pokemon)
    if "pokemon" in t_f or "pokémon" in t_f:
        if any(x in t_f for x in ["etb", "booster box", "display", "tin", "blister"]):
            if 40 <= price <= 600: return True, "TCG"

    # 3. Rozpoznawanie sprzętu
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

    # Filtr pojedynczych gier (Twoje ustawienie)
    if not (has_konsola or BUNDLE_RE.search(t_f)) and price > 45:
        return False, "SINGLE_GAME"

    # TWOJE LIMITY CENOWE
    limits = {
        "PSP": (50, 200),
        "VITA": (200, 500),
        "3DS": (100, 500),
        "DS": (50, 170),
        "RETRO": (50, 250),
        "WALKMAN": (35, 120)
    }
    lo, hi = limits.get(hw_cat, (50, 1000))
    return (True, hw_cat) if lo <= price <= hi else (False, "PRICE")

def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN
    if item_id and item_id in SENT_IDS: return False
    
    clean_url = url.split("?")[0].rstrip("/")
    # Hash do sprawdzania duplikatów (nawet jeśli link jest inny, a tytuł i cena te same)
    content_hash = hashlib.md5(f"{title[:40].lower()}_{int(price)}".encode()).hexdigest()
    
    # Sprawdzenie w Redis lub Cache lokalnym
    if content_hash in SENT_CACHE: return False
    if r_db and r_db.exists(f"sent:{content_hash}"): return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title}\n💰 `{price:.2f} zł`"
            if src == "OLX":
                oid = extract_olx_id(clean_url)
                kb = {"inline_keyboard": [[{"text": "📱 App", "url": f"olx://listing/{oid}" if oid else clean_url}, {"text": "🌐 WWW", "url": clean_url}]]}
                send_telegram(msg, reply_markup=kb)
            else:
                send_telegram(f"{msg}\n🔗 [LINK]({clean_url})")
            log_debug(f"🎯 WYSŁANO: {title[:40]} ({price} zł)")
        
        # Zapis do pamięci
        SENT_CACHE.add(content_hash)
        if item_id: SENT_IDS.add(item_id)
        if r_db: r_db.setex(f"sent:{content_hash}", 172800, clean_url)
        return True
    
    # Logowanie odrzuconych (tylko jeśli nie są ewidentnym śmieciem)
    if res not in ["JUNK"]:
        log_debug(f"⛔ [{res}] {title[:30]} ({price} zł)")
    return False

# --- SCRAPERY ---

def scrape_vinted(query):
    try:
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={urllib.parse.quote_plus(query)}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            items = r.json().get("items", [])
            for item in items:
                v_url = "https://www.vinted.pl" + item.get("url", "")
                process_item(item.get("title", ""), v_url, float(item.get("price", {}).get("amount", 0)), "VINTED", item_id=str(item.get("id")))
    except Exception as e: log_debug(f"Vinted Error: {e}")

def scrape_olx(query):
    try:
        # Używamy API v1 - najstabilniejsze
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=25"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json().get('data', [])
            for o in data:
                # Wyciąganie ceny z parametrów
                p_val = 0
                for p in o.get('params', []):
                    if p.get('key') == 'price':
                        p_val = float(p.get('value', {}).get('value', 0))
                process_item(o['title'], o['url'], p_val, "OLX", item_id=f"olx_{o.get('id')}")
    except Exception as e: log_debug(f"OLX Error: {e}")

def scrape_allegro_lokalnie(query):
    try:
        url = f"https://allegrolokalnie.pl/oferty?phrase={urllib.parse.quote_plus(query)}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=15)
        if r.status_code != 200: return
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("article[data-testid='listing-ad']"):
            try:
                title = item.find(["h2", "h3"]).get_text(strip=True)
                link = item.find("a", href=True)['href']
                price_text = item.find("span", class_=re.compile(r"price")).get_text()
                price = float(re.sub(r"[^\d,\.]", "", price_text).replace(",", "."))
                process_item(title, "https://allegrolokalnie.pl" + link, price, "ALLEGRO")
            except: continue
    except Exception as e: log_debug(f"Allegro Error: {e}")

# --- MAIN LOOP ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER FULL SPEC START")
    
    Q_LIST = ["psp", "ps vita", "nintendo 3ds", "nintendo ds", "gameboy", "pokemon etb", "walkman"]
    
    while True:
        for q in Q_LIST:
            scrape_vinted(q)
            time.sleep(random.uniform(4, 7))
            scrape_olx(q)
            time.sleep(random.uniform(3, 6))
            scrape_allegro_lokalnie(q)
            time.sleep(random.uniform(3, 6))
        
        if IS_FIRST_RUN:
            log_debug("✨ Pierwszy skan zakończony. Od teraz powiadomienia są AKTYWNE.")
            IS_FIRST_RUN = False
            
        log_debug("💤 Chwila odpoczynku...")
        time.sleep(240)
