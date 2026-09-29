import os
import re
import time
import random
import hashlib
import json
import urllib.parse
from bs4 import BeautifulSoup
import requests
from curl_cffi import requests as curl_requests

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
FIRST_RUN_VINTED  = True
FIRST_RUN_OLX     = True
FIRST_RUN_ALLEGRO = True
VINTED_LAST_INIT  = 0
VINTED_INIT_INTERVAL = 2 * 3600
VINTED_SCAN_INTERVAL = 15 * 60  # 15 minut
LAST_VINTED_SCAN = 0
VINTED_FAIL_COUNT = 0
VINTED_BLOCKED_UNTIL = 0

if not r_db and os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                val = line.strip()
                if val: SENT_CACHE.add(val)
    except: pass

# --- SESJE ---
VINTED_SESSION = curl_requests.Session(impersonate="chrome120")
VINTED_SESSION.headers.update({
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://www.vinted.pl/catalog",
    "Origin": "https://www.vinted.pl",
})

OLX_SESSION = curl_requests.Session(impersonate="chrome120")
OLX_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

ALLEGRO_SESSION = requests.Session()
ALLEGRO_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9",
})

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def escape_md(text):
    return re.sub(r'([_*\[\]`])', r'\\\1', text)

def send_telegram(msg, reply_markup=None):
    try:
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload, timeout=15
        )
        if r.status_code != 200:
            log_debug(f"⚠️ Telegram błąd {r.status_code}: {r.text[:100]}")
        return r.status_code == 200
    except Exception as e:
        log_debug(f"💥 Telegram wyjątek: {e}")
        return False

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
            r_db.set(f"sent:{content_hash}", clean_url, ex=172800)
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
    global VINTED_LAST_INIT, VINTED_FAIL_COUNT, VINTED_BLOCKED_UNTIL
    try:
        log_debug("🔄 Inicjalizuję sesję Vinted (HTML mode)...")
        chosen = random.choice(["chrome120", "chrome116", "safari15_5", "edge101"])
        VINTED_SESSION.impersonate = chosen
        VINTED_SESSION.cookies.clear()
        
        VINTED_SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8",
            "Referer": "https://www.vinted.pl/",
        })

        r = VINTED_SESSION.get("https://www.vinted.pl/", timeout=20)
        
        if r.status_code == 200:
            log_debug(f"✅ Sesja Vinted gotowa ({chosen})")
            VINTED_LAST_INIT = time.time()
            VINTED_FAIL_COUNT = 0
            VINTED_BLOCKED_UNTIL = 0
            return True
        else:
            VINTED_FAIL_COUNT += 1
            wait = min(300 * (2 ** (VINTED_FAIL_COUNT - 1)), 1800)
            VINTED_BLOCKED_UNTIL = time.time() + wait
            log_debug(f"💥 Vinted init status: {r.status_code}")
            return False
    except Exception as e:
        VINTED_FAIL_COUNT += 1
        wait = min(300 * (2 ** (VINTED_FAIL_COUNT - 1)), 1800)
        VINTED_BLOCKED_UNTIL = time.time() + wait
        log_debug(f"💥 Błąd init Vinted: {e}")
        return False

def vinted_available():
    if time.time() < VINTED_BLOCKED_UNTIL:
        remaining = int(VINTED_BLOCKED_UNTIL - time.time()) // 60
        log_debug(f"⏳ Vinted w backoffie — jeszcze ~{remaining} min")
        return False
    if time.time() - VINTED_LAST_INIT > VINTED_INIT_INTERVAL:
        return vinted_init()
    return True

