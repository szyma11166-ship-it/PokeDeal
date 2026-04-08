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

# Wczytanie Twardej Pamięci (Format: URL|HASH)
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) == 2:
                    SENT_URLS.add(parts[0])
                    SENT_HASHES.add(parts[1])
                elif len(parts) == 1:
                    SENT_URLS.add(parts[0])
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
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=15
        )
        return r.status_code == 200
    except: return False

def append_to_history(url, content_hash):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{url}|{content_hash}\n")

# --- INICJALIZACJA VINTED ---
def vinted_init():
    global VINTED_LAST_INIT
    try:
        log_debug("🔄 Inicjalizuję sesję Vinted...")
        VINTED_SESSION.impersonate = random.choice(["chrome120", "chrome116", "safari15_5"])
        VINTED_SESSION.cookies.clear()
        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        if r.status_code == 200:
            VINTED_LAST_INIT = time.time()
            return True
        return False
    except: return False

def vinted_ensure():
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

# --- SCRAPERY ---
def scrape_vinted(query):
    if not vinted_ensure(): return
    try:
        url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={urllib.parse.quote_plus(query)}&order=newest_first&per_page=30"
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code == 200:
            items = r.json().get("items", [])
            new_count = 0
            for item in items:
                item_id = str(item.get("id", ""))
                title = item.get("title", "")
                p_raw = item.get("price", 0)
                price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED", item_id=item_id): new_count += 1
            log_debug(f"✅ Vinted [{query}]: nowych {new_count}")
    except Exception as e: log_debug(f"💥 Błąd Vinted: {e}")

def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if p_val and process_item(o['title'], o['url'], float(p_val), "OLX", item_id=f"olx_{o.get('id')}"): new_count += 1
            log_debug(f"✅ OLX [{query}]: nowych {new_count}")
    except: pass

def scrape_allegro_lokalnie(query):
    try:
        url = f"https://allegrolokalnie.pl/oferty?phrase={urllib.parse.quote_plus(query)}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200: return
        soup = BeautifulSoup(r.text, "html.parser")
        new_count = 0
        for item in soup.select("article[data-testid='listing-ad'], div[class*='mlc-itemcard']"):
            try:
                link = item.find("a", href=lambda h: h and "/oferta/" in h)
                if not link: continue
                item_url = "https://allegrolokalnie.pl" + link.get("href") if not link.get("href").startswith("http") else link.get("href")
                title = item.find(["h2", "h3", "span"], class_=re.compile(r"title|name", re.I)).get_text(strip=True)
                price_match = re.search(r"(\d[\d\s]*(?:[,\.]\d{1,2})?)\s*zł", item.get_text())
                if price_match and process_item(title, item_url, float(price_match.group(1).replace(" ", "").replace(",", ".")), "ALLEGRO"): new_count += 1
            except: continue
        log_debug(f"✅ Allegro [{query}]: nowych {new_count}")
    except: pass

# --- FILTRY ---

POKEMON_GAMES = ["silver", "gold", "blue", "red", "yellow", "crystal", "ruby", "sapphire", "emerald", "fire red", "leaf green", "soul silver", "heart gold", "diamond", "pearl", "platinum", "black", "white", "black 2", "white 2", "omega ruby", "alpha sapphire", "x", "y", "sun", "moon"]

PARTS_RE = re.compile(r"\b(ekran|lcd|obudow|shell|rys|kabel|ładowark|zasilacz|bateria|etui|pokrowiec|szkło|przyciski|taśm|słuchawk|stojak|uchwyt|pudełko|box|replacement|manual|instrukcja)\b", re.I)
FOLIA_RE = re.compile(r"(^folia\b|folia\s*ochronna)", re.I)
BUNDLE_RE = re.compile(r"\b(zestaw|komplet|bundle|lot|x\d|\d+x|\d+\s*gier|\d+\s*szt)\b", re.I)
CONSOLE_MAIN_RE = re.compile(r"\b(konsola|console|handheld|psp\b|vita|nintendo|3ds|2ds|dsi|gameboy|gba|gbc|sp)\b", re.I)

def classify_tcg(t_f):
    if not any(x in t_f for x in ["pokemon", "pokémon"]): return None
    # Limity dla TCG (zostawione bez zmian)
    if "etb" in t_f or "elite trainer" in t_f: return ("TCG_ETB", 280)
    if "booster box" in t_f or ("display" in t_f and "pokemon" in t_f): return ("TCG_BOX", 600)
    if any(x in t_f for x in ["tin", "bundle", "blister", "booster"]): return ("TCG_SEALED", 150)
    return None

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. TCG logic
    tcg = classify_tcg(t_f)
    if tcg:
        subcat, max_p = tcg
        if 20 <= price <= max_p: return True, subcat
        return False, "PRICE_TCG"

    # 2. Pokemon Games filter (blokada gier bez konsoli)
    is_pkmn_game = any(f" {g}" in t_f or f"{g} version" in t_f for g in POKEMON_GAMES)
    has_console_word = any(x in t_f for x in ["konsola", "console", "zestaw", "bundle", "gameboy", "gba", "3ds", "dsi", "nintendo"])
    if is_pkmn_game and not has_console_word:
        return False, "PKMN_GAME"

    # 3. Akcesoria i części
    if PARTS_RE.search(t_f) or FOLIA_RE.search(t_f): return False, "PART"

    # 4. Kategorie i limity (TWÓJ LIMIT 60 PLN i górne granice)
    hw_cat = None
    if "vita" in t_f: hw_cat = "VITA"
    elif "psp" in t_f: hw_cat = "PSP"
    elif "3ds" in t_f: hw_cat = "3DS"
    elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): hw_cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "game boy"]): hw_cat = "RETRO"
    elif "walkman" in t_f: hw_cat = "WALKMAN"

    if not hw_cat: return False, "NO_CAT"

    # Blokada pojedynczych gier (jeśli nie ma słowa konsola/zestaw/itp)
    if not CONSOLE_MAIN_RE.search(t_f) and not BUNDLE_RE.search(t_f):
        return False, "SINGLE_GAME"

    # TWOJE LIMITY CENOWE
    limits = {
        "PSP": (60, 250),
        "VITA": (60, 600),
        "3DS": (60, 500),
        "DS": (60, 170),
        "RETRO": (60, 300),
        "WALKMAN": (60, 100)
    }
    
    lo, hi = limits.get(hw_cat, (60, 1000))
    if lo <= price <= hi: return True, hw_cat
    return False, "PRICE"

def process_item(title, url, price, src, item_id=None):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower().strip()}_{int(price)}".encode()).hexdigest()

    if (item_id and item_id in SENT_IDS) or clean_url in SENT_URLS or content_hash in SENT_HASHES:
        return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:40]} ({price} zł)")
        
        if item_id: SENT_IDS.add(item_id)
        SENT_URLS.add(clean_url)
        SENT_HASHES.add(content_hash)
        append_to_history(clean_url, content_hash)
        return True
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER v52.0 | Pokemon Game Filter + Hard Memory + 60PLN")
    vinted_init()
    
    queries = ["psp", "ps vita", "nintendo 3ds", "nintendo ds lite", "game boy advance", "game boy color", "pokemon etb", "pokemon booster box", "sony walkman"]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800); continue

        random.shuffle(queries)
        for q in queries:
            scrape_vinted(q)
            time.sleep(random.uniform(4, 7))
            scrape_olx(q)
            time.sleep(random.uniform(2, 4))
            scrape_allegro_lokalnie(q)
            time.sleep(random.uniform(3, 5))

        IS_FIRST_RUN = False
        log_debug("💤 Przerwa 5 min.")
        time.sleep(300)
