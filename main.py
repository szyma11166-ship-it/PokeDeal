import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os

# --- ARSENAŁ KLUCZY (10 SHIELDS) ---
# Kolejka WebScraping.ai (4 klucze)
WEBSCRAPING_KEYS = [
    "b495cdb4-453c-4dc7-8bb0-2b8120c93394",
    "4deb3a68-ec3d-49fc-8fd0-9bbb15a4d8f9",
    "04315772-d80c-43d7-ac79-5623b87d3921",
    "7a2ddce7-a25e-4126-8f72-e67fd107e261"
]

# Kolejka OloStep (5 kluczy - dodano nowe!)
OLOSTEP_KEYS = [
    "olostep_ElxXEs8WCSrtaPU3RE5E3azbuMDEe6Vx03Rv",
    "olostep_J3hXd9tU8hcP8qTHqqmFhzzrsaoG0V4neNy7",
    "olostep_Aok0E95IbyvijgPCeS4qLEFv0FJ58x3PxsP0",
    "olostep_Ai2L7IEzCRI8WY1Ofa10aHNj8PpT1p0wV18W",
    "olostep_uZYru9zWGHl60W4CO7aj5T2Dud48id3MmhPr"
]

STAKEWATCH_URL = "https://agent.stakewatch.dev/api/scrape?url="

# --- KONFIGURACJA TELEGRAM ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

# --- ZMIENNE SYSTEMOWE ---
SENT_HASHES = set()
IS_FIRST_RUN = True
WS_INDEX = 0 
OLO_INDEX = 0

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_night_time():
    # Railway używa UTC. Polska to ok. UTC+2.
    # godzina_utc >= 22 (północ w PL) do < 4 (6:00 rano w PL)
    h_utc = int(time.strftime("%H"))
    return h_utc >= 22 or h_utc < 4

def is_interesting_item(title, price):
    t_f = title.lower()
    # Śmieciarka - odrzucamy chińskie emulatory i części
    blacklist = ["r36s", "miyoo", "anbernic", "powkiddy", "sf2000", "emulator", "stojak", "case", "uchwyt", "naprawa", "części", "uszkodzon"]
    if any(x in t_f for x in blacklist): 
        return False, "TRASH"
    
    cat = None
    if "pokemon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb"]): cat = "TCG_DISPLAY"
    
    if not cat:
        if any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
        elif "psp" in t_f and any(x in t_f for x in ["konsola", "console", "1004", "2004", "3004", "go", "street"]): cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "color"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"
    
    # Ceny maksymalne dla Twoich okazji
    limits = {"PSP": 280, "VITA": 650, "3DS": 550, "2DS": 450, "RETRO": 420, "TCG_ETB": 350, "TCG_DISPLAY": 750}
    if 60 < price <= limits.get(cat, 999): 
        return True, cat
    return False, "PRICE"

def get_vinted_html(target_url):
    global WS_INDEX, OLO_INDEX
    
    # --- POZIOM 1: WebScraping.ai ---
    while WS_INDEX < len(WEBSCRAPING_KEYS):
        key = WEBSCRAPING_KEYS[WS_INDEX]
        try:
            api_url = f"https://api.webscraping.ai/html?api_key={key}&url={target_url}"
            r = requests.get(api_url, timeout=30) # Zwiększony timeout
            if r.status_code == 200: 
                return r.text
            else:
                log_debug(f"⚠️ WebScraping Kod: {r.status_code} (Klucz {WS_INDEX+1})")
                WS_INDEX += 1 # Jeśli nie 200, to idź do następnego
        except Exception as e:
            log_debug(f"❌ WebScraping Błąd Sieci: {str(e)[:50]}")
            WS_INDEX += 1

    # --- POZIOM 2: OloStep ---

    while OLO_INDEX < len(OLOSTEP_KEYS):
        token = OLOSTEP_KEYS[OLO_INDEX]
        try:
            log_debug(f"🔄 Shield: OloStep Key {OLO_INDEX+1}...")
            h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            r = requests.post("https://api.olostep.com/v1/scrapes", json={"url_to_scrape": target_url}, headers=h, timeout=25)
            if r.status_code == 200:
                return r.json().get('default_snapshot', {}).get('content', '')
            elif r.status_code in [401, 402, 429]:
                log_debug(f"⚠️ OloStep {OLO_INDEX+1} pusty. Skok...")
                OLO_INDEX += 1
            else: break
        except: OLO_INDEX += 1

    # --- POZIOM 3: Stakewatch (Ostatni bastion) ---
    try:
        log_debug("🔄 Shield: Stakewatch Backup...")
        r = requests.get(f"{STAKEWATCH_URL}{target_url}", timeout=25)
        if r.status_code == 200: return r.text
    except: pass

    log_debug("❌ KATastrofa: Wszystkie klucze wyczerpane!")
    return None

def scrape_olx(query):
    try:
        # OLX leci bezpośrednio z IP Railway
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
            # Omijamy stare oferty (sprzed dni/vakar)
            if any(x in txt for x in ["dni temu", "vakar", "days ago", "ilgiem"]): continue
            link = card.find("a", href=True)
            p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
            if link and p_match:
                price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                process_item(link.get("title", "") or "Przedmiot", link['href'], price, "VINTED")
    except: pass

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    # Unikalny hash, żeby nie słać dubli
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
    log_debug("🚀 SNIPER v18.10 | RAILWAY FULL-POWER")
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "pokemon etb", "pokemon booster box"]
    
    last_reset_day = time.strftime("%d")

    while True:
        # Reset kluczy o północy UTC
        current_day = time.strftime("%d")
        if current_day != last_reset_day:
            log_debug("🌅 Nowy dzień! Odświeżam listę kluczy API...")
            WS_INDEX = 0
            OLO_INDEX = 0
            last_reset_day = current_day

        if is_night_time():
            log_debug("🌙 Nocna pauza (00:00-06:00 PL). Śpię 30 min...")
            time.sleep(1800)
            continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(15, 25))
            scrape_vinted(q)
            time.sleep(random.randint(20, 40))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)} ofert). Snajper czuwa...")
            IS_FIRST_RUN = False
        
        log_debug(f"🔄 Cykl OK. Baza: {len(SENT_HASHES)}. Sleep...")
        time.sleep(random.randint(900, 1100))