def scrape_vinted(query, first_run=False):
    if not vinted_available(): return False
    try:
        encoded_q = urllib.parse.quote_plus(query)
        url = f"https://www.vinted.pl/catalog?search_text={encoded_q}&order=newest_first"
        
        r = VINTED_SESSION.get(url, timeout=20)

        if r.status_code in [401, 403]:
            log_debug(f"🔄 Vinted {r.status_code} [{query}] — reset sesji...")
            time.sleep(random.uniform(5, 10))
            if vinted_init():
                r = VINTED_SESSION.get(url, timeout=20)
            else:
                return False

        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            items = []

            script_tag = soup.find("script", id="__NEXT_DATA__")
            if script_tag and script_tag.string:
                try:
                    json_data = json.loads(script_tag.string)
                    page_props = json_data.get("props", {}).get("pageProps", {})
                    catalog_props = page_props.get("catalogItems", {}) or page_props.get("items", {})
                    items = catalog_props.get("items", [])
                except Exception as e:
                    log_debug(f"⚠️ Błąd parsowania __NEXT_DATA__ [{query}]: {e}")

            if not items:
                item_cards = soup.select("div[data-testid='grid-item'], div.feed-grid__item")
                for card in item_cards:
                    a_tag = card.find("a", href=re.compile(r"/items/"))
                    if not a_tag: continue
                    
                    item_url = a_tag.get("href", "")
                    if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                    
                    item_id_match = re.search(r'/items/(\d+)', item_url)
                    item_id = item_id_match.group(1) if item_id_match else ""

                    log_debug(card.get_text(" ", strip=True)[:500])
                    title_el = card.find(
                        ["p", "h2", "h3", "span"],
                        class_=re.compile(r".*", re.I)
                    )
                    title = title_el.get_text(strip=True) if title_el else a_tag.get("title", "")

                    price_el = card.find(string=re.compile(r"\d+[\s,.]*\d*\s*zł", re.I))
                    if price_el:
                        p_match = re.search(r"(\d+(?:[\s,.]\d+)?)\s*zł", str(price_el))
                        if p_match:
                            clean_p = p_match.group(1).replace(" ", "").replace(",", ".")
                            items.append({
                                "id": item_id,
                                "title": title,
                                "price": float(clean_p),
                                "url": item_url
                            })
                
            new_count = 0
            for item in items:
                if isinstance(item, dict):
                    item_id = str(item.get("id", ""))
                    if item_id and item_id in SENT_IDS: continue
                    
                    title = item.get("title", "")
                    p_raw = item.get("price", 0)
                    price = float(p_raw.get("amount", 0)) if isinstance(p_raw, dict) else float(p_raw or 0)
                    
                    item_url = item.get("url", "")
                    if not item_url.startswith("http"): item_url = f"https://www.vinted.pl{item_url}"
                    
                    if process_item(title, item_url, price, "VINTED", item_id=item_id, suppress=first_run): 
                        new_count += 1

            if not first_run:
                log_debug(f"✅ Vinted [{query}]: przeanalizowano {len(items)} ofert, nowych {new_count}")
            return True
        elif r.status_code == 429:
            log_debug(f"⚠️ Vinted [{query}]: 429 - rate limit")
            
            time.sleep(random.uniform(60, 120))
            
            return False

        else:
            log_debug(f"⚠️ Vinted [{query}]: {r.status_code}")
            return False

    except Exception as e:
        log_debug(f"💥 Błąd Vinted [{query}]: {e}")
        return False

def scrape_olx(query, first_run=False):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=25"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o.get('params', []) if x.get('key') == 'price'), None)
                if not p_val: continue
                olx_id = f"olx_{o.get('id', '')}"
                if process_item(o['title'], o['url'], float(p_val), "OLX", item_id=olx_id, suppress=first_run): 
                    new_count += 1
            if not first_run:
                log_debug(f"✅ OLX [{query}]: nowych {new_count}")
            return True
        else:
            log_debug(f"⚠️ OLX [{query}]: {r.status_code}")
            return False
    except Exception as e:
        log_debug(f"💥 Błąd OLX [{query}]: {e}")
        return False

