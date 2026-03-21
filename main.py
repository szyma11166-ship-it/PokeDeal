import requests
from bs4 import BeautifulSoup
import time
import os
import re

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

sent = set()

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ---------- FILTR OKAZJI ----------
def is_deal(name, price):
    name = name.lower()

    if "etb" in name and price < 300:
        return True
    if "booster box" in name and price < 200:
        return True
    if "booster" in name and price < 25:
        return True
    if "tin" in name and price < 100:
        return True

    return False

# ---------- FILTR POKEMON ----------
def is_pokemon_product(text):
    text = text.lower()

    must_have = ["pokemon", "pokémon"]
    banned = ["lorcana", "mtg", "magic", "yugioh", "one piece", "digimon"]
    product_types = ["booster", "etb", "box", "tin"]

    if any(b in text for b in banned):
        return False

    if not any(m in text for m in must_have):
        return False

    if not any(p in text for p in product_types):
        return False

    return True

# ---------- ALLEGRO ----------
def check_allegro():
    print("Allegro...")
    url = "https://allegro.pl/listing?string=pokemon%20tcg"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("article")

    for item in items[:20]:
        try:
            name = item.select_one("h2").text.strip()
            price = item.select_one("span").text.strip()
            link = item.find("a")["href"]

            price_num = float(price.replace("zł", "").replace(",", ".").split()[0])

            if is_pokemon_product(name) and is_deal(name, price_num):
                if link not in sent:
                    sent.add(link)
                    send(f"🔥 ALLEGRO OKAZJA 🔥\n{name}\n{price}\n{link}")

        except:
            continue

# ---------- REBEL ----------
def check_rebel():
    print("Rebel...")
    url = "https://www.rebel.pl/pokemon"

    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    products = soup.select(".product")

    for p in products:
        try:
            name = p.select_one(".product-name").text.strip()
            price = p.select_one(".price").text.strip()
            link = "https://www.rebel.pl" + p.select_one("a")["href"]

            price_num = float(price.replace("zł", "").replace(",", "."))

            if is_pokemon_product(name) and is_deal(name, price_num):
                if link not in sent:
                    sent.add(link)
                    send(f"🟡 REBEL OKAZJA\n{name}\n{price}\n{link}")

        except:
            continue

# ---------- SKLEPY ----------
shops = [
    ("LootQuest", "https://lootquest.pl/", "BRAK"),
    ("Strefa Kart", "https://strefakart.pl/", "Rozaserdel"),
    ("Strefa TCG", "https://strefa-tcg.pl/", "taDZIK"),
    ("Kanto Drop", "https://kantodrop.pl/", "BRAK"),
    ("Świat Kart", "https://swiatkart.com.pl/", "BRAK"),
    ("Skład Gier", "https://skladgier.pl/", "BRAK"),
]

def check_shop(name, url, code):
    print(f"{name}...")
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")

        links = soup.find_all("a")

        for p in links[:150]:
            text = p.text.strip().lower()

            if not text:
                continue

            link = p.get("href")
            if not link:
                continue

            # ❌ blokuj śmieci
            if any(x in link for x in ["wp-admin", "login", "konto", "cart"]):
                continue

            # ❌ blokuj kategorie
            bad_paths = [
                "/collections",
                "/category",
                "/kategoria",
                "/tag",
                "/search",
                "/blog"
            ]

            if any(b in link for b in bad_paths):
                continue

            # ❌ musi być produkt
            if not any(x in link for x in ["product", "/p/", ".html"]):
                continue

            if not link.startswith("http"):
                link = url + link

            # 🎯 filtr pokemon
            if not is_pokemon_product(text):
                continue

            # 🔍 szukamy ceny
            parent = p.parent
            price = None

            if parent:
                price_text = parent.get_text()
                match = re.search(r"(\d+[,.]?\d*)\s*zł", price_text)

                if match:
                    price = float(match.group(1).replace(",", "."))

            # ❌ brak ceny
            if price is None:
                continue

            # 🎯 filtr okazji
            if not is_deal(text, price):
                continue

            if link in sent:
                continue

            sent.add(link)

            msg = f"""🟢 {name}
{text[:100]}

💰 {price} zł
🎟 Kod: {code}
{link}"""

            send(msg)

    except Exception as e:
        print(f"Błąd {name}:", e)

# ---------- START ----------
print("START DEAL BOT")

while True:
    try:
        check_allegro()
        check_rebel()

        for shop in shops:
            check_shop(shop[0], shop[1], shop[2])

    except Exception as e:
        print("Błąd:", e)

    time.sleep(30)