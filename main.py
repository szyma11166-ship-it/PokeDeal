import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os, json
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
SCRAPER_KEYS = ["558dd7ae69a6b68bf43a2cf2cb11be37", "34fef74e3ced51e01bb8391a147e909e", "8d3241b4e907c2e9c2508ba753bdb0cf"]
CURRENT_KEY_IDX = 0
SCRAPER_DEAD = False
SCRAPING_ANT_KEY = "5587f74b5a154af9a235f145e72cfdec"

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_interesting_item(title, price):
    t_f = title.lower()
    # Śmieci (z filtrem mediów)
    trash = ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "czesci", 
             "karta", "etui", "pudełko", "pudelko", "box", "instrukcja", "ładowarka", "ladowarka", 
             "adapter", "bajka", "film", "dvd", "książka", "komiks", "płyta", "plyta", "plakat"]
    if any(x in t_f for x in trash): return False, "TRASH"
    
    # Filtr gier (Ochrona Gameboy / Konsol)
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
    
    limits = {"PSP": 250, "VITA": 650, "3DS": 550, "2DS": 400, "DS_OLD": 150, "RETRO": 300, "TCG_ETB": 300, "TCG_BB": 700, "TCG_BUNDLE": 150, "FIRST_PARTNER": 150}
    if 45 < price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

def extract_vinted_items(html):
    found = []
    if not html: return found
    
    # METODA 1: JSON Baza (najskuteczniejsza)
    try:
        json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', html)
        if json_match:
            data = json.loads(json_match.group(1))
            items_data = data.get('catalog', {}).get('items', {}).get('catalogItems', {}).get('list', [])
            for item in items_data:
                title = item.get('title')
                price = float(item.get('price', {}).get('amount', 0))
                url = item.get('url')
                if title and url:
                    full_url = f"https://www.vinted.pl{url}" if not url.startswith('http') else url
                    found.append({"title": title, "url": full_url, "price": price})
    except: pass

    # METODA 2: Klasyczny Parser (zapasowy)
    if not found:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select('div[data-testid*="grid-item"], div[class*="feed-grid__item"], div[class*="ItemBox"]')
        for item in items:
            link = item.find("a", href=True)
            if not link or "/items/" not in link['href']: continue
            price_text = item.get_text(separator=" ")
            prices = re.findall(r"(\d+[\d\s,.]*)\s?zł", price_text)
            if prices:
                try:
                    p = float(prices[0].replace(",", ".").replace(" ", ""))
                    t = link.get("title") or item.get_text().strip()[:50]
                    u = link['href']
                    full_u = u if "vinted.pl" in u else f"https://www.vinted.pl{u}"
                    found.append({"title": t, "url": full_u, "price": p})
                except: continue
    return found

def scrape_vinted(query):
    global CURRENT_KEY_IDX, SCRAPER_DEAD
    q_enc = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_enc}&order=newest_first"
    
    if not SCRAPER_DEAD:
        try:
            current_key = SCRAPER_KEYS[CURRENT_KEY_IDX]
            log_debug(f"🔍 [ScraperAPI] {query} (Klucz {CURRENT_KEY_IDX+1})...")
            
            # WYŁĄCZONY device_type=mobile, włączony rendering i premium
            params = {
                'api_key': current_key,
                'url': target_url,
                'render': 'true',
                'premium': 'true',
                'country_code': 'pl'
            }
            r = requests.get('https://api.scraperapi.com/', params=params, timeout=80)
            
            if r.status_code == 200:
                html_low = r.text.lower()
                if "datadome" in html_low or "captcha" in html_low or "verify you are a human" in html_low:
                    log_debug("⚠️ Wykryto Captcha/Datadome. Zmiana klucza...")
                    CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(SCRAPER_KEYS)
                    return

                items = extract_vinted_items(r.text)
                if items:
                    new_count = 0
                    for i in items:
                        if process_item(i['title'], i['url'], i['price'], "VINTED"):
                            new_count += 1
                    log_debug(f"✅ Znaleziono {len(items)} ofert (Nowe: {new_count})")
                    return
                else:
                    log_debug("❓ Brak przedmiotów w HTML (mimo braku blokady).")
            elif r.status_code in [403, 429]:
                CURRENT_KEY_IDX += 1
                if CURRENT_KEY_IDX >= len(SCRAPER_KEYS): SCRAPER_DEAD = True
        except Exception as e:
            log_debug(f"💥 Błąd sieciowy: {e}")

    # Rezerwowy Ant tylko jeśli ScraperAPI leży
    if SCRAPER_DEAD:
        try:
            log_debug(f"🐜 [Ant] {query}...")
            ant_url = f"https://api.scrapingant.com/v2/general?url={urllib.parse.quote(target_url)}&x-api-key={SCRAPING_ANT_KEY}&browser=true"
            r = requests.get(ant_url, timeout=50)
            if r.status_code == 200:
                items = extract_vinted_items(r.text)
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
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            log_debug(f"🎯 WYSŁANO: {title[:25]} ({price} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
        return True
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER v38.3 | DEEP VISION")
    QUERIES = ["nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy advance", "gameboy color", "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"]
    
    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800); continue
        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(2)
            scrape_vinted(q)
            time.sleep(12) 
        if IS_FIRST_RUN: IS_FIRST_RUN = False
        log_debug("💤 Koniec pętli. Przerwa 400s.")
        time.sleep(400)