def scrape_allegro_lokalnie(query, first_run=False):
    try:
        url = f"https://allegrolokalnie.pl/oferty?phrase={urllib.parse.quote_plus(query)}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200:
            log_debug(f"⚠️ Allegro [{query}]: {r.status_code}")
            return False
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
                price_match = re.search(r"(\d[\d\s\xa0]*(?:[,\.]\d{1,2})?)\s*zł", item.get_text(separator=" "))
                if price_match:
                    clean_price = re.sub(r'\s+', '', price_match.group(1)).replace(",", ".")
                    if process_item(title.strip(), item_url, float(clean_price), "ALLEGRO", suppress=first_run):
                        new_count += 1
            except Exception:
                continue
        if not first_run:
            log_debug(f"✅ Allegro [{query}]: nowych {new_count}")
        return True
    except Exception as e:
        log_debug(f"💥 Błąd Allegro [{query}]: {e}")
        return False

# ---------------------------------------------------------------------------
# FILTRY I REGEXY
# ---------------------------------------------------------------------------

PARTS_RE = re.compile(r"""
    (
        \bekran\b|\bscreen\b|\blcd\b|
        \bobudow|\bshell\b|\bhousing\b|\bcasing\b|\bfaceplate\b|
        \brysik\b|\bstylus\b|
        \bkabel\b|\bcable\b|\bprzewód\b|\bładowark|\bcharger\b|\bzasilacz\b|
        \bpower\s*supply\b|\bpunjač\b|\bnabíječ|\bnabíjačk|\blader\b|\bladegerät\b|
        \boplader\b|\blaturi\b|\btöltő\b|
        \bbateria\b|\bbattery\b|\bakumulator\b|\bmoduł\s*akumulatora\b|
        \betui\b|\bpokrowiec\b|\btorb|\bbag\b|
        \bszkło\s*hartowane\b|\bscreen\s*protector\b|\bfolia\b|
        \bprzyciski\b|\bbuttons\b|\btrigger\b|\bgłośnik\b|\bspeaker\b|
        \btaśm|\bribbon\b|\bflex\b|\bobiektyw\b|\blens\b|
        \bremote\s*control\b|\bpilot\b|\btelecommand\b|
        \bheadphones?\b|\bsłuchawk|\bearphones?\b|
        \bakryl\b|\bacrylic\b|\bgablotk|\bcard\s*case\b|\bcard\s*holder\b|
        \bsleeve\b|\bkoszulk|\bcoin\b|
        \brecordable\s*md\b|\bblank\s*md\b|\bkaseta\s*md|\btaśma\s*md\b|
        \bminidisc\s*74\b|\bminidisc\s*80\b|\bmd\s*74\b|\bmd\s*80\b|
        \bkarta\s*pamięci\b|\bmemory\s*card\b|\bmicrosd\b|\bmicro\s*sd\b|
        \bms\s*pro\b|\bpro\s*duo\b|\bpro-duo\b
    )
""", re.I | re.VERBOSE)

MERCH_RE = re.compile(r"""
    \b(
        lampka|lamp\b|paladone|
        kubek|szklanka|portfel|wallet|poster|plakat|brelok|keychain|
        figurk|statue|statuett|plush|pluszak|poduszk|pillow|
        koszulk|t[\s\-]*shirt|bluza|hoodie|\bcap\b|czapk|
        pudełko|puste\s*pudełko|empty\s*box|box\s*only|
        \bständ\b|\bstall\b|\bstativ\b|ställ\b|stojak|podstawk|\bstand\b|
        naklejk|sticker|decal|\bskin\b|\bvinyl\b|
        książk|\bbook\b|\bguide\b|\bmanual\b|instrukcj|
        amiibo|puzzle\b
    )\b
""", re.I | re.VERBOSE)

