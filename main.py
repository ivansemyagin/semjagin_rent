import json
import os
import requests
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
import time
import sys
import traceback
import random
from fake_useragent import UserAgent
ua = UserAgent()
import brotli
from io import BytesIO
import re
from urllib.parse import urljoin

# === Telegram config ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "твой_токен")
CHAT_ID = os.getenv("CHAT_ID", "твой_chat_id")
bot = Bot(token=TELEGRAM_TOKEN)

# === Пути для Volume ===
os.makedirs("/data", exist_ok=True)
LOG_FILE = "/data/flat_parser.log"
SEEN_FILE = "/data/seen1.json"

# === Logging (и в файл, и в stdout для Railway) ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# === 1. Парсинг квартиры с учетом пагинации ===
def parse_flat_info(session):
    base_url = "https://www.inberlinwohnen.de/wohnungsfinder/"

    headers = {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "TE": "trailers",
    }

    flats = []
    next_url = base_url
    visited = set()

    while next_url and next_url not in visited:
        url = next_url
        visited.add(url)

        # загрузка одной страницы объявлений
        for attempt in range(3):
            try:
                time.sleep(random.uniform(2, 5))
                response = session.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                html = response.text
                break
            except requests.RequestException as e:
                logging.warning(f"Попытка {attempt + 1} не удалась: {e}")
                logging.warning(traceback.format_exc())
        else:
            logging.error(f"❌ Не удалось получить страницу {url} после 3 попыток.")
            break

        soup = BeautifulSoup(html, "html.parser")

        listings = soup.select("div[id^='apartment-']")
        logging.info(f"Найдено объявлений на странице: {len(listings)}")

        for item in listings:

            flat_id_attr = item.get("id", "")
            flat_id = flat_id_attr.replace("apartment-", "").strip() if flat_id_attr else None

            link_tag = item.find("a", href=True)
            detail_url = urljoin(url, link_tag["href"].strip()) if link_tag else None

            info_span = item.find("span", class_="block")
            if not info_span:
                continue
            info_text = " ".join(info_span.stripped_strings)
            match = re.search(r"(\d+,\d+)\s*Zimmer,\s*(\d+,\d+)\s*m²,\s*[\d.,]+\s*€.*?,\s*(.*)", info_text)
            if not match:
                continue
            rooms_text, area_val, address = match.groups()
            try:
                rooms_value = float(rooms_text.replace(",", "."))
                if rooms_value < 4:
                    continue
            except ValueError:
                continue

            area = f"{area_val} m²"
            rooms = rooms_text

            flats.append({
                "id": flat_id,
                "address": address,
                "rooms": rooms,
                "area": area,
                "url": detail_url,
            })

        # поиск ссылки на следующую страницу
        next_url = None
        selectors = [
            "a[rel='next']",
            "a.next",
            "li.next a",
            "a.pagination-next",
        ]
        for sel in selectors:
            link = soup.select_one(f"{sel}[href]")
            if link:
                candidate = urljoin(url, link["href"])
                if candidate not in visited:
                    next_url = candidate
                    break
        if not next_url:
            for a in soup.find_all("a", href=True):
                if a.get_text(strip=True) in (">", "›", "Weiter", "Next", "»"):
                    candidate = urljoin(url, a["href"])
                    if candidate not in visited:
                        next_url = candidate
                        break
        if next_url:
            logging.info(f"Переходим на следующую страницу: {next_url}")

    return flats

# === 2. Работа с локальным seen.json через Volume ===
def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception as e:
            logging.error(f"Ошибка загрузки seen.json: {e}")
    return set()

def save_seen(seen_ids):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_ids), f)
    except Exception as e:
        logging.error(f"Ошибка сохранения seen.json: {e}")

# === 3. Async Telegram отправка ===
async def send_to_telegram(flat):
    message = (
        f"\U0001F3E0 *{flat['rooms']} Zimmer* – *{flat['area']}*\n"
        f"\U0001F4CD {flat['address']}\n"
        f"[Подробнее]({flat['url']})"
    )
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=False
        )
    except Exception as e:
        logging.error(f"Ошибка отправки Telegram: {e}")

# === 4. Основной async-цикл ===
async def main():
    logging.info("▶️ Скрипт запустился в Railway")
    while True:
        with requests.Session() as session:
            logging.info("\U0001F50D Запуск проверки новых квартир")
            try:
                seen = load_seen()
                new_seen = set(seen)
    
                flats = parse_flat_info(session)
                logging.info(f"Найдено объявлений: {len(flats)}")
                new_count = 0
    
                for flat in flats:
                    if flat["id"] not in seen:
                        await send_to_telegram(flat)
                        await asyncio.sleep(1)
                        new_seen.add(flat["id"])
                        new_count += 1
    
                save_seen(new_seen)
                logging.info(f"Найдено и отправлено новых объявлений: {new_count}")
    
            except Exception as e:
                logging.error(f"Ошибка в основном цикле: {e}")
    
        await asyncio.sleep(300)



# === 5. Запуск ===
if __name__ == "__main__":
    logging.info("📦 Запуск контейнера")
    try:
        asyncio.run(main())
    except Exception as e:
        logging.exception(f"❌ Ошибка при запуске скрипта: {e}")

