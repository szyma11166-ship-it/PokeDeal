import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re, time, random, os, hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()

# TWOJA KONFIGURACJA HYDRAPROXY
RAW_PROXY = "isp2.hydraproxy.com:9989:szykvbdhxg404595:CmaoDg885jEO6Dxb_country-Poland"
hp = RAW_PROXY.split(':')
MY_PROXY = f"http://{hp[2]}:{hp[3]}@{hp[0]}:{hp[1]}"

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_console_smart(title, price):
    t_f = title.lower()
    
    # 1. Słowa kluczowe sprzętu (Sygnał, że to może być konsola)
    priority_keywords = ["konsola", "v2", "oled", "lite", "classic", "fat", "slim", "pch-", "3004", "2004", "1004", "new", "nintendo"]
    
    # 2. Słowa kluczowe śmieci (Gry i akcesoria)
    trash_keywords = [
        "gra", "gry", "game", "games", "zaidimai", "joc", "pudełko", "box", 
        "instrukcja", "manual", "etui", "case", "pokrowiec", "części", "parts",
        "ładowarka", "charger", "kabel", "zasilacz", "tupac", "disks", "umd"
    ]

    has_priority = any(x in t_f for x in priority_keywords)
    has_trash = any(x in t_f for x in trash_keywords)

    # LOGIKA: Jeśli są "gry" w tytule, ale NIE MA słowa "konsola" -> ODRZUCAMY
    if has_trash and not has_priority:
        return False, None

    # 3. FILTR CENOWY (Twarde dno 80 zł - zabezpieczenie przed drobnicą)
    if price < 80:
        return False, None

    # 4. KATEGORYZACJA I LIMITY GÓRNE
    cat = None
    if any(x in t_f for x in ["ps vita", "psvita"]): cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "advance"]): cat = "GB"
    
    if not cat: return False, None
    
    # Twoje oryginalne limity cenowe
    limits = {"GB": 450, "PSP": 350, "VITA": 650, "3DS": 650}
    return (price <= limits.get(cat, 999)), cat

def get_session():
    s = cffi_requests.Session(impersonate="chrome124", proxies={"http": MY_PROXY, "https": MY_PROXY})
    s.headers.update({
        "Accept-Language": "pl-PL,pl;q=0.9",
        "Referer": "https://www.google.pl/",
    })
    return s

def scrape_olx(session, query):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        r = session.get(url, timeout=12)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_val:
                    if process_item(o['title'], o['url'], float(p_val), "OLX"):
                        found += 1
    except: pass
    return found

def scrape_vinted(session, query):
    found = 0
    try:
        # Vinted "rozgrzewka" (ciastka)
        session.get("https://www.vinted.pl/", timeout=10)
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=15)
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            
            for card in cards:
                txt = card.get_text(separator=" ").lower()
                # Omijaj stare oferty (sprzed dni/tygodni)
                if any(x in txt for x in ["dni", "vakar", "days"]): continue
                
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    title = link.get("title", "") or "Konsola / Sprzęt"
                    if process_item(title, link['href'], price, "VINTED"):
                        found += 1
            return found
        return -1
    except: return -1

def process_item(title, url, price, src):
    clean_url = url.split("?")[0].rstrip("/")
    # Hashujemy tytuł i cenę, żeby uniknąć duplikatów
    h = hashlib.md5(f"{title[:40]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, cat = is_console_smart(title, price)
    if valid:
        msg = f"💎 *OFERTA {src}* [{cat}]\n📦 {title[:75]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        log_debug(f"🔥 WYSŁANO: {title[:25]}... ({price:.2f} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
        return True
    return False

if __name__ == "__main__":
    log_debug("🚀 SNIPER v17.41 | SMART FILTER | HYDRA ACTIVE")
    QUERIES = ["psp konsola", "ps vita", "nintendo 3ds", "gameboy", "nintendo 2ds"]
    
    while True:
        v_total = o_total = 0
        with get_session() as s:
            random.shuffle(QUERIES)
            for q in QUERIES:
                o_total += scrape_olx(s, q)
                time.sleep(random.randint(8, 12))
                
                res = scrape_vinted(s, q)
                if res != -1: v_total += res
                time.sleep(random.randint(15, 25))
        
        log_debug(f"Koniec pętli. Vinted({v_total}) OLX({o_total}). Baza: {len(SENT_HASHES)}")
        # Przerwa, aby nie dostać bana na IP
        time.sleep(random.randint(80, 150))