ADAPTER_MAIN_RE = re.compile(r"^(adapter|zasilacz|ac\s*adapter|power\s*adapter|przejściówka)\b", re.I)
PHONE_WALKMAN_RE = re.compile(r"\b(ericsson|xperia|nokia|samsung|iphone|motorola|htc|huawei|xiaomi)\b", re.I)
CLONE_RE = re.compile(r"\b(r36s?|miyoo|anbernic|retroid|trimui|powkiddy|rg\d+|rk\d+|rgb\d+|rgxx|rg cube|gameforce|pxp|sup\s*game|retromini|bittboy|pocketgo|r36h)\b", re.I)
JAPANESE_RE = re.compile(r"\b(japanese|japan|japoński|japońskie|jp\s*version|jp\s*ed|japanese\s*ed|nihon|nippon|\bjp\b(?=\s*(ver|ed|version|edition)))\b", re.I)
SONY_CAMERA_RE = re.compile(r"\bsony\s+dsc[-\s]", re.I)

JUNK_RE = re.compile(r"""
    \b(
        ps[1-5]|playstation\s*[1-5]|xbox|xbox\s*360|xbox\s*one|xbox\s*series|
        wii|wii\s*u|
        tur|ładowacz|ciągnik|koparka|silnik|maszyny\s*rolnicze|skrzynia\s*biegów|
        klacz|koń|pks|pck|pkp|bilet|bilety|kalendarz|
        iveco|mercedes|audi|bmw|land\s*rover|
        pc\s*cd|gry\s*pc|gra\s*pc|
        suszarka|pralka|lodówka|zmywarka|odkurzacz|felgi|opony|
        dywaniki\s*samochodowe|dywaniki\s*gumowe|pompa\s*wspomagania|
        ubezpieczeni|wydawnictwo
    )\b
""", re.I | re.VERBOSE)

BUNDLE_RE = re.compile(r"""
    \b(
        bundle|zestaw|komplet|lot|
        x[2-9]|[2-9]\s*x\b|
        \d+\s*gier|\d+\s*gry|\d+\s*sztuk|\d+\s*szt\b|
        \d+\s*games?|hry\s*\d|\d+\s*hry|
        gry\s*na|gry\s*do|kilka\s*gier|par[eę]\s*gier|
        \d+\s*spel\b|\d+\s*spiele?\b|
        \d+\s*jeux?\b|\d+\s*juegos?\b|\d+\s*giochi?\b|
        \d+\s*igr[aei]\b|\d+\s*joc[uri]*\b|\d+\s*játék\b|
        \d+\s*jocuri\b|
        paketti\b|pakket\b|pack(?!\s*art)
    )\b
""", re.I | re.VERBOSE)

HW_PATTERNS = {
    "VITA": re.compile(r"\b(ps\s*vita|psvita|playstation\s*vita|vita|pch[-\s]?\d{4}|pch\d{4})\b", re.I),
    "PSP": re.compile(r"\b(psp|playstation\s*portable|psp[-\s]?\d{4}|psp[-\s]?e\d{4})\b", re.I),
    "3DS": re.compile(r"\b(3ds|2ds|nintendo\s*3ds|nintendo\s*2ds|new\s*3ds|old\s*3ds|3ds\s*xl|2ds\s*xl|3ds\s*ll)\b", re.I),
    "DS": re.compile(r"\b(nintendo\s*ds|ds\s*lite|dsi|ds\s*xl|dsi\s*xl|ds\s*fat|ds\s*phat|ds\s*tank|\bds\b)\b", re.I),
    "RETRO": re.compile(r"\b(game\s*boy|gameboy|gba|gbc|gb\s*advance|gb\s*micro|game\s*boy\s*micro|gba\s*sp)\b", re.I),
    "SWITCH": re.compile(r"\b(nintendo\s*switch|switch\s*lite|switch\s*oled)\b", re.I),
    "PEN": re.compile(r"\b(apple\s*pencil)\b", re.I),
}

