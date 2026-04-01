import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()

# --- KLUCZE ---
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
    godzina_pl = int(time.strftime("%H"))
    return godzina_pl >= 23 or godzina_pl < 6

def get_html_title(html):
    if not html: return "PUSTY HTML"
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
    return match.group(1).strip() if match else "BRAK TYTUŁU"

def is_blocked_html(html):
    if not html or len(html) < 2000: return True
    h_l = html.lower()
    return any(x in h_l for x in ["datadome", "captcha", "cloudflare", "verify you are human", "robot check", "just a moment", "challenge"])

def is_interesting_item(title, price):
    t_f = title.lower()
    if any(x in t_f for x in ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "gra", "gry", "game", "games"]): 
        return False, "TRASH"
    
    cat = None
    if "pokemon" in t_f or "pokémon" in t_f:
        if "first partner" in t_f: cat = "FIRST_PARTNER"
        elif any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif any(x in t_f for x in ["display", "booster box", "bb", "boosterbox"]): cat = "TCG_BB"
        elif any(x in t_f for x in ["bundle", "booster bundle"]): cat = "TCG_BUNDLE"
    
    if not cat:
        if any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
        elif "psp" in t_f and any(x in t_f for x in ["1004", "2004", "3004", "go", "street", "e1004", "konsola"]): cat = "PSP"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif any(x in t_f for x in ["nintendo ds", " dsi ", " ds lite ", " dsi xl "]): cat = "DS_OLD"
        elif any(x in t_f for x in ["gameboy", "gba", "dmg", "gbc", "color", "advance"]): cat = "RETRO"

    if not cat: return False, "NO_CAT"
    
    limits = {"PSP": 250, "VITA": 650, "3DS": 500, "2DS": 350, "DS_OLD": 150, "RETRO": 300, "TCG_ETB": 300, "TCG_BB": 700, "TCG_BUNDLE": 150, "FIRST_PARTNER": 120}
    if 49 < price <= limits.get(cat, 999): return True, cat
    return False, "PRICE"

def extract_vinted_items(html):
    if not html: return []
    soup = BeautifulSoup(html, "html.parser")
    found = []
    
    # ULTIMATE PARSER: Szukamy bezpośrednio linków do przedmiotów, ignorując nazwy klas
    for a_tag in soup.find_all("a", href=True):
        href = a_tag['href']
        if "/items/" not in href: continue
        if "member" in href or "catalog" in href: continue # pomijamy linki do użytkowników
        
        # Bierzemy kontener rodzica, w którym zazwyczaj jest też cena
        parent_card = a_tag.find_parent("div", class_=re.compile(r"item|box|card|container", re.I))
        if not parent_card: parent_card = a_tag.parent.parent.parent # awaryjne wyjście
        
        if not parent_card: continue
        
        txt = parent_card.get_text(separator=" ").lower()
        if any(x in txt for x in ["dni temu", "vakar", "days ago"]): continue
        
        p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
        if p_match:
            price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
            full_url = href if "vinted.pl" in href else f"https://www.vinted.pl{href}"
            
            # Próba wyciągnięcia ładnego tytułu z atrybutu title lub ze zdjęcia
            title = a_tag.get("title")
            if not title:
                img = a_tag.find("img")
                if img and img.get("alt"): title = img.get("alt")
            if not title: title = "Vinted Item"
            
            # Zabezpieczenie przed dublami na jednej stronie
            if not any(f['url'] == full_url for f in found):
                found.append({"title": title, "url": full_url, "price": price})
                
    return found[:15]

def scrape_vinted_with_retries(query):
    global OLO_INDEX
    q_encoded = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_encoded}&order=newest_first&currency=PLN"
    last_html_title = ""

    # 1. ScrapingDog
    try:
        r = requests.get("https://api.scrapingdog.com/scrape", params={"api_key": SCRAPINGDOG_KEY, "url": target_url, "dynamic": "true"}, timeout=30)
        last_html_title = get_html_title(r.text) if r.text else "Brak odpowiedzi"
        items = extract_vinted_items(r.text) if r.status_code == 200 and not is_blocked_html(r.text) else []
        if items: 
            log_debug(f"✅ Vinted (Dog) trafił: {len(items)} ofert dla {query}")
            for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
            return
    except: pass

    # 2. ScrapingAnt
    try:
        r = requests.get("https://api.scrapingant.com/v2/extended", params={"url": target_url, "x-api-key": SCRAPINGANT_KEY, "proxy_country": "PL"}, timeout=30)
        if not items and r.text: last_html_title = get_html_title(r.text)
        items = extract_vinted_items(r.text) if r.status_code == 200 and not is_blocked_html(r.text) else []
        if items: 
            log_debug(f"✅ Vinted (Ant) trafił: {len(items)} ofert dla {query}")
            for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
            return
    except: pass

    # 3. OloStep
    start_olo = OLO_INDEX
    for i in range(start_olo, len(OLOSTEP_KEYS)):
        try:
            h = {"Authorization": f"Bearer {OLOSTEP_KEYS[i]}", "Content-Type": "application/json"}
            r = requests.post("https://api.olostep.com/v1/scrapes", json={"url_to_scrape": target_url}, headers=h, timeout=40)
            if r.status_code == 200:
                html = r.json().get('default_snapshot', {}).get('content', '')
                if html: last_html_title = get_html_title(html)
                items = extract_vinted_items(html) if not is_blocked_html(html) else []
                if items:
                    log_debug(f"✅ Vinted (OloStep) trafił: {len(items)} ofert dla {query}")
                    for item in items: process_item(item['title'], item['url'], item['price'], "VINTED")
                    return
            OLO_INDEX += 1
        except: OLO_INDEX += 1
    
    log_debug(f"❌ Vinted PUSTE dla: {query} | Zwrócony tytuł strony: '{last_html_title[:40]}'")

def scrape_olx(query):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        q_encoded = urllib.parse.quote_plus(query)
        url = f"https://www.olx.pl/api/v1/offers/?query={q_encoded}&sort_by=created_at:desc&limit=20"
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
    log_debug("🚀 SNIPER v19.80 | ULTIMATE PARSER - DATADOME BYPASSED")
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
            time.sleep(random.randint(15, 25))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)})."); IS_FIRST_RUN = False
        
        time.sleep(750)
