import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re

print("START DEAL BOT")

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

CHECK_INTERVAL = 20


def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.get(url, params={
            "chat_id": CHAT_ID,
            "text": msg
        })
    except Exception as e:
        print("ERROR:", e)


def extract_price(text):
    match = re.search(r'(\d+[.,]?\d*)\s?zł', text.lower())
    if match:
        return float(match.group(1).replace(",", "."))
    return None


# 🔥 ROZPOZNAWANIE PRODUKTU + LIMIT
def get_price_limit(name):
    n = name.lower()

    if "booster box" in n or "display" in n:
        return 200, "Booster Box"

    elif "etb" in n:
        return 300, "ETB"

    elif "tin" in n:
        return 100, "Tin"

    elif "booster" in n:
        return 25, "Booster"

    return None, None


def get_rebel():
    url = "https://www.rebel.pl/pokemon"
    headers = {"User-Agent": "Mozilla/5.0"}

    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    products = []

    for item in soup.find_all("a"):
        try:
            name = item.text.strip()
            link = item.get("href")

            if not link or not name:
                continue

            if "/produkt/" not in link:
                continue

            price = extract_price(item.text)

            if not price:
                continue

            limit, typ = get_price_limit(name)

            if not limit:
                continue

            if price > limit:
                continue

            full_link = "https://www.rebel.pl" + link

            products.append({
                "name": name,
                "price": price,
                "link": full_link,
                "shop": "Rebel",
                "type": typ
            })

        except:
            continue

    return products


def load_seen():
    try:
        with open("seen_deals.json", "r") as f:
            return json.load(f)
    except:
        return []


def save_seen(data):
    with open("seen_deals.json", "w") as f:
        json.dump(data, f)


def main():
    seen = load_seen()

    while True:
        print("SZUKAM OKAZJI...")

        products = get_rebel()

        for p in products:
            if p["link"] not in seen:

                msg = f"💰 OKAZJA ({p['type']})!\n\n{p['name']}\nCena: {p['price']} zł\nSklep: {p['shop']}\n{p['link']}"
                send_telegram(msg)

                seen.append(p["link"])

        save_seen(seen)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
