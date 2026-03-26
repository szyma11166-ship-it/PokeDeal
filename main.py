import requests
from bs4 import BeautifulSoup
import re
import time
import random
import os
import base64

# =========================
# CONFIG — wpisz swoje wartości
# =========================
BOT_TOKEN = "8641671766:AAEfRWe-lHc_8LLTA-rDecW3NjooDmENOl4"
CHAT_ID = "-1003743099672"
GEMINI_API_KEY = "AIzaSyCBRzBU3IE6-Gt3mAHDQwlhpJ1WwHbpdZE"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

print("🚀 SNIPER V8.6 START")

SENT_FILE = "sent_links.txt"

def load_sent_links():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_link(link):
    with open(SENT_FILE, "a") as f:
        f.write(link + "\n")

sent_links = load_sent_links()


# =========================
# CLEAN
# =========================
def clean(text):
    return re.sub(r"\s+", " ", text).strip().lower()


# =========================
# HELPERS
# =========================
def safe_text(el):
    return el.text.strip() if el else ""


def olx_title(item):
    for selector in ["h6", "h4", "h3", "[data-cy='ad-card-title']", "a"]:
        el = item.select_one(selector)
        if el and el.text.strip():
            return el.text.strip()
    for line in item.get_text(separator="\n").splitlines():
        line = line.strip()
        if len(line) > 5:
            return line
    return ""


def allegro_title(item):
    for selector in ["h2", "h3", "h4", "[class*='title']", "[class*='name']", "a"]:
        el = item.select_one(selector)
        if el and el.text.strip():
            return el.text.strip()
    for line in item.get_text(separator="\n").splitlines():
        line = line.strip()
        if len(line) > 5:
            return line
    return ""


def allegro_link(item):
    a = item.select_one("a")
    if not a:
        return None
    href = a.get("href", "")
    if href.startswith("http"):
        return href
    return "https://allegrolokalnie.pl" + href


# =========================
# PRICE
# =========================
def get_price(text):
    text = text.lower()
    text = re.sub(r"\d+\s*gb", "", text)
    text = re.sub(r"\d+%", "", text)
    matches = re.findall(r"(\d{1,5}(?:[\.,]\d{1,2})?)\s*zł", text)
    if not matches:
        return None
    prices = [float(m.replace(",", ".")) for m in matches]
    prices = [p for p in prices if p >= 5]
    if not prices:
        return None
    return min(prices)


# =========================
# GAME DETECTION
# =========================
def is_game(text):
    t = clean(text)
    game_words = [
        "gra ", "gry ", " game", " games",
        "fifa", "lego ", "mario ", "zelda ",
        "littlebigplanet", "god of war", "monster hunter",
        "crisis core", "final fantasy", "metal gear"
    ]
    return any(g in t for g in game_words)


def is_game_bundle(text):
    t = clean(text)
    many_games = re.search(r"([3-9]|\d{2,})\s*(gier|games|gry)", t)
    return bool(many_games)


# =========================
# GLOBAL FILTER
# =========================
def is_valid(title, full_text):
    t = clean(title)
    full = clean(full_text)

    banned_title = [
        "pudelko", "pudełko", "opakowanie", "box only",
        "samo pudelko", "samo opakowanie", "idealne pudelko",
        "oryginalne opakowanie", "sam box", "karton",
        "umd", "umd movie", "umd film", "film umd", "umd video",
        "elokuva", "peli", " film", "movie", "žaidimai",
        "gra psp", "gra na psp", "gra do psp",
        "gra 3ds", "gra na 3ds", "gra do 3ds",
        "gra gameboy", "gra gba",
        "konto", "psn", "steam", "kod",
        "kabel", "ladowarka", "charger", "bateria", "akumulator",
        "case", "pokrowiec", "etui", "folia", "szklo",
        "adapter", "dock", "stacja", "uchwyt",
        "x7", "x7 slim", "x6 slim", "x9",
        "1000 gier", "10000 gier", "ponad 1000 gier",
    ]

    if any(b in t for b in banned_title):
        return False

    banned_global = [
        "uszkodz", "na czesci", "czesci zamienne",
        "japanese import", "korea", "korean",
        "zamiennik", "replacement",
        "blu-ray", " dvd ",
        "bulk", "random lot",
    ]

    if any(b in full for b in banned_global):
        return False

    return True


# =========================
# CONSOLE FILTER
# =========================
PSP_MODELS = [
    "psp 1000", "psp 2000", "psp 3000", "psp 3004",
    "psp go", "psp street", "psp-1000", "psp-2​​​​​​​​​​​​​​​​
