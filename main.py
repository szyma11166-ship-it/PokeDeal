import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()

# --- TWOJE NOWE KLUCZE ---
SCRAPER_API_KEY = "48611f7ab450207b4931b3d235028a60"
SCRAPING_ANT_KEY = "5587f74b5a154af9a235f145e72cfdec"
SCRAPING_DOG_KEY = "69cc2236cca5a0331e084197"

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # --- POPRAWIONY FILTR ŚMIECI ---
    # Ignorujemy gry/akcesoria, ale oszczędzamy konsole
    trash_keywords = ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "czesci"]
    if any(x in t_f for x in trash_keywords):
        return False, "TRASH"
    
    # Specyficzny filtr na gry (żeby nie wycinać słowa Gameboy/Gamegear)
    # Szukamy "gra", "gry", "game" jako osobnych słów
    if re.search(r'\b(gra|gry|game|games)\b', t_f):
        # Jeśli w tytule jest "game", ale nie ma "boy" ani "gear" ani "station", to pewnie gra
        if not any(ok in t_f for ok in ["boy", "gear", "station", "cube", "watch"]):
            return False, "SINGLE_GAME"

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
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "gbc", "color", "advance", "game boy"]): cat = "RETRO"
    
    if not cat: return False, "NO_CAT"
    
    # --- NOWE WYŻSZE LIMITY CENOWE ---
    limits = {
        "PSP": 250, 
        "VITA": 650, 
        "3DS": 550, 
        "2DS": 400, 
        "DS_OLD": 150, 
        "RETRO": 300, # Podniesione z 300, żeby łapać GBA w lepszym stanie
        "TCG_ETB": 300, 
        "TCG_BB": 700, 
        "TCG_BUNDLE": 150, 
        "FIRST_PARTNER": 150
    }
    
    if 45 < price <= limits.get(cat, 1000): 
        return True, cat
    return False, "PRICE"

def extract_vinted_items(html):
    found = []
    if not html: return found
    soup = BeautifulSoup(html, "html.parser")
    # Szukamy kafelków Vinted
    items = soup.find_all("div", attrs={"data-testid": re.compile(r"grid-item|product-item")})
    if not items: items = soup.find_all("div", class_=re.compile(r"new-item-box|feed-item"))
    
    for item in items:
        link = item.find("a", href=True)
        if not link or "/items/" not in link['href']: continue
        price_texts = re.findall(r"(\d+[\d\s,.]*)\s?zł", item.get_text(separator=" "))
        if price_texts:
            try:
                price = float(price_texts[0].replace(",", ".").replace(" ", ""))
                title = link.get("title") or "Item"
                url = link['href']
                full_url = url if "vinted.pl" in url else f"https://www.vinted.pl{url}"
                if not any(f['url'] == full_url for f in found):
                    found.append({"title": title, "url": full_url, "price": price})
            except: continue
    return found

def scrape_vinted(query):
    q_enc = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_enc}&order=newest_first"
    
    # 1. PRÓBA: ScraperAPI
    try:
        log_debug(f"🔍 [ScraperAPI] Szukam: {query}...")
        r = requests.get('https://api.scraperapi.com/', params={'api_key': SCRAPER_API_KEY, 'url': target_url}, timeout=30)
        if r.status_code == 200:
            items = extract_vinted_items(r.text)
            if items:
                log_debug(f"✅ [ScraperAPI] Znalazłem {len(items)} ofert.")
                for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
                return
            elif "datadome" in r.text.lower():
                log_debug("⚠️ [ScraperAPI] Wykryto blokadę Datadome.")
    except: pass

    # 2. PRÓBA: ScrapingAnt
    try:
        log_debug(f"🐜 [ScrapingAnt] Szukam: {query}...")
        ant_url = f"https://api.scrapingant.com/v2/general?url={urllib.parse.quote(target_url)}&x-api-key={SCRAPING_ANT_KEY}"
        r = requests.get(ant_url, timeout=30)
        if r.status_code == 200:
            items = extract_vinted_items(r.text)
            if items:
                log_debug(f"✅ [ScrapingAnt] Znalazłem {len(items)} ofert.")
                for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
                return
    except: pass

    # 3. PRÓBA: ScrapingDog (Awaryjnie)
    try:
        log_debug(f"🐕 [ScrapingDog] Szukam: {query}...")
        r = requests.get("https://api.scrapingdog.com/scrape", params={"api_key": SCRAPING_DOG_KEY, "url": target_url, "dynamic": "false"}, timeout=20)
        if r.status_code == 200:
            items = extract_vinted_items(r.text)
            if items:
                log_debug(f"✅ [ScrapingDog] Znalazłem {len(items)} ofert.")
                for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
    except: pass

def scrape_olx(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
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
            log_debug(f"🎯 WYSŁANO: {title[:20]} ({price} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)

if __name__ == "__main__":
    log_debug("🚀 SNIPER v34.0 | THE MULTI-PROXY")
    QUERIES = ["nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy advance", "gameboy color", "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"]
    
    while True:
        # PRZERWA NOCNA (01:00 - 05:59)
        current_hour = time.localtime().tm_hour
        if 1 <= current_hour < 6:
            log_debug("🌙 Przerwa nocna..."); time.sleep(1800); continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q); time.sleep(5)
            scrape_vinted(q); time.sleep(15)
            
        if IS_FIRST_RUN: 
            log_debug("✅ Baza początkowa gotowa."); IS_FIRST_RUN = False
            
        log_debug("💤 Koniec pętli. Przerwa 400s.")
        time.sleep(400)