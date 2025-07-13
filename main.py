import json
import os
import requests
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
import time

# Google Drive
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile

# === Telegram config ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "твой_токен")
CHAT_ID = os.getenv("CHAT_ID", "твой_chat_id")
bot = Bot(token=TELEGRAM_TOKEN)

# === Logging ===
logging.basicConfig(
    filename="flat_parser.log",
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)

# === Google Drive Auth ===
def init_drive():
    from oauth2client.service_account import ServiceAccountCredentials

    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if not creds_json:
        raise Exception("Нет переменной GOOGLE_CREDENTIALS")

    if isinstance(creds_json, str):
        try:
            # Попробуем сразу распарсить строку
            creds_data = json.loads(creds_json)
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка декодирования JSON из переменной GOOGLE_CREDENTIALS: {e}")
            raise
    else:
        raise ValueError("GOOGLE_CREDENTIALS должна быть строкой с JSON.")


    scope = ["https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)

    gauth = GoogleAuth()
    gauth.credentials = credentials
    return GoogleDrive(gauth)

def upload_to_drive(filename, drive, folder_name="parcerlogs"):
    if not os.path.exists(filename):
        return
    try:
        # Проверим, есть ли папка с таким именем
        folder_list = drive.ListFile({
            'q': f"title='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        }).GetList()

        if folder_list:
            folder_id = folder_list[0]['id']
        else:
            folder_metadata = {'title': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
            folder = drive.CreateFile(folder_metadata)
            folder.Upload()
            folder_id = folder['id']

        file_drive = drive.CreateFile({"title": filename, "parents": [{"id": folder_id}]})
        file_drive.SetContentFile(filename)
        file_drive.Upload()
        logging.info(f"Загружено в Google Drive: {filename} в папку {folder_name}")
    except Exception as e:
        logging.error(f"Ошибка загрузки в Google Drive: {e}")

# === 1. Парсинг квартиры ===
def parse_flat_info():
    url = "https://inberlinwohnen.de/wohnungsfinder/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.9",
        "Connection": "keep-alive",
    }

    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            break
        except requests.RequestException as e:
            logging.warning(f"Попытка {attempt + 1} не удалась: {e}")
            time.sleep(5)
    else:
        logging.error("❌ Не удалось получить страницу после 3 попыток.")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    flats = []

    for li in soup.select("li.tb-merkflat"):
        flat_id = None
        address = None
        area = None
        rooms = None
        detail_url = None

        flat_id_attr = li.get("id", "")
        if flat_id_attr.startswith("flat_"):
            flat_id = flat_id_attr.replace("flat_", "").strip()

        link_tag = li.find("a", class_="org-but", href=True)
        if link_tag:
            detail_url = 'https://inberlinwohnen.de' + link_tag["href"].strip()

        address_row = li.find("th", string="Adresse: ")
        if address_row:
            address = address_row.find_next_sibling("td").get_text(strip=True)

        rooms_row = li.find("th", string="Zimmeranzahl: ")
        if rooms_row:
            rooms_text = rooms_row.find_next_sibling("td").get_text(strip=True)
            try:
                rooms_value = float(rooms_text.replace(",", "."))
                if rooms_value < 3:
                    continue
                rooms = rooms_text
            except ValueError:
                continue

        area_row = li.find("th", string="Wohnfläche: ")
        if area_row:
            area = area_row.find_next_sibling("td").get_text(strip=True)

        flats.append({
            "id": flat_id,
            "address": address,
            "rooms": rooms,
            "area": area,
            "url": detail_url
        })

    return flats

# === 2. Seen-файл ===
SEEN_FILE = "seen.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)

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

# === 4. Основной async-цикл с логированием и циклическим запуском ===
async def main():
    drive = init_drive()
    while True:
        logging.info("Запуск проверки новых квартир")
        try:
            seen = load_seen()
            new_seen = set(seen)

            flats = parse_flat_info()
            new_count = 0

            for flat in flats:
                if flat["id"] not in seen:
                    await send_to_telegram(flat)
                    await asyncio.sleep(1)
                    new_seen.add(flat["id"])
                    new_count += 1

            save_seen(new_seen)
            logging.info(f"Найдено и отправлено новых объявлений: {new_count}")

            # Загружаем файлы в Google Drive
            upload_to_drive(SEEN_FILE, drive)
            upload_to_drive("flat_parser.log", drive)

        except Exception as e:
            logging.error(f"Ошибка в основном цикле: {e}")

        await asyncio.sleep(600)

# === 5. Запуск ===
logging.info("\U0001F680 Скрипт стартовал, вызываем main()")
asyncio.run(main())