CONSOLE_MAIN_RE = re.compile(r"""
    \b(
        konsola|console|handheld|playstation\s*portable|portabil\b|
        konsol\b|konsolę|konsoli|konzol\b|konzole\b|
        consolă\b|consola\b|spielkonsole\b|pelikonsoli\b|spelkonsol\b|
        psp\s*(fat|slim|go|street|1000|2000|3000|value\s*pack)|
        psp[-\s]?\d{4}|psp[-\s]?e\d{4}|
        ps\s*vita\b|psvita\b|playstation\s*vita\b|pch-?\d{4}|
        vita\s*(slim|fat|1000|2000|pch|oled|tv)|
        new\s*3ds|old\s*3ds|3ds\s*xl|3ds\s*ll|2ds\s*xl|
        nintendo\s*3ds|nintendo\s*2ds|
        nintendo\s*ds\b|ds\s*lite|dsi\s*xl|\bdsi\b|
        nintendo\s*switch|switch\s*lite|
        game\s*boy\s*(advance\s*sp|color|pocket|light|original|classic)|
        gameboy\s*(color|advance|sp|pocket|light|classic)|
        gba\s*sp|\bgbc\b|\bgba\b
    )\b
""", re.I | re.VERBOSE)

TCG_EMPTY_RE = re.compile(r"""
    \b(
        empty|pusty|puste|pusta|puszka|
        tomma?\b|tyhj[äa]\b|leer\b|leere\b|
        prázdný|prázdné|ures\b|üres\b|
        vuota\b|vacía\b|vacío\b|vide\b|tom\s*boks|tomt\b|
        used\s*tin|empty\s*tin|
        avattuja\b|avattu\b|opened?\b|otwart\w+|
        geöffnet\b|aperto\b|abierto\b|otevřen\w+|
        loose|luzem|luzne|luźne|
        single|singles|pojedyncz|
        holo\s*rare|reverse\s*holo|
        chinese|korean|chinois|chinesisch|koreanisch|
        bulk\b|akryl\w*|acrylic|mystery\b|
        \d+\s*cards?\b|\d+\s*kort\w*\b|\d+\s*kortti\w*\b|\d+\s*kart\w*\b|
        cards?\s*lot|cards?\s*bundle|
        mixed\s*collection|mixed\s*set|card\s*collection|
        \bkart\b
    )\b
""", re.I | re.VERBOSE)

# REGEXY GRADED
GRADER_RE = re.compile(
    r'\b(psa|bgs|cgc|sgc|ace|pgx|pca|graad|ap)\b|\b(psa|bgs|cgc|sgc|ace|pgx|pca|graad|ap)\d',
    re.I
)

GRADE_VALUE_RE = re.compile(
    r'\b(10|gem\s*mint|pristine|9\.5)\b'
    r'|\b(psa|bgs|cgc|sgc|ace|pgx|pca|graad|ap)[\s\-_]*(10|9\.5|9)\b'
    r'|\bgrade[d]?[\s\-_]*(10|9\.5|9)\b',
    re.I
)

GRADE_LOW_RE = re.compile(
    r'\b(psa|bgs|cgc|sgc|ace|pgx|pca|graad|ap)[\s\-_]*[1-8](?!\d|\.)\b'
    r'|\bgrade[d]?[\s\-_]*[1-8](?!\d|\.)\b',
    re.I
)

GRADED_FAKE_RE = re.compile(
    r'\b(fake|fałszyw|replica|reprint|proxy|custom|chiński|chińska|chinese|bootleg)\b',
    re.I
)

# ---------------------------------------------------------------------------
# KLASYFIKACJE TCG I GRADED
# ---------------------------------------------------------------------------

