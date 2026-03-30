import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re, time, random, hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()
IS_FIRST_RUN = True  # Mechanizm blokady starych ofert

RAW_PROXY = "isp2.hydraproxy.com:9989:szykvbdhxg404595:CmaoDg885jEO6Dxb_country-Poland"
hp = RAW_PROXY.split(':')
MY_PROXY = f"http://{hp[2]}:{hp[3]}@{hp[0]}:{hp[1]}"

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_console_smart(title, price):
    t_f = title.lower()
    
    priority_keywords = ["konsola", "v2", "oled", "lite", "classic", "fat", "slim", "pch-", "3004", "2004", "1004", "dual ips"]
    trash_keywords = ["gra", "gry", "game", "joc", "zaidimai", "etui", "case", "pudełko", "instrukcja", "kabel", "adapter", "części", "parts", "amiibo"]

    has_priority = any(x in t_f for x in priority_keywords)
    has_trash = any(x in t_f for x in trash_keywords)

    if has_trash and not has_priority: return False, None
    if price < 80: return False, None

    # PRECYZYJNA KATEGORYZACJA
    cat = None
    if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif "new 3ds" in t_f: cat = "N3DS"
    elif "3ds" in t_f: cat = "3DS"
    elif "2ds" in t_f: cat = "2DS"
    elif "dsi" in t_f: cat = "DSI"
    elif "ds lite" in t_f or "ds fat" in t_f: cat = "DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "advance"]): cat = "GB"
    
    if not cat: return False, None
    
    limits = {"GB": 450, "PSP": 350, "VITA": 650, "3DS": 650, "N3DS": 800, "2DS": 600, "DSI": 300, "DS": 250}
    return (price <= limits.get(cat, 999)), cat

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
                    if process_item(link.get("title", "") or "Konsola", link['href'], price, "VINTED"): found += 1
            return found
        return -1
    except: return -1

def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:40]}_{int(price)}".encode()).hexdigest()
    
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, cat = is_console_smart(title, price)
    if valid:
        # Jeśli to pierwsze uruchomienie, tylko dodajemy do bazy "starych", nie wysyłamy wiadomości
        if IS_FIRST_RUN:
            SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
            return False
            
        msg = f"💎 *OFERTA {src}* [{cat}]\n📦 {title[:75]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        log_debug(f"🔥 NOWA: {title[:20]}... ({price:.2f} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
        return True
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.42 | TYLKO NOWE OFERTY | SMART CAT")
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "nintendo 2ds", "nintendo dsi", "ds lite"]
    
    while True:
        v_total = o_total = 0
        with get_session() as s:
            for q in QUERIES:
                o_total += scrape_olx(s, q)
                time.sleep(random.randint(5, 10))
                res = scrape_vinted(s, q)
                if res != -1: v_total += res
                time.sleep(random.randint(15, 25))
        
        if IS_FIRST_RUN:
            log_debug(f"✅ Baza zainicjowana ({len(SENT_HASHES)} ofert). Czekam na nowe...")
            IS_FIRST_RUN = False # Od teraz każda nowa oferta leci na Telegram
        else:
            log_debug(f"Pętla OK. Znaleziono nowych: V({v_total}) O({o_total})")
            
        time.sleep(random.randint(60, 120))
