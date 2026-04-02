import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'):
    time.tzset()

# --- TWOJE KLUCZE (29 SZTUK) ---
OLOSTEP_KEYS = [
    "olostep_koEUWUkQ7ue1e56xsJEmXBIwhFgNUWjvOT7U", "olostep_Jtz86lFTzVTyVnYr7Ci2LaMC0wnelqGB2kjJ",
    "olostep_HNb7ahynRXVg053o9YYSCuoIZIe5PCI3PYQp", "olostep_ilStdJ4wxfJm80DhrKYUo5x9oGh5bQ1ex3vJ",
    "olostep_F9a3YpVhC4rD1aoQXOxdW6NIRqVJpoF9ykY1", "olostep_h1B6t6i3o1LomV7wgkJRuTrKORCyfuwZ7Wtv",
    "olostep_E1ULbEpkGVj3ebtbNl7GERlMh4yOWfsD9c1X", "olostep_uLmphHL0rHj1iikKHexEnHxItbHyTaUWtiLi",
    "olostep_n8Y2d5FCsjrdtaqy5cGmT5nFiSMF8MeEE6O8", "olostep_r28K78wzg2GVLDVz4V6F1Qa0UdT17pN3Ratd",
    "olostep_tP1WrjpuagOsYCdctCOQQx6cwTzkbVIJfUXw", "olostep_nFP0YwFWIdTUazbEIsivJRR5JepmdORVm9nv",
    "olostep_yVHx982cBYQlfXZUDcjAezgbffQ1Ot2v4o42", "olostep_lv02DqXQIQQ6WF1PMLdQgTePaKeVTmjbaLy8",
    "olostep_4HAwlpNG0bJu9a9YFjM3IiAjOFarGaYeUZEX", "olostep_cJuSrUHAdGe97mdiuNilJs6DQFN934tByRAb",
    "olostep_Ismu4Th5YKA4NV5wTYUqNQL2Eod2pOWfdCEK", "olostep_yZ8GRKuSoA3deLXYxIMdOJZezFYOxVWkSKjH",
    "olostep_BwAhFJuK9ZzyOqtQEDuX0QwxWmAc6ZSj65HJ", "olostep_ElxXEs8WCSrtaPU3RE5E3azbuMDEe6Vx03Rv",
    "olostep_J3hXd9tU8hcP8qTHqqmFhzzrsaoG0V4neNy7", "olostep_Aok0E95IbyvijgPCeS4qLEFv0FJ58x3PxsP0",
    "olostep_Ai2L7IEzCRI8WY1Ofa10aHNj8PpT1p0wV18W", "olostep_uZYru9zWGHl60W4CO7aj5T2Dud48id3MmhPr",
    "olostep_gu9B52cJ30OV20ShHwLiMbfHUcFB1F3iVXBd", "olostep_MSTMsMkYk0AdyC8JoGD7hk2wrhsC3EzUmWt1",
    "olostep_KuvN0l1m3DqzjPvIVhsvp4hSBZBZ8rhLOnt6", "olostep_lxVgFBkSFN8LOeHLpBBBBRmwZm5YsNYC6b7P",
    "olostep_TEZ2ySYKVa93lLRbH45NDbLeyIck1ghRgEhc"
]

SCRAPINGDOG_KEY = "69cc2236cca5a0331e084197"
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True
OLO_INDEX = 0

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

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
    soup = BeautifulSoup(html, "html.parser")
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
    global OLO_INDEX
    q_enc = urllib.parse.quote_plus(query)
    target_url = f"https://www.vinted.pl/catalog?search_text={q_enc}&order=newest_first"
    success = False

    for attempt in range(2):
        idx = OLO_INDEX % len(OLOSTEP_KEYS)
        key = OLOSTEP_KEYS[idx]
        # W drugiej próbie wymuszamy JS, żeby sprawdzić czy to coś zmieni
        use_js = (attempt == 1)
        
        try:
            r = requests.post(
                "https://api.olostep.com/v1/scrapes", 
                json={"url_to_scrape": target_url, "render_js": use_js}, 
                headers={"Authorization": f"Bearer {key}"}, 
                timeout=25
            )
            
            if r.status_code == 200:
                html = r.json().get('default_snapshot', {}).get('content', '')
                if "datadome" in html.lower():
                    log_debug(f"⚠️ [Olo-{idx}] Datadome detect.")
                else:
                    items = extract_vinted_items(html)
                    if items:
                        log_debug(f"✅ [Olo-{idx}] OK ({len(items)}) | JS: {use_js}")
                        for i in items: process_item(i['title'], i['url'], i['price'], "VINTED")
                        success = True; break
                    else:
                        log_debug(f"ℹ️ [Olo-{idx}] Brak ofert | JS: {use_js}")
                        success = True; break
            elif r.status_code == 402:
                # DIAGNOSTYKA BŁĘDU 402
                error_msg = r.json().get('message', 'No message')
                log_debug(f"🛑 [DIAGNOZA-402] Klucz {idx} ({key[-4:]}): {error_msg}")
            else:
                log_debug(f"❌ [Olo-{idx}] HTTP {r.status_code}")
                
            OLO_INDEX += 1
        except Exception as e:
            log_debug(f"❌ [Olo-{idx}] Błąd: {str(e)}")
            OLO_INDEX += 1

    if not success:
        try:
            r = requests.get("https://api.scrapingdog.com/scrape", params={"api_key": SCRAPINGDOG_KEY, "url": target_url, "dynamic": "false"}, timeout=20)
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
    if h in SENT_HASHES or clean_url in SENT_HASHES: return
    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
            log_debug(f"🎯 WYSŁANO: {title[:15]}")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)

if __name__ == "__main__":
    log_debug("🚀 SNIPER v33.0 | THE DETECTIVE")
    QUERIES = ["nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds", "nintendo 2ds", "gameboy advance", "gameboy color", "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"]
    while True:
        current_hour = time.localtime().tm_hour
        if 1 <= current_hour < 6:
            log_debug("🌙 Nocna pauza..."); time.sleep(1800); continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q); time.sleep(5)
            scrape_vinted(q); time.sleep(15)
            
        if IS_FIRST_RUN: log_debug("✅ Baza gotowa."); IS_FIRST_RUN = False
        log_debug(f"💤 Przerwa 400s. Klucz: {OLO_INDEX % len(OLOSTEP_KEYS)}")
        time.sleep(400)
