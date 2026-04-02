import requests
from bs4 import BeautifulSoup
import re, time, random, hashlib, os, json
import urllib.parse

os.environ['TZ'] = 'Europe/Warsaw'
if hasattr(time, 'tzset'): time.tzset()

# --- KONFIGURACJA ---
VINTED_SESSION_COOKIE = "RCszcWZ4M1RHNDRTSG1aTEQ3a1hGVXVzL2xsNWptMWN3bE5oT0wrS1FCZ3lNazM0Vi9qWWtpY1JwNGhxWVhlZE1wMExxVlhvNWR1QU1IRFdJUUNUSEU3Vkt4am5GUjFQSFNUa2NmYnRhOGlOVXhjeW1mWEYrZk9tVmhLUkhpTXk4ZHRkUzlXUUlWdGw3bVRkM3llemNGL000cWNOcU52ZUhUVS9VNGozVkQzYVV0azEyL09UVDRxdVJtV0FZTTFReTNUS0VsRS8vRTZYRGlWMlR1dmFvQ1ZmcytKS2lGZ0I3aUxBb1BtR2VqWVRBNUdQd0FWemhzTEFwbWJhQ1hDUHcxRnNzbnVBY0NxcmtNWnpsaTJNMlJHelp4SGhwTTlMSWVRcFg0V1NYazMwVzg5eUE3ZC9yeHFhbmdLMnhDRFktLU13N1N0NzlMVmZSWlhDMTZDUTUvYkE9PQ%3D%3D--a8a0b822e535a4140bb5829dd4cc80d873a08b35"

BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"

SENT_HASHES = set()
IS_FIRST_RUN = True

VINTED_SESSION = requests.Session()
VINTED_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://www.vinted.pl/",
    "X-Requested-With": "XMLHttpRequest",
})
VINTED_SESSION.cookies.set("_vinted_fr_session", VINTED_SESSION_COOKIE, domain=".vinted.pl")

ALLEGRO_SESSION = requests.Session()
ALLEGRO_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pl-PL,pl;q=0.9",
})

OLX_SESSION = requests.Session()
OLX_SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

def log_debug(msg):
    print(f"{time.strftime('%H:%M:%S')} | {msg}", flush=True)

# --- SCRAPING VINTED (wewnętrzne API) ---
def scrape_vinted(query):
    q_enc = urllib.parse.quote_plus(query)
    url = f"https://www.vinted.pl/api/v2/catalog/items?search_text={q_enc}&order=newest_first&per_page=30"
    try:
        r = VINTED_SESSION.get(url, timeout=20)
        if r.status_code == 401:
            log_debug("🔄 Sesja Vinted wygasła — zaktualizuj VINTED_SESSION_COOKIE")
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": "⚠️ *SNIPER* — Sesja Vinted wygasła!\nPodmień token w kodzie (_vinted\\_fr\\_session_ z ciasteczek przeglądarki).", "parse_mode": "Markdown"}
            )
            return
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", [])
            new_count = 0
            for item in items:
                title = item.get("title", "")
                price = float(item.get("price", 0))
                item_url = item.get("url", "")
                if not item_url.startswith("http"):
                    item_url = f"https://www.vinted.pl{item_url}"
                if process_item(title, item_url, price, "VINTED"):
                    new_count += 1
            log_debug(f"✅ Vinted [{query}]: {len(items)} ofert, {new_count} nowych")
        else:
            log_debug(f"⚠️ Vinted status: {r.status_code}")
    except Exception as e:
        log_debug(f"💥 Błąd Vinted: {e}")

# --- SCRAPING OLX ---
def scrape_olx(query):
    try:
        url = f"https://www.olx.pl/api/v1/offers/?query={urllib.parse.quote_plus(query)}&sort_by=created_at:desc&limit=20"
        r = OLX_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            new_count = 0
            for o in r.json().get('data', []):
                p_val = next((x['value']['value'] for x in o['params'] if x['key'] == 'price'), None)
                if p_val:
                    if process_item(o['title'], o['url'], float(p_val), "OLX"):
                        new_count += 1
            log_debug(f"✅ OLX [{query}]: nowych {new_count}")
    except Exception as e:
        log_debug(f"💥 Błąd OLX: {e}")

