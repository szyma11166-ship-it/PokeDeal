import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re, time, random, hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()
IS_FIRST_RUN = True  

RAW_PROXY = "isp2.hydraproxy.com:9989:szykvbdhxg404595:CmaoDg885jEO6Dxb_country-Poland"
hp = RAW_PROXY.split(':')
MY_PROXY = f"http://{hp[2]}:{hp[3]}@{hp[0]}:{hp[1]}"

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. ABSOLUTNA CZARNA LISTA
    absolute_trash = ["r36s", "miyoo", "anbernic", "powkiddy", "sf2000", "emulator", "podstawk", "stojak", "stand"]
    if any(x in t_f for x in absolute_trash): return False, "TRASH"

    # 2. FILTR JĘZYKOWY (Poprawiony - szuka całych słów)
    bad_langs = [" jap ", " de ", " fr ", " it ", " kor ", "japonskie", "japanese", "niemieckie"]
    if any(x in f" {t_f} " for x in bad_langs): return False, "BAD_LANG"

    # 3. KATEGORIE
    cat = None
    if "pokemon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif "booster box" in t_f or "display" in t_f: cat = "TCG_DISPLAY"
        elif "bundle" in t_f: cat = "TCG_BUNDLE"
        elif "tin" in t_f: cat = "TCG_TIN"
    
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
        elif "psp" in t_f: cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["ds lite", "gameboy", "gba"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"

    # 4. LIMITY CENOWE (Dopasowane, żeby nie skipować okazji)
    limits = {
        "PSP": 280, "VITA": 650, "3DS": 500, "2DS": 450, "RETRO": 400,
        "TCG_ETB": 350, "TCG_DISPLAY": 650, "TCG_BUNDLE": 200, "TCG_TIN": 130
    }
    
    if price < 70: return False, "TOO_CHEAP"
    if price > limits.get(cat, 999): return False, "OVER_PRICE"

    return True, cat

def get_session():
    return cffi_requests.Session(impersonate="chrome124", proxies={"http": MY_PROXY, "https": MY_PROXY})

def scrape_olx(session, query):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&limit=20"
        r = session.get(url, timeout=10)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val and process_item(o['title'], o['url'], float(p_val), "OLX"): found += 1
    except: pass
    return found

def scrape_vinted(session, query):
    found = 0
    try:
        # Usunięcie zbędnego requestu do strony głównej (oszczędność transferu!)
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            for card in cards[:15]: # Sprawdzamy tylko 15 najnowszych (oszczędność czasu)
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "vakar", "days"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    if process_item(link.get("title", "") or "Item", link['href'], price, "VINTED"): found += 1
            return found
        return -1
    except: return -1

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:30]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, res = is_interesting_item(title, price)
    if valid:
        if IS_FIRST_RUN:
            SENT_HASHES.add(h); return False
        msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        log_debug(f"🎯 WYSŁANO: {title[:20]} ({price} zł)")
        SENT_HASHES.add(h); return True
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER ECO-MODE | Zredukowane zapytania | Oszczędność Proxy")
    # Zredukowana liczba zapytań = mniej zużytego transferu
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "pokemon etb"]
    
    while True:
        with get_session() as s:
            for q in QUERIES:
                scrape_olx(s, q)
                time.sleep(random.randint(10, 20))
                scrape_vinted(s, q)
                time.sleep(random.randint(20, 40))
        
        if IS_FIRST_RUN:
            log_debug("✅ Baza zainicjowana. Przechodzę w tryb ECO (czekam 8-12 min)...")
            IS_FIRST_RUN = False
        
        # DŁUGA PRZERWA - Twoje proxy Ci podziękuje
        time.sleep(random.randint(500, 750)) 