def classify_tcg(t_f):
    if JAPANESE_RE.search(t_f): return None
    if TCG_EMPTY_RE.search(t_f): return None
    if any(x in t_f for x in ["chiński", "chińskie", "chinese", "chin "]): return None
    
    sealed_keywords = [
        "etb", "elite trainer", "booster box", "display", "bundle",
        "tin", "blister", "first partner", "collection box",
        "premium collection", "booster pack", "booster",
    ]
    if not any(k in t_f for k in sealed_keywords): return None

    if "etb" in t_f or "elite trainer" in t_f: return ("TCG_ETB", 280)
    if "booster box" in t_f or "display" in t_f: return ("TCG_BOX", 600)
    if "first partner" in t_f: return ("TCG_FIRST_PARTNER", 150)
    if "bundle" in t_f: return ("TCG_BUNDLE", 150)
    if any(x in t_f for x in ["mini tin", "mini-tin", "small tin"]): return ("TCG_MINI_TIN", 50)
    if "tin" in t_f: return ("TCG_TIN", 100)
    if "blister" in t_f: return ("TCG_BLISTER", 70)
    if "booster pack" in t_f or "booster" in t_f: return ("TCG_BOOSTER", 25)
    return None


def classify_graded_card(t_f):
    if not GRADER_RE.search(t_f): return None
    if GRADE_LOW_RE.search(t_f): return None
    if GRADED_FAKE_RE.search(t_f): return None
    if not GRADE_VALUE_RE.search(t_f): return None

    is_psa  = bool(re.search(r'\bpsa\b|\bpsa\d', t_f, re.I))
    is_bgs  = bool(re.search(r'\bbgs\b|\bbgs\d', t_f, re.I))
    is_cgc  = bool(re.search(r'\bcgc\b|\bcgc\d', t_f, re.I))
    is_sgc  = bool(re.search(r'\bsgc\b|\bsgc\d', t_f, re.I))
    is_ace  = bool(re.search(r'\b(ace\s*grading|ace)\b|\bace\d', t_f, re.I))
    is_pgx  = bool(re.search(r'\bpgx\b|\bpgx\d', t_f, re.I))

    is_10   = bool(re.search(r'\b10\b|gem\s*mint|pristine', t_f, re.I)) or bool(re.search(r'(psa|cgc|bgs|sgc|ace|pgx)[\s\-_]*10', t_f, re.I))
    is_9_5  = bool(re.search(r'9\.5', t_f, re.I))

    if is_psa:
        return ("GRADED_PSA10", 100) if is_10 else ("GRADED_PSA9", 100)
    elif is_bgs:
        return ("GRADED_BGS10", 100) if (is_10 or is_9_5) else ("GRADED_BGS9", 100)
    elif is_cgc:
        return ("GRADED_CGC10", 100) if is_10 else ("GRADED_CGC9", 100)
    elif is_sgc:
        return ("GRADED_SGC", 100)
    elif is_ace:
        return ("GRADED_ACE", 100)
    elif is_pgx:
        return ("GRADED_PGX", 100)
    else:
        return ("GRADED_OTHER", 100)


