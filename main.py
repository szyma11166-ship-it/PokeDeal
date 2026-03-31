import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib

# --- KONFIGURACJA KLUCZY ---
WEBSCRAPING_KEYS = [
    "7a2ddce7-a25e-4126-8f72-e67fd107e261", # Klucz 1
    "b495cdb4-453c-4dc7-8bb0-2b8120c93394"  # Klucz 2
]
OLOSTEP_TOKEN = "olostep_ElxXEs8WCSrtaPU3RE5E3azbuMDEe6Vx03Rv"
STAKEWATCH_URL = "https://agent.stakewatch.dev/api/scrape?url="

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()
IS_FIRST_RUN = True
CURRENT_KEY_INDEX = 0 

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_night_time():
    godzina = int(time.strftime("%H"))
    return 1 <= godzina < 6

def is_interesting_item(title, price):
    t_f = title.lower()
    if any(x in t_f for x in ["r36s", "miyoo", "anbernic", "powkiddy", "sf2000", "emulator", "stojak", "case"]): return False, "TRASH"
    
    cat = None
    if "pokemon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb"]): cat = "TCG_DISPLAY"
    if not cat:
        if any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
        elif "psp" in t_f and "konsola" in t_f: cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"
    
    limits = {"PSP": 280, "VITA": 650, "3DS": 500, "2DS": 450, "RETRO": 400, "TCG_ETB": 350, "TCG_DISPLAY": 700}
    if 70 < price <= limits.get(cat, 999): return True, cat
    return False, "PRICE"

def get_vinted_html(target_url):
    global CURRENT_KEY_INDEX
    
    # KROK 1: WebScraping.ai (Twoje główne paliwo)
    if CURRENT_KEY_INDEX < len(WEBSCRAPING_KEYS):
        key = WEBSCRAPING_KEYS[CURRENT_KEY_INDEX]
        try:
            api_url = f"https://api.webscraping.ai/html?api_key={key}&url={target_url}"
            r = requests.get(api_url, timeout=20)
            if r.status_code == 200: return r.text
            elif r.status_code in [402, 429]:
                log_debug(f"⚠️ WebScraping Key {CURRENT_KEY_INDEX+1} wyczerpany.")
                CURRENT_KEY_INDEX += 1
                return get_vinted_html(target_url)
        except:
            CURRENT_KEY_INDEX += 1
            return get_vinted_html(target_url)

    # KROK 2: OloStep API
    if OLOSTEP_TOKEN:
        try:
            log_debug("🔄 Próba przez OloStep...")
            h = {"Authorization": f"Bearer {OLOSTEP_TOKEN}", "Content-Type": "application/json"}
            r = requests.post("https://api.olostep.com/v1/scrapes", json={"url_to_scrape": target_url}, headers=h, timeout=25)
            if r.status_code == 200:
                return r.json().get('default_snapshot', {}).get('content', '')
        except: pass

    # KROK 3: Stakewatch API (Nowość)
    try:
        log_debug("🔄 Próba przez Stakewatch...")
        r = requests.get(f"{STAKEWATCH_URL}{target_url}", timeout=25)
        if r.status_code == 200: return r.text
    except: pass

    log_debug("❌ Wszystkie API zawiodły w tym cyklu.")
    return None

def scrape_olx(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&limit=15"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val: process_item(o['title'], o['url'], float(p_val), "OLX")
    except: pass

def scrape_vinted(query):
    v_url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
    html = get_vinted_html(v_url)
    if not html: return

    try:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
        for card in cards[:10]:
            txt = card.get_text(separator=" ").lower()
            if any(x in txt for x in ["dni", "vakar", "days"]): continue
            link = card.find("a", href=True)
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
            if link and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link.get("title", "") or "Item", link['href'], price, "VINTED")
    except: pass

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
            log_debug(f"🎯 WYSŁANO: {title[:15]} ({price} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.80 | MULTI-SHIELD MODE")
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy", "pokemon etb", "pokemon booster box"]
    
    while True:
        if is_night_time():
            log_debug("🌙 Noc. Śpię..."); time.sleep(2400); continue

        CURRENT_KEY_INDEX = 0 # Reset kluczy na start każdego cyklu
        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(10, 20))
            scrape_vinted(q)
            time.sleep(random.randint(15, 30))
        
        if IS_FIRST_RUN:
            log_debug("✅ Baza gotowa. Czekam na okazje...")
            IS_FIRST_RUN = False
        
        log_debug(f"🔄 Cykl zakończony (Baza: {len(SENT_HASHES)}). Śpię 15 min...")
        time.sleep(random.randint(900, 1100))
