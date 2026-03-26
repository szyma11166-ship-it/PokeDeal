import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import json
from datetime import datetime

# --- CONFIG ---
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"
SENT_FILE = "sent_links.txt"

# Wyczyszczenie listy wysłanych przy starcie testu (opcjonalnie)
if os.path.exists(SENT_FILE): os.remove(SENT_FILE)

def send_telegram(title, price, link, source):
    msg = f"🧪 TEST POŁĄCZENIA: {source}\n📦 {title[:50]}\n💰 {price} zł\n🔗 {link}"
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                         data={"chat_id": CHAT_ID, "text": msg})
        if r.status_code == 200: print(f"  >>> [TELEGRAM] Wiadomość wysłana pomyślnie!")
        else: print(f"  >>> [TELEGRAM] BŁĄD: {r.text}")
    except Exception as e: print(f"  >>> [TELEGRAM] CRITICAL ERROR: {e}")

def scrape(source, query):
    # Rotacja User-Agent dla uniknięcia blokad
    headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110,123)}.0.0.0 Safari/537.36"}
    print(f"🔎 Szukam '{query}' na {source}...")
    
    try:
        if source == "OLX":
            url = f"https://www.olx.pl/api/v1/offers/?query={query}&sort_by=created_at:desc"
            r = requests.get(url, headers=headers, timeout=15)
            print(f"  [STATUS] OLX Response: {r.status_code}")
            items = r.json().get('data', [])
            for o in items[:5]: # Bierzemy tylko 5 pierwszych do testu
                t = o.get('title')
                p = o.get('price', {}).get('value', {}).get('amount')
                l = o.get('url')
                print(f"    - Znaleziono: {t[:40]} | {p}zł")
                if t and p and l: send_telegram(t, p, l, "OLX_TEST")
        
        elif source == "VINTED":
            url = f"https://www.vinted.pl/catalog?search_text={query}&order=newest_first"
            # Vinted wymaga ciasteczek, uderzamy najpierw w główną
            s = requests.Session()
            s.get("https://www.vinted.pl", headers=headers, timeout=10)
            r = s.get(url, headers=headers, timeout=15)
            print(f"  [STATUS] VINTED Response: {r.status_code}")
            
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", {"data-testid": re.compile(r"grid-item")})
            print(f"    - Znaleziono {len(cards)} kontenerów na Vinted")
            
            for card in cards[:5]:
                link_tag = card.find("a", href=True)
                if not link_tag: continue
                t = link_tag.get("title") or "Brak tytułu"
                p_raw = re.findall(r"(\d+[,.]\d+) zł", card.get_text())
                p = p_raw[0].replace(",", ".") if p_raw else "0"
                l = link_tag['href'] if "http" in link_tag['href'] else "https://www.vinted.pl" + link_tag['href']
                print(f"    - Znaleziono: {t[:40]} | {p}zł")
                send_telegram(t, p, l, "VINTED_TEST")

    except Exception as e:
        print(f"  [!] BŁĄD SCRAPINGU {source}: {e}")

if __name__ == "__main__":
    print("🛠️ URUCHAMIAM TRYB DIAGNOSTYCZNY (BEZ FILTRÓW)")
    # Używamy prostego zapytania, które na 100% coś zwróci
    test_queries = ["konsola", "pokemon"]
    
    for q in test_queries:
        scrape("OLX", q)
        time.sleep(5)
        scrape("VINTED", q)
        time.sleep(5)
    
    print("\n✅ Test zakończony. Sprawdź telefon i logi powyżej.")
