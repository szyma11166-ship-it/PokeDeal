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
    
    # 1. ABSOLUTNA CZARNA LISTA (Chińszczyzna i śmieci)
    absolute_trash = ["r36s", "miyoo", "anbernic", "powkiddy", "sf2000", "emulator", "podstawk", "stojak", "stand", "uchwyt"]
    if any(x in t_f for x in absolute_trash):
        return False, "ABSOLUTE_TRASH"

    # 2. FILTR JĘZYKOWY (Działa na wszystko: Karty i Konsole)
    # Wywalamy śmieciowe języki na starcie
    bad_languages = ["jap", "japonskie", "japanese", "kor", "korean", "koreanskie", "fr", "it", "de", "niemieckie", "wloskie"]
    if any(x in t_f for x in bad_languages):
        return False, "BAD_LANGUAGE"

    # 3. DEFINICJA KATEGORII
    cat = None
    
    # --- POKEMON TCG LOGIC ---
    if "pokemon" in t_f:
        if any(x in t_f for x in ["etb", "elite trainer"]): cat = "TCG_ETB"
        elif "booster box" in t_f or "display" in t_f: cat = "TCG_DISPLAY" # Tylko całe boxy
        elif "booster" in t_f: cat = "TCG_PACK" # Pojedyncze paczki
        elif "bundle" in t_f: cat = "TCG_BUNDLE"
        elif "tin" in t_f: cat = "TCG_TIN"
        elif "partner illustration" in t_f: cat = "TCG_PAR"
    
    # --- CONSOLE LOGIC ---
    if not cat:
        if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
        elif "psp" in t_f: cat = "PSP"
        elif "new 3ds" in t_f: cat = "N3DS"
        elif "3ds" in t_f: cat = "3DS"
        elif "2ds" in t_f: cat = "2DS"
        elif "dsi" in t_f: cat = "DSI"
        elif any(x in t_f for x in ["ds lite", "ds fat"]): cat = "DS"
        elif any(x in t_f for x in ["gameboy", "gba", "gbc", "advance"]): cat = "GB"

    if not cat: return False, "NO_CATEGORY"

    # 4. FILTRY MIĘKKIE (Tylko dla konsol)
    if "TCG_" not in cat:
        priority_keywords = ["konsola", "v2", "oled", "lite", "classic", "fat", "slim", "pch-", "3004", "2004", "1004"]
        trash_keywords = ["gra", "gry", "game", "joc", "zaidimai", "spiel", "jeu", "mario", "zelda", "fifa", "gta"]
        has_priority = any(x in t_f for x in priority_keywords)
        has_trash = any(x in t_f for x in trash_keywords)
        if has_trash and not has_priority: return False, "CONSOLE_GAME_SKIP"

    # 5. NOWE LIMITY CENOWE (Poprawione TCG_DISPLAY i TCG_PACK)
    limits = {
        "GB": 300, "PSP": 250, "VITA": 650, "3DS": 450, "N3DS": 650, "2DS": 400, "DSI": 200, "DS": 150,
        "TCG_ETB": 250, 
        "TCG_DISPLAY": 600, # Cały box
        "TCG_PACK": 40,    # Pojedynczy booster
        "TCG_BUNDLE": 150, 
        "TCG_TIN": 120, 
        "TCG_PAR": 150
    }
    
    # Dół zostawiamy bez zmian
    if price < 80 and cat != "TCG_PACK": # Obniżka progu tylko dla paczek kart
        return False, "TOO_CHEAP"
        
    if price > limits.get(cat, 999): 
        return False, "OVER_PRICED"

    return True, cat

def get_session():
    s = cffi_requests.Session(impersonate="chrome124", proxies={"http": MY_PROXY, "https": MY_PROXY})
    s.headers.update({"Accept-Language": "pl-PL,pl;q=0.9", "Referer": "https://www.google.pl/"})
    return s

def scrape_olx(session, query):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        r = session.get(url, timeout=12)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val and process_item(o['title'], o['url'], float(p_val), "OLX"): found += 1
    except: pass
    return found

def scrape_vinted(session, query):
    found = 0
    try:
        session.get("https://www.vinted.pl/", timeout=10)
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            for card in cards:
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "vakar", "days"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    if process_item(link.get("title", "") or "Przedmiot", link['href'], price, "VINTED"): found += 1
            return found
        return -1
    except: return -1

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:40]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, result = is_interesting_item(title, price)
    
    if valid:
        if IS_FIRST_RUN:
            SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
            return False
            
        msg = f"🔥 *OKAZJA {src}* [{result}]\n📦 {title[:75]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        log_debug(f"🎯 WYSŁANO: {title[:20]}... ({price:.2f} zł) [{result}]")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
        return True
    else:
        if price >= 100 and result != "CONSOLE_GAME_SKIP":
            log_debug(f"🛑 SKIP ({result}): {title[:30]}... ({price:.2f} zł)")
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.44 | CONSOLES & TCG | HYDRA")
    # Dodano zapytania o karty
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "pokemon etb", "pokemon booster box", "pokemon bundle"]
    
    while True:
        v_total = o_total = 0
        with get_session() as s:
            random.shuffle(QUERIES)
            for q in QUERIES:
                o_total += scrape_olx(s, q)
                time.sleep(random.randint(5, 10))
                res = scrape_vinted(s, q)
                if res != -1: v_total += res
                time.sleep(random.randint(15, 25))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza gotowa ({len(SENT_HASHES)} ofert). Szukam okazji...")
            IS_FIRST_RUN = False
        else:
            log_debug(f"Pętla OK. Nowe: V({v_total}) O({o_total})")
        time.sleep(random.randint(60, 120))
