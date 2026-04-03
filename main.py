import subprocess, sys
try:
    from vinted_api_wrapper import Vinted
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "vinted-api-wrapper", "--quiet"])

import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True

# --- VINTED WRAPPER ---
try:
    from vinted_api_wrapper import Vinted
    vinted = Vinted(domain="pl")
    VINTED_OK = True
    print("✅ vinted-api-wrapper załadowany")
except Exception as e:
    VINTED_OK = False
    print(f"❌ Brak vinted-api-wrapper: {e} — zainstaluj: pip install vinted-api-wrapper")

# --- SESJE ---
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

# --- VINTED ---
def scrape_vinted(query):
    if not VINTED_OK:
        return
    try:
        results = vinted.search(query, per_page=30, order="newest_first")
        items = getattr(results, "items", []) or []
        new_count = 0
        for item in items:
            title = getattr(item, "title", "") or ""
            price_obj = getattr(item, "price", None)
            if price_obj is None:
                continue
            if hasattr(price_obj, "amount"):
                price = float(price_obj.amount)
            else:
                price = float(price_obj)
            url = getattr(item, "url", "") or ""
            if not url.startswith("http"):
                url = f"https://www.vinted.pl{url}"
            if process_item(title, url, price, "VINTED"):
                new_count += 1
        log_debug(f"✅ Vinted [{query}]: {len(items)} ofert, {new_count} nowych")
    except Exception as e:
        log_debug(f"💥 Błąd Vinted: {e}")

# --- OLX ---
def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if p_val:
                    if process_item(o['title'], o['url'], float(p_val), "OLX"):
                        new_count += 1
            log_debug(f"✅ OLX [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd OLX: {e}")

# --- ALLEGRO LOKALNIE ---
def scrape_allegro_lokalnie(query):
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://allegrolokalnie.pl/oferty?phrase={q_enc}&sort=createdAt-desc"
        r = ALLEGRO_SESSION.get(url, timeout=20)
        if r.status_code != 200:
            log_debug(f"⚠️ Allegro Lokalnie status: {r.status_code}")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        new_count = 0
        items = soup.select("article[data-testid='listing-ad'], div[class*='mlc-itemcard'], article[class*='offer-card']")
        if not items:
            items = soup.select("a[href*='/oferta/']")

        for item in items:
            try:
                link = item if item.name == 'a' else item.find("a", href=lambda h: h and "/oferta/" in h)
                if not link:
                    continue
                item_url = link.get("href", "")
                if not item_url.startswith("http"):
                    item_url = f"https://allegrolokalnie.pl{item_url}"

                title_el = item.find(["h2", "h3", "span"], class_=re.compile(r"title|name|heading", re.I))
                title = title_el.get_text(strip=True) if title_el else item.get_text(separator=" ")[:60]

                price_text = item.get_text(separator=" ")
                price_match = re.search(r"(\d[\d\s]*(?:[,\.]\d{1,2})?)\s*zł", price_text)
                if not price_match:
                    continue
                price = float(price_match.group(1).replace(" ", "").replace(",", "."))

                if title and price:
                    if process_item(title.strip(), item_url, price, "ALLEGRO"):
                        new_count += 1
            except:
                continue

        log_debug(f"✅ Allegro Lokalnie [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd Allegro Lokalnie: {e}")

# --- FILTR OKAZJI ---
def is_interesting_item(title, price):
    t_f = title.lower()
    trash = ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "czesci",
             "karta", "etui", "pudełko", "pudelko", "box", "instrukcja", "ładowarka", "ladowarka",
             "adapter", "bajka", "film", "dvd", "książka", "komiks", "płyta", "plyta", "plakat",
             "obudowa", "r4i"]
    if any(x in t_f for x in trash): return False, "TRASH"

    if re.search(r'\b(gra|gry|game|games)\b', t_f):
        if not any(ok in t_f for ok in ["boy", "gear", "station", "cube", "watch", "advance", "color", "dsi", "vita", "konsola"]):
            return False, "SINGLE_GAME"

    cat = None
    if "pokemon" in t_f or "pokémon" in t_f:
        if "first partner" in t_f: cat = "FIRST_PARTNER"
        elif any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb", "boosterbox"]): cat = "TCG_BB"
        elif "bundle" in t_f: cat = "TCG_BUNDLE"

    if not cat:
        if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
        elif "psp" in t_f: cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["nintendo ds", "dsi", "ds lite", "ds xl"]): cat = "DS_OLD"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "gbc", "color", "advance", "game boy"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"

    limits = {
        "PSP": 250, "VITA": 650, "3DS": 550, "2DS": 400,
        "DS_OLD": 150, "RETRO": 300, "TCG_ETB": 300,
        "TCG_BB": 700, "TCG_BUNDLE": 150, "FIRST_PARTNER": 150
    }
    if 45 < price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

# --- WYSYŁKA ---
def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:30]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            send_telegram(msg)
            log_debug(f"🎯 WYSŁANO: {title[:25]} ({price} zł)")
        SENT_HASHES.add(h)
        SENT_HASHES.add(clean_url)
        return True
    return False

# --- GŁÓWNA PĘTLA ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER v39.6 | OLX + VINTED WRAPPER + ALLEGRO LOKALNIE")

    QUERIES = [
        "nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds",
        "nintendo 2ds", "gameboy advance", "gameboy color",
        "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"
    ]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800)
            continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(2)
            scrape_vinted(q)
            time.sleep(3)
            scrape_allegro_lokalnie(q)
            time.sleep(random.randint(4, 8))

        if IS_FIRST_RUN:
            IS_FIRST_RUN = False

        log_debug("💤 Koniec pętli. Przerwa 300s.")
        time.sleep(300)