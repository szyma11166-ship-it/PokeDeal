import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

# Ustawienie strefy czasowej
os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()

# --- MAGAZYNEK KLUCZY ---
SCRAPER_KEYS = [
    "558dd7ae69a6b68bf43a2cf2cb11be37",
    "34fef74e3ced51e01bb8391a147e909e",
    "8d3241b4e907c2e9c2508ba753bdb0cf"
]
CURRENT_KEY_IDX = 0
SCRAPER_DEAD = False

SCRAPING_ANT_KEY = "5587f74b5a154af9a235f145e72cfdec"
SCRAPING_DOG_KEY = "69cc2236cca5a0331e084197"

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def send_telegram_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def is_interesting_item(title, price):
    t_f = title.lower()
    
    # 1. ŚMIECI
    trash = ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "czesci", 
             "karta", "etui", "pudełko", "pudelko", "box", "instrukcja", "ładowarka", "ladowarka", "adapter"]
    if any(x in t_f for x in trash): return False, "TRASH"
    
    # 2. FILTR GIER (Z ochroną Gameboya/Konsol)
    if re.search(r'\b(gra|gry|game|games)\b', t_f):
        # Sprawdzamy, czy to na pewno nie konsola
        if not any(ok in t_f for ok in ["boy", "gear", "station", "cube", "watch", "advance", "color", "dsi", "vita", "konsola"]):
            return False, "SINGLE_GAME"

    # 3. KATEGORYZACJA
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
    
    # 4. TWOJE SZTYWNE CENY
    limits = {
        "PSP": 250, "VITA": 650, "3DS": 550, "2DS": 400, "DS_OLD": 150, 
        "RETRO": 300, "TCG_ETB": 300, "TCG_BB": 700, "TCG_BUNDLE": 150, "FIRST_PARTNER": 150
    }
    
    if 45 < price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

def extract_vinted_items(html):
    found = []
    if not html: return found
    soup = BeautifulSoup(html, "html.parser")
    # Vinted przy renderingu JS często zmienia klasy, szukamy szeroko
    items = soup.find_all("div", attrs={"data-testid": re.compile(r"grid-item|product-item")})
    if not items: items = soup.select('div[class*="feed-grid__item"]')
    if not items: items = soup.find_all("div", class_=re.compile(r"new-item-box|feed-item"))
    
    for item in items:
        link = item.find("a", href=True)
        if not link or "/items/" not in link['href']: continue
        price_texts = re.findall(r"(\d+[\d\s,.]*)\s?zł", item.get_text(separator=" "))
        if price_texts:
            try:
                price = float(price_texts[0].replace(",", ".").replace(" ", ""))
                title = link.get("title") or item.get_text().strip()[:50]
                url = link['href']
                full_url = url if "vinted.pl" in url else f"https://www.vinted.pl{url}"
                if not any(f['url'] == full_url for f in found):
                    found.append({"title": title, "url": full_url, "price": price})
            except: continue
    return found

def scrape_vinted(query):
    global CURRENT_KEY_IDX, SCRAPER_DEAD
    q_enc = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_enc}&order=newest_first"
    
    if not SCRAPER_DEAD:
        try:
            current_key = SCRAPER_KEYS[CURRENT_KEY_IDX]
            log_debug(f"🔍 [ScraperAPI] Szukam: {query} (Klucz {CURRENT_KEY_IDX+1} + RENDER)...")
            
            # WŁĄCZAMY RENDER I COUNTRY_CODE
            params = {
                'api_key': current_key,
                'url': target_url,
                'render': 'true',
                'country_code': 'pl'
            }
            r = requests.get('https://api.scraperapi.com/', params=params, timeout=40)
            
            if r.status_code == 200:
                if "datadome" in r.text.lower():
                    log_debug("⚠️ Blokada Datadome mimo renderingu!")
                    return

                items = extract_vinted_items(r.text)
                if items:
                    log_debug(f"✅ [ScraperAPI] Znalazłem {len(items)} ofert.")
                    for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
                    return
                else:
                    log_debug("❓ Brak ofert w HTML (mimo statusu 200).")
            elif r.status_code in [403, 429]:
                log_debug(f"❌ Klucz {CURRENT_KEY_IDX+1} pusty.")
                CURRENT_KEY_IDX += 1
                if CURRENT_KEY_IDX >= len(SCRAPER_KEYS):
                    SCRAPER_DEAD = True
                    send_telegram_alert("🚨 *Klucze ScraperAPI wyczerpane!* Jedziemy na awaryjnym Ant.")
        except Exception as e:
            log_debug(f"💥 Błąd: {e}")

    # AWARYJNY ANT (Tylko jak ScraperAPI padnie)
    if SCRAPER_DEAD:
        try:
            log_debug(f"🐜 [ScrapingAnt] Szukam: {query}...")
            ant_url = f"https://api.scrapingant.com/v2/general?url={urllib.parse.quote(target_url)}&x-api-key={SCRAPING_ANT_KEY}&browser=false"
            r = requests.get(ant_url, timeout=30)
            if r.status_code == 200:
                items = extract_vinted_items(r.text)
                if items:
                    log_debug(f"✅ [ScrapingAnt] Znalazłem {len(items)} ofert.")
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
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK DO OFERTY]({clean_url})"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            log_debug(f"🎯 WYSŁANO: {title[:25]} ({price} zł)")
        SENT_HASHES.add(h)
        SENT_HASHES.add(clean_url)

if __name__ == "__main__":
    log_debug("🚀 SNIPER v37.0 | RENDER MODE ON")
    QUERIES = ["nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy advance", "gameboy color", "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"]
    
    while True:
        current_hour = time.localtime().tm_hour
        if 1 <= current_hour < 6:
            log_debug("🌙 Przerwa nocna...")
            time.sleep(1800); continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(2)
            scrape_vinted(q)
            time.sleep(12) 
            
        if IS_FIRST_RUN: 
            log_debug("✅ Baza początkowa gotowa.")
            IS_FIRST_RUN = False
            
        log_debug("💤 Koniec pętli. Przerwa 400s.")
        time.sleep(400)