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
                title = item.get("title", "")
                p_raw = item.get("price", 0)
                price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                item_url = item.get("url", "")
                if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED"): new_count += 1
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
# FILTRY I OPTYMALIZACJA
# ---------------------------------------------------------------------------

CONSOLE_WORDS = ["vita", "psp", "konsola", "zestaw", "console", "3ds", "2ds", "dsi", "ds lite", "gameboy", "gba", "nintendo", "spelkonsol", "konzole", "konzol", "pelikonsoli", "spielkonsole"]

POKEMON_GAMES = ["silver", "gold", "blue", "red", "yellow", "crystal", "ruby", "sapphire", "emerald", "fire red", "leaf green", "soul silver", "heart gold", "diamond", "pearl", "platinum", "black", "white"]

# Prekompilacja Regex dla wydajności
ACCESSORY_PATTERNS = [
    re.compile(r"\bsam(a|e|ego|emu|ą)?\s+(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|ekran|rysik|case|pokrowiec)", re.I),
    re.compile(r"\b(tylko|sam(a)?)\s+(kabel|ładowark|zasilacz|adapter|bater|etui|obudow|rysik)", re.I),
    re.compile(r"^(kabel|ładowarka|zasilacz|adapter|bateria|etui|obudowa|rysik|pokrowiec|case|stojak|uchwyt|charger|cable)\b", re.I),
    re.compile(r"\b(only|just|nur|alleen|vain|endast)\s+(the\s+)?(charger|cable|adapter|stylus|case|stand|ladekabel|ladegerät)", re.I),
]

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. Blokada śmieci i akcesoriów
    if any(p.search(t_f) for p in ACCESSORY_PATTERNS): return False, "ACC"
    if any(x in t_f for x in ["szkło hartowane", "folia", "case", "etui", "pudełko", "obudowa", "replacement shell", "r36s", "miyoo", "anbernic"]):
        if not any(c in t_f for c in ["konsola", "zestaw"]): return False, "TRASH"

    # 2. Blokada gier Pokemon (Silver/Gold itd.) CHYBA ŻE jest w zestawie z konsolą
    is_pkmn_game = any(f"pokemon {g}" in t_f or f"pokémon {g}" in t_f for g in POKEMON_GAMES)
    has_cons = any(c in t_f for c in CONSOLE_WORDS)
    if is_pkmn_game and not has_cons: return False, "PKMN_GAME"

    # 3. Kategoryzacja
    cat = None
    if "pokemon" in t_f or "pokémon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer", "display", "booster box", "bundle", "tin", "first partner"]): cat = "TCG"
    
    if not cat:
        if "vita" in t_f: cat = "VITA"
        elif "psp" in t_f: cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["ds lite", "dsi", "nintendo ds"]): cat = "DS"
        elif any(x in t_f for x in ["gameboy", "gba", "gbc"]): cat = "RETRO"
        elif "walkman" in t_f: cat = "WALKMAN"

    if not cat: return False, "NO_CAT"

    # 4. Limity cenowe (MINIMUM 60 PLN)
    limits = {"PSP": 250, "VITA": 600, "3DS": 500, "2DS": 350, "DS": 170, "RETRO": 300, "TCG": 650, "WALKMAN": 400}
    
    if 60 <= price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    if len(SENT_URLS) > 15000:
        SENT_URLS.clear()
        SENT_HASHES.clear()
    
    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(f"{title[:40].lower().strip()}_{int(price)}".encode()).hexdigest()

    if clean_url in SENT_URLS or content_hash in SENT_HASHES: return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:30]} ({price} zł)")
        
        SENT_URLS.add(clean_url)
        SENT_HASHES.add(content_hash)
        append_to_history(clean_url) # Zapis do pliku
        return True
    return False

# --- PĘTLA ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER v45.0 | PKMN Filter + Hard Memory + 60PLN Limit")
    vinted_init()
    
    Q_V = ["psp", "ps vita", "nintendo 3ds", "nintendo 2ds", "nintendo ds lite", "game boy advance", "game boy color", "pokemon etb", "pokemon booster box", "sony walkman"]
    Q_PL = ["psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "nintendo ds", "gameboy advance", "pokemon etb", "sony walkman"]

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
