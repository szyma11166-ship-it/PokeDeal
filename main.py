import requests
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import re, time, random, os, hashlib

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
SENT_HASHES = set()

# TWOJA LISTA HYDRAPROXY (Przerobiona na format Pythona)
RAW_PROXIES = [
    "isp2.hydraproxy.com:9989:szykvbdhxg404595:CmaoDg885jEO6Dxb_country-Poland"
] * 50 # Hydra używa jednego endpointu, który sam rotuje IP przy każdym połączeniu

PAID_PROXIES = [f"http://{p.split(':')[2]}:{p.split(':')[3]}@{p.split(':')[0]}:{p.split(':')[1]}" for p in RAW_PROXIES]

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

def is_valid_strict(title, price):
    t_f = title.lower()
    
    # CZYSZCZENIE SPAMU (To wycina śmieci z OLX)
    bad = [
        "ładowarka", "kabel", "etui", "case", "serwis", "naprawa", "części", "bateria", 
        "styki", "gumki", "obudowa", "pusta", "box only", "sama okładka", "instrukcja", 
        "manual", "ulotka", "pudełko", "zamiennik", "dummy", "atrapa", "pudełko po", "okładka do"
    ]
    
    if any(x in t_f for x in bad): return False, None
    if price < 30: return False, None # Podniesiony próg, żeby nie spamować drobnicą

    cat = None
    if "ps vita" in t_f or "psvita" in t_f: cat = "VITA"
    elif "psp" in t_f: cat = "PSP"
    elif any(x in t_f for x in ["3ds", "2ds", "n3ds"]): cat = "3DS"
    elif any(x in t_f for x in ["gameboy", "gba", "gbc", "advance"]): cat = "GB"
    elif any(x in t_f for x in ["booster", "bundle", "etb", "display"]): cat = "POKE"
    
    if not cat: return False, None
    
    limits = {"POKE": 400, "GB": 450, "PSP": 350, "VITA": 650, "3DS": 650}
    return (price <= limits.get(cat, 999)), cat

def get_random_session():
    px = random.choice(PAID_PROXIES)
    return cffi_requests.Session(impersonate="chrome124", proxies={"http": px, "https": px})

def scrape_olx(session, query):
    found = 0
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
        r = session.get(url, timeout=12)
        if r.status_code == 200:
            for o in r.json().get('data', []):
                p_data = next((x['value']['value'] for x in o['params'] if x['key']=='price'), None)
                if p_data:
                    if process_item(o['title'], o['url'], float(p_data), "OLX"): found += 1
    except: pass
    return found

def scrape_vinted(session, query):
    found = 0
    try:
        url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            if "datadome" in r.text.lower() or "cloudflare" in r.text.lower(): return -1
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            for card in cards:
                txt = card.get_text(separator=" ").lower()
                if any(x in txt for x in ["dni", "vakar", "days"]): continue
                link = card.find("a", href=True)
                p_match = re.search(r"(\d+[\d\s,.]*)\s?zł", txt)
                if link and p_match:
                    price = float(p_match.group(1).replace(",", ".").replace(" ", ""))
                    if process_item(link.get("title", ""), link['href'], price, "VINTED"): found += 1
            return found
        return -1
    except: return -1

def process_item(title, url, price, src):
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:40]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False
    
    valid, cat = is_valid_strict(title, price)
    if valid:
        msg = f"🎯 *HIT {src}*\n📦 *{title[:75]}*\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        log_debug(f"🔥 WYSŁANO: {title[:25]}... ({price:.2f} zł)")
        SENT_HASHES.add(h); SENT_HASHES.add(clean_url)
        return True
    return False

if __name__ == "__main__":
    log_debug("🚀 HYDRA ENGINE v17.36 | Filtry: OSTRE")
    QUERIES = ["psp konsola", "ps vita", "3ds", "gameboy", "pokemon bundle"]
    
    while True:
        v_total = o_total = 0
        with get_random_session() as s:
            random.shuffle(QUERIES)
            for q in QUERIES:
                o_total += scrape_olx(s, q)
                time.sleep(random.randint(7, 12))
                
                res = scrape_vinted(s, q)
                if res == -1:
                    log_debug("⚠️ Hydra/Vinted Block. Rotacja sesji...")
                    break 
                else: v_total += res
                time.sleep(random.randint(15, 25))
        
        log_debug(f"Pętla OK: V({v_total}) O({o_total}). Baza: {len(SENT_HASHES)}")
        time.sleep(random.randint(45, 90))