def is_interesting_item(title, price):
    t_f = title.lower().strip()

    if JUNK_RE.search(t_f): return False, "JUNK_EXCLUDE"
    if CLONE_RE.search(t_f): return False, "CLONE"
    if MERCH_RE.search(t_f): return False, "MERCH"
    if SONY_CAMERA_RE.search(t_f): return False, "JUNK_EXCLUDE"

    # 1. Graded Cards (PSA 10, CGC10, BGS 9.5 itp.)
    graded = classify_graded_card(t_f)
    if graded:
        subcat, max_price = graded
        if price <= max_price:
            return True, subcat
        return False, "PRICE"

    # 2. TCG Sealed (ETB, Blister, Box)
    tcg = classify_tcg(t_f)
    if tcg:
        subcat, max_price = tcg
        if 10 <= price <= max_price:
            return True, subcat
        return False, "PRICE"

    # 3. Ochrona dla śmieci Pokemon bez konsoli
    if any(p in t_f for p in ["pokemon", "pokémon", "ポケモン"]):
        if PARTS_RE.search(t_f) and not any(x in t_f for x in ["konsola", "console"]):
            return False, "PART"

        has_console = any(HW_PATTERNS[cat].search(t_f) for cat in ["VITA", "PSP", "3DS", "DS", "RETRO", "SWITCH"])
        if not has_console: return False, "PKMN_JUNK"

    # 4. Detekcja gier i akcesoriów
    GAME_SIGNAL_RE = re.compile(r"""
        \b(
            ^gra\s+|\bgra\s+na\s+|
            \bna\s+(nintendo|psp|ds|gba|gbc|vita|switch)\b|
            \bgame\s+for\s+|
            \bjoc\s+|jogo\s+|juego\s+|jeu\s+|
            \bspel\s+till\s+|spil\s+til\s+
        )
    """, re.I | re.VERBOSE)
    is_game_signal = bool(GAME_SIGNAL_RE.search(t_f))

    SCREEN_RE = re.compile(r"\b(ekran|screen|lcd|ecran|display\s*(ips|oled|tft|lcd)?|wyświetlacz)\b", re.I)
    if SCREEN_RE.search(t_f): return False, "PART"

    has_konsola_in_title = bool(CONSOLE_MAIN_RE.search(t_f)) or "konsola" in t_f or "console" in t_f
    has_bundle_signal = bool(BUNDLE_RE.search(t_f))

    if PARTS_RE.search(t_f) or ADAPTER_MAIN_RE.search(t_f):
        return False, "PART"

    # 5. Dopasowanie kategorii HW (sprzętu)
    hw_cat = None
    for cat_name, pattern in HW_PATTERNS.items():
        if pattern.search(t_f):
            hw_cat = cat_name
            break

    if hw_cat:
        if is_game_signal and not has_bundle_signal:
            return False, "SINGLE_GAME"
        if not has_konsola_in_title and not has_bundle_signal:
            return False, "SINGLE_GAME"

    if not hw_cat:
        return False, "NO_CAT"

    # Granice cenowe dla poszczególnych konsol
    limits = {
        "PSP":     (40, 220),
        "VITA":    (100, 550),
        "3DS":     (80, 550),
        "DS":      (40, 180),
        "RETRO":   (40, 300),
        "SWITCH":  (250, 700),
        "PEN":     (50, 120),
    }
    lo, hi = limits.get(hw_cat, (40, 1000))
    if lo <= price <= hi: return True, hw_cat
    return False, "PRICE"

# ---------------------------------------------------------------------------
# PROCESS ITEM
# ---------------------------------------------------------------------------

def process_item(title, url, price, src, item_id=None, suppress=False):
    if src == "VINTED":
        log_debug(f"TEST VINTED TITLE: {title}")
    if item_id:
        if item_id in SENT_IDS:
            return False
        SENT_IDS.add(item_id)

    clean_url = url.split("?")[0].rstrip("/")
    content_hash = hashlib.md5(
    f"{title.lower().strip()}_{price}_{clean_url}".encode()
    ).hexdigest()

    if is_duplicate(clean_url, content_hash):
        return False

    valid, res = is_interesting_item(title, price)

    if valid:
        if suppress:
            save_to_memory(clean_url, content_hash)
            return False
            
        save_to_memory(clean_url, content_hash)
        
        msg = (
        f"🔥 *OKAZJA {src}* [{res}]\n"
        f"📦 {escape_md(title[:70])}\n"
        f"💰 `{price:.2f} zł`\n"
        f"🔗 {clean_url}"
        )
        
        send_telegram(msg)
        log_debug(f"🎯 WYSŁANO: {title[:50]} ({price} zł) [{res}]")
        
        return True
        
    else:
        save_to_memory(clean_url, content_hash)
        if res not in ["JUNK_EXCLUDE", "PKMN_JUNK", "NO_CAT"] and not suppress:
            log_debug(f"⛔ [{res}] {title[:50]} ({price} zł)")
        elif res == "NO_CAT" and not suppress:
            if any(w in title.lower() for w in ["nintendo", "sony", "playstation", "console", "konsola", "game"]):
                log_debug(f"❓ [NIE_ROZPOZNANO] {title[:50]} ({price} zł)")
        return False

