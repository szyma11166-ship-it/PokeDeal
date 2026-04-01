import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os, json
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()

# --- KLUCZE (Bez zmian) ---
SCRAPINGDOG_KEY = "69cc2236cca5a0331e084197"
SCRAPINGANT_KEY = "5587f74b5a154af9a235f145e72cfdec"
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

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True
OLO_INDEX = 0

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_night_time():
    h = int(time.strftime("%H"))
    return h >= 23 or h < 6

def get_html_title(html):
    if not html: return "PUSTY HTML"
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    return match.group(1).strip() if match else "BRAK TYTUŁU"

def is_blocked_html(html):
    if not html or len(html) < 2500: return True
    h_l = html.lower()
    return any(x in h_l for x in ["datadome", "captcha", "verify you are human", "robot check", "just a moment"])

def is_interesting_item(title, price):
    t_f = title.lower()
    if any(x in t_f for x in ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "gra ", "gry ", "game", "games"]): 
        return False, "TRASH"
    
    cat = None
    if "pokemon" in t_f or "pokémon" in t_f:
        if "first partner" in t_f: cat = "FIRST_PARTNER"
        elif "etb" in t_f or "elite trainer" in t_f: cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb", "boosterbox"]): cat = "TCG_BB"
        elif "bundle" in t_f: cat = "TCG_BUNDLE"
    
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
        elif "psp" in t_f and any(x in t_f for x in ["1004", "2004", "3004", "go", "street", "konsola"]): cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["nintendo ds", " dsi", " ds lite"]): cat = "DS_OLD"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "gbc", "color", "advance"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"
    
    limits = {"PSP": 250, "VITA": 650, "3DS": 500, "2DS": 350, "DS_OLD": 160, "RETRO": 300, "TCG_ETB": 300, "TCG_BB": 750, "TCG_BUNDLE": 160, "FIRST_PARTNER": 120}
    if 49 < price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

def extract_vinted_items(html):
    found = []
    if not html: return found
    
    # METODA 1: SZUKANIE W JSON (Najskuteczniejsza)
    try:
        # Vinted często trzyma dane w tagu script z id "z-vinted-dotnet-initial-state" lub podobnym
        json_blobs = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html)
        for blob in json_blobs:
            if '"items"' in blob and '"price"' in blob:
                data = json.loads(blob)
                # Przeszukiwanie zagnieżdżonego słownika w poszukiwaniu listy 'items'
                def find_items(d):
                    if isinstance(d, dict):
                        if 'items' in d and isinstance(d['items'], list):
                            return d['items']
                        for v in d.values():
                            res = find_items(v)
                            if res: return res
                    elif isinstance(d, list):
                        for i in d:
                            res = find_items(i)
                            if res: return res
                    return None
                
                items_list = find_items(data)
                if items_list:
                    for it in items_list:
                        title = it.get('title') or it.get('name')
                        url = it.get('url')
                        price = it.get('price', {}).get('amount') or it.get('price')
                        if title and url and price:
                            full_url = url if "vinted.pl" in url else f"https://www.vinted.pl{url}"
                            found.append({"title": str(title), "url": full_url, "price": float(price)})
    except: pass

    # METODA 2: FALLBACK (Jeśli JSON zawiedzie, szukamy prymitywnie po linkach i cenach)
    if not found:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            if "/items/" in a['href'] and "zł" in a.get_text():
                txt = a.get_text(separator=" ").lower()
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if p_match:
                    p = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    found.append({"title": a.get("title") or "Vinted Item", "url": f"https://www.vinted.pl{a['href']}", "price": p})

    return found

def scrape_vinted_with_retries(query):
    global OLO_INDEX
    q_enc = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_enc}&order=newest_first&currency=PLN"
    
    # Próba 1: ScrapingDog
    try:
        r = requests.get("https://api.scrapingdog.com/scrape", params={"api_key": SCRAPINGDOG_KEY, "url": target_url, "dynamic": "true"}, timeout=35)
        items = extract_vinted_items(r.text) if r.status_code == 200 and not is_blocked_html(r.text) else []
        if items:
            log_debug(f"💎 Vinted (Dog) wyrwał {len(items)} ogłoszeń dla: {query}")
            for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
            return
    except: pass

    # Próba 2: OloStep (Tylko jeśli Dog zawiedzie)
    while OLO_INDEX < len(OLOSTEP_KEYS):
        try:
            h = {"Authorization": f"Bearer {OLOSTEP_KEYS[OLO_INDEX]}", "Content-Type": "application/json"}
            r = requests.post("https://api.olostep.com/v1/scrapes", json={"url_to_scrape": target_url}, headers=h, timeout=45)
            if r.status_code == 200:
                html = r.json().get('default_snapshot', {}).get('content', '')
                items = extract_vinted_items(html) if not is_blocked_html(html) else []
                if items:
                    log_debug(f"💎 Vinted (OloStep {OLO_INDEX+1}) wyrwał {len(items)} ogłoszeń dla: {query}")
                    for item in items: process_item(item['title'], item['url'], item['price'], "VINTED")
                    return
            OLO_INDEX += 1
        except: OLO_INDEX += 1
    
    log_debug(f"❌ Vinted PUSTE mimo JSON Mining: {query}")

def scrape_olx(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://www.olx.pl/api/v1/offers/?query={q_enc}&sort_by=created_at:desc&limit=20"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val: process_item(o['title'], o['url'], float(p_val), "OLX")
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
    log_debug("🚀 SNIPER v19.90 | JSON DEEP MINING MODE")
    QUERIES = ["nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy advance", "gameboy color", "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"]
    
    while True:
        if is_night_time():
            log_debug("🌙 Nocna pauza..."); time.sleep(1800); continue
        
        if time.strftime("%H:%M") == "06:00": OLO_INDEX = 0

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(random.randint(5, 10))
            scrape_vinted_with_retries(q)
            time.sleep(random.randint(20, 30))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)})."); IS_FIRST_RUN = False
        
        time.sleep(900)