# --- SCRAPING ALLEGRO LOKALNIE ---
def scrape_allegro_lokalnie(query):
    try:
        q_enc = urllib.parse.quote_plus(query)
        url = f"https://allegrolokalnie.pl/api/v1/items?phrase={q_enc}&sort=-created_at&limit=30"
        r = ALLEGRO_SESSION.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("items", data.get("data", []))
            new_count = 0
            for item in items:
                title = item.get("name") or item.get("title", "")
                price_raw = item.get("price") or item.get("selling_price", {})
                if isinstance(price_raw, dict):
                    price = float(price_raw.get("amount", 0))
                else:
                    price = float(price_raw or 0)
                slug = item.get("slug") or item.get("id", "")
                item_url = f"https://allegrolokalnie.pl/oferta/{slug}"
                if title and price:
                    if process_item(title, item_url, price, "ALLEGRO"):
                        new_count += 1
            log_debug(f"✅ Allegro Lokalnie [{query}]: nowych {new_count}")
        else:
            log_debug(f"⚠️ Allegro Lokalnie status: {r.status_code}")
    except Exception as e:
        log_debug(f"💥 Błąd Allegro Lokalnie: {e}")

# --- FILTR OKAZJI ---
def is_interesting_item(title, price):
    t_f = title.lower()
    trash = ["r36s", "miyoo", "anbernic", "powkiddy", "stojak", "case", "uchwyt", "części", "czesci",
             "karta", "etui", "pudełko", "pudelko", "box", "instrukcja", "ładowarka", "ladowarka",
             "adapter", "bajka", "film", "dvd", "książka", "komiks", "płyta", "plyta", "plakat"]
    if any(x in t_f for x in trash): return False, "TRASH"

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

    limits = {
        "PSP": 250, "VITA": 650, "3DS": 550, "2DS": 400,
        "DS_OLD": 150, "RETRO": 300, "TCG_ETB": 300,
        "TCG_BB": 700, "TCG_BUNDLE": 150, "FIRST_PARTNER": 150
    }
    if 45 < price <= limits.get(cat, 1000): return True, cat
    return False, "PRICE"

# --- WYSYŁKA TELEGRAM ---
def process_item(title, url, price, src):
    global IS_FIRST_RUN
    clean_url = url.split("?")[0].rstrip("/")
    h = hashlib.md5(f"{title[:30]}_{int(price)}".encode()).hexdigest()
    if h in SENT_HASHES or clean_url in SENT_HASHES: return False

    valid, res = is_interesting_item(title, price)
    if valid:
        if not IS_FIRST_RUN:
            msg = f"🔥 *OKAZJA {src}* [{res}]\n📦 {title[:70]}\n💰 `{price:.2f} zł`\n🔗 [LINK]({clean_url})"
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
            )
            log_debug(f"🎯 WYSŁANO: {title[:25]} ({price} zł)")
        SENT_HASHES.add(h)
        SENT_HASHES.add(clean_url)
        return True
    return False

# --- GŁÓWNA PĘTLA ---
if __name__ == "__main__":
    log_debug("🚀 SNIPER v39.1 | VINTED COOKIE + ALLEGRO LOKALNIE")

    QUERIES = [
        "nintendo ds konsola", "psp konsola", "ps vita", "nintendo 3ds",
        "nintendo 2ds", "gameboy advance", "gameboy color",
        "pokemon etb", "pokemon booster box", "pokemon bundle", "first partner pack"
    ]

    while True:
        if 1 <= time.localtime().tm_hour < 6:
            time.sleep(1800)
            continue

        random.shuffle(QUERIES)
        for q in QUERIES:
            scrape_olx(q)
            time.sleep(2)
            scrape_vinted(q)
            time.sleep(3)
            scrape_allegro_lokalnie(q)
            time.sleep(5)

        if IS_FIRST_RUN:
            IS_FIRST_RUN = False

        log_debug("💤 Koniec pętli. Przerwa 300s.")
        time.sleep(30)