# ---------------------------------------------------------------------------
# PĘTLA GŁÓWNA
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_debug("🚀 SNIPER v77.0 | Naprawione dopasowanie konsol i wyczyszczone logi NO_CAT")
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
        "gameboy pocket", "gameboy light",
        "pokemon etb", "pokemon elite trainer box",
        "pokemon booster box", "pokemon booster bundle",
        "pokemon tin", "pokemon mini tin", "pokemon blister",
        # --- GRADED ---
        "pokemon psa 10", "pokemon psa 9",
        "pokemon bgs 10", "pokemon bgs 9",
        "pokemon cgc 10", "pokemon cgc 9",
        "pokemon graded psa", "pokemon graded cgc",
        "pokemon ace grading", "pokemon sgc",
        # --- GRADED JAPOŃSKIE ---
        "ポケモン psa 10", "ポケモン psa 9",
        "ポケモン bgs 10", "ポケモン bgs 9",
        "ポケモン cgc 10", "ポケモン cgc 9",
        "ポケモン psa graded", "pokemon japanese psa",
        "pokemon japanese graded", "pokemon jp psa",
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
        # --- GRADED ---
        "pokemon psa 10", "pokemon psa 9",
        "pokemon bgs 9", "pokemon cgc 10",
        "pokemon graded",
        # --- GRADED JAPOŃSKIE ---
        "ポケモン psa 10", "ポケモン psa 9",
        "pokemon japanese psa", "pokemon jp graded",
    ]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800)
            continue

        v_list = Q_V.copy()
        pl_list = Q_PL.copy()
        random.shuffle(v_list)
        random.shuffle(pl_list)

        # =========================
        # VINTED — CO 15 MINa
        # =========================
        now = time.time()
        if now - LAST_VINTED_SCAN >= VINTED_SCAN_INTERVAL:
            log_debug("🔎 Start skanu Vinted (15 min interval)")
            vinted_ok = False

            for q_v in v_list:
                ok = scrape_vinted(q_v, first_run=FIRST_RUN_VINTED)
                
                if ok:
                    vinted_ok = True

                time.sleep(random.uniform(5, 8))

            time.sleep(random.uniform(8, 14))

            LAST_VINTED_SCAN = now

            if vinted_ok and FIRST_RUN_VINTED:
                FIRST_RUN_VINTED = False
                log_debug("✅ Vinted — pierwszy skan zakończony, powiadomienia aktywne")
        else:
            remaining = int((VINTED_SCAN_INTERVAL - (now - LAST_VINTED_SCAN)) // 60)
            log_debug(f"⏳ Vinted — kolejny skan za ~{remaining} min")

        # =========================
        # OLX + ALLEGRO — CO PĘTLĘ
        # =========================
        olx_ok = False
        allegro_ok = False

        for q_pl in pl_list:
            ok_olx = scrape_olx(q_pl, first_run=FIRST_RUN_OLX)
            if ok_olx:
                olx_ok = True
            time.sleep(random.uniform(2, 4))

            ok_al = scrape_allegro_lokalnie(q_pl, first_run=FIRST_RUN_ALLEGRO)
            if ok_al:
                allegro_ok = True
            time.sleep(random.uniform(3, 5))

        if olx_ok and FIRST_RUN_OLX:
            FIRST_RUN_OLX = False
            log_debug("✅ OLX — pierwszy skan zakończony, powiadomienia aktywne")

        if allegro_ok and FIRST_RUN_ALLEGRO:
            FIRST_RUN_ALLEGRO = False
            log_debug("✅ Allegro — pierwszy skan zakończony, powiadomienia aktywne")

        log_debug("💤 Przerwa 5 min.")
        time.sleep(300)
