import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os

# --- ARSENAŁ KLUCZY (5x500 = 2500 req) ---
OLOSTEP_KEYS = [
    "olostep_ElxXEs8WCSrtaPU3RE5E3azbuMDEe6Vx03Rv",
    "olostep_J3hXd9tU8hcP8qTHqqmFhzzrsaoG0V4neNy7",
    "olostep_Aok0E95IbyvijgPCeS4qLEFv0FJ58x3PxsP0",
    "olostep_Ai2L7IEzCRI8WY1Ofa10aHNj8PpT1p0wV18W",
    "olostep_uZYru9zWGHl60W4CO7aj5T2Dud48id3MmhPr",
    "olostep_gu9B52cJ30OV20ShHwLiMbfHUcFB1F3iVXBd",
    "olostep_MSTMsMkYk0AdyC8JoGD7hk2wrhsC3EzUmWt1",
    "olostep_KuvN0l1m3DqzjPvIVhsvp4hSBZBZ8rhLOnt6",
    "olostep_lxVgFBkSFN8LOeHLpBBBBRmwZm5YsNYC6b7P",
    "olostep_TEZ2ySYKVa93lLRbH45NDbLeyIck1ghRgEhc"
]
STAKEWATCH_URL = "https://agent.stakewatch.dev/api/scrape?url="

# TELEGRAM
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

# SYSTEM
SENT_HASHES = set()
IS_FIRST_RUN = True
OLO_INDEX = 0

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_night_time():
    h_utc = int(time.strftime("%H"))
    return h_utc >= 22 or h_utc < 4

def is_interesting_item(title, price):
    t_f = title.lower()
    if any(x in t_f for x in ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części"]): 
        return False, "TRASH"
    
    cat = None
    if "pokemon" in t_f or "pokémon" in t_f:
        if "first partner" in t_f: cat = "FIRST_PARTNER"
        elif any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb", "boosterbox"]): cat = "TCG_BB"
        elif any(x in t_f for x in ["bundle", "booster bundle"]): cat = "TCG_BUNDLE"
    
    if not cat:
        if any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
        elif "psp" in t_f and any(x in t_f for x in ["konsola", "1004", "2004", "3004", "go", "street", "e1004"]): cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "gbc", "color", "advance"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"
    
    # --- ZAKTUALIZOWANE CENY ---
    limits = {
        "PSP": 280, 
        "VITA": 650, 
        "3DS": 500, 
        "2DS": 450, 
        "RETRO": 300, # Zmieniono z 400 na 300
        "TCG_ETB": 350, 
        "TCG_BB": 700, 
        "TCG_BUNDLE": 150, # Zmieniono z 140 na 150
        "FIRST_PARTNER": 120
    }
    
    if 65 < price <= limits.get(cat, 999): 
        return True, cat
    return False, "PRICE"

def get_vinted_html(target_url):
    global OLO_INDEX
    while OLO_INDEX < len(OLOSTEP_KEYS):
        token = OLOSTEP_KEYS[OLO_INDEX]
        try:
            h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            r = requests.post("https://api.olostep.com/v1/scrapes", 
                              json={"url_to_scrape": target_url}, headers=h, timeout=25)
            if r.status_code == 200:
                return r.json().get('default_snapshot', {}).get('content', '')
            elif r.status_code in [401, 402, 429]:
                log_debug(f"⚠️ OloStep {OLO_INDEX+1} wyczerpany. Skok...")
                OLO_INDEX += 1
            else:
                OLO_INDEX += 1
        except: OLO_INDEX += 1

    try:
        r = requests.get(f"{STAKEWATCH_URL}{target_url}", timeout=25)
        if r.status_code == 200: return r.text
    except: pass
    return None

def scrape_olx(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc&limit=20"
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
        for card in cards[:12]:
            txt = card.get_text(separator=" ").lower()
            if any(x in txt for x in ["dni temu", "vakar", "days ago"]): continue
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
    log_debug("🚀 SNIPER v18.60 | FINAL SYNC")
    QUERIES = [
        "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", 
        "gameboy advance", "gameboy color", "pokemon etb", 
        "pokemon booster box", "pokemon bundle", "first partner pack"
    ]
    
    last_reset_day = time.strftime("%d")

    while True:
        if time.strftime("%d") != last_reset_day:
            OLO_INDEX = 0
            last_reset_day = time.strftime("%d")

        if is_night_time():
            log_debug("🌙 Nocna pauza..."); time.sleep(1800); continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(15, 25))
            scrape_vinted(q)
            time.sleep(random.randint(20, 35))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)}). Snajper czuwa...")
            IS_FIRST_RUN = False
        
        log_debug("🔄 Cykl OK. Sleep 15min...")
        time.sleep(900)
