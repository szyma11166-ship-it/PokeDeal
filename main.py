import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re, time, random, hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()
IS_FIRST_RUN = True  

# Dane HydraProxy (Podmień jak zmienisz dostawcę)
RAW_PROXY = "isp2.hydraproxy.com:9989:szykvbdhxg404595:CmaoDg885jEO6Dxb_country-Poland"
hp = RAW_PROXY.split(':')
MY_PROXY = f"http://{hp[2]}:{hp[3]}@{hp[0]}:{hp[1]}"

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_night_time():
    """Zwraca True, jeśli jest między 01:00 a 06:00 rano (czasu serwera)."""
    # Jeśli serwer ma czas o 2h do tyłu, 1:00-6:00 u niego to 3:00-8:00 u nas.
    godzina = int(time.strftime("%H"))
    return 1 <= godzina < 6

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. ABSOLUTNA CZARNA LISTA
    absolute_trash = ["r36s", "miyoo", "anbernic", "powkiddy", "sf2000", "emulator", "podstawk", "stojak", "stand"]
    if any(x in t_f for x in absolute_trash): return False, "TRASH"

    # 2. FILTR JĘZYKOWY (Szuka całych słów, żeby nie psuć 'order' lub 'elite')
    bad_langs = [" jap ", " de ", " fr ", " it ", " kor ", "japonskie", "japanese", "niemieckie"]
    if any(x in f" {t_f} " for x in bad_langs): return False, "BAD_LANG"

    # 3. KATEGORIE
    cat = None
    if "pokemon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box"]): cat = "TCG_DISPLAY"
        elif "bundle" in t_f: cat = "TCG_BUNDLE"
        elif "tin" in t_f: cat = "TCG_TIN"
    
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
        elif "psp" in t_f: cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["ds lite", "gameboy", "gba"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"

    # 4. LIMITY CENOWE (ETB podbite do 350 zł)
    limits = {
        "PSP": 280, "VITA": 650, "3DS": 500, "2DS": 450, "RETRO": 400,
        "TCG_ETB": 350, "TCG_DISPLAY": 650, "TCG_BUNDLE": 200, "TCG_TIN": 130
    }
    
    if price < 70: return False, "TOO_CHEAP"
    if price > limits.get(cat, 999): return False, "OVER_PRICED"

    return True, cat

def get_session():
    return cffi_requests.Session(impersonate="chrome124", proxies={"http": MY_PROXY, "https": MY_PROXY})

def scrape_olx(session, query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&limit=15"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val: process_item(o['title'], o['url'], float(p_val), "OLX")
        else:
            log_debug(f"⚠️ OLX Błąd: {r.status_code}")
    except Exception as e:
        log_debug(f"❌ OLX Wyjątek: {str(e)[:50]}")

def scrape_vinted(session, query):
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=15)
        
        if r.status_code != 200:
            log_debug(f"⚠️ Vinted Error {r.status_code} dla: {query}")
            return

        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
        
        if not cards:
            log_debug(f"❓ Vinted: Brak ofert dla '{query}' (Możliwa blokada?)")
            return

        for card in cards[:12]:
            txt = card.get_text(separator=" ").lower()
            if any(x in txt for x in ["dni", "vakar", "days"]): continue
            link = card.find("a", href=True)
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
            if link and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link.get("title", "") or "Item", link['href'], price, "VINTED")
    except Exception as e:
        log_debug(f"❌ Vinted Wyjątek: {str(e)[:50]}")

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:30]}_{int(price)}".encode()).hexdigest()
    
    if h in SENT_HASHES or clean_url in SENT_HASHES: return
    
    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            log_debug(f"🎯 WYSŁANO: {title[:20]} ({price} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
    elif price >= 100:
        if not IS_FIRST_RUN:
            # Opcjonalne: odkomentuj poniżej, jeśli chcesz widzieć CO bot odrzuca
            # log_debug(f"🛑 SKIP ({res}): {title[:25]}... ({price} zł)")
            pass

if __name__ == "__main__":
    log_debug("🚀 SNIPER ECO v17.47 | FULL DIAGNOSTICS")
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "pokemon etb", "pokemon booster"]
    
    while True:
        if is_night_time():
            log_debug("🌙 Tryb nocny (01-06). Śpię 40 minut...")
            time.sleep(2400)
            continue

        with get_session() as s:
            random.shuffle(QUERIES)
            for q in QUERIES:
                scrape_olx(s, q)
                time.sleep(random.randint(10, 20))
                scrape_vinted(s, q)
                time.sleep(random.randint(15, 30))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)} ofert).")
            IS_FIRST_RUN = False
        
        log_debug(f"🔄 Cykl zakończony. Pamięć: {len(SENT_HASHES)} pozycji. Śpię...")
        time.sleep(random.randint(600, 850))
