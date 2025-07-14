import json
import os
import requests
import asyncio
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from telegram import Bot
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === Telegram config ===
TELEGRAM_TOKEN = '8198318307:AAHB4T4za1rrCXToh92i0IV7oFf-OVIk1C4'
CHAT_ID = '-4736861986'  # можно временно руками
bot = Bot(token=TELEGRAM_TOKEN)

# === Logging ===
logging.basicConfig(
    filename="flat_parser.log",
    level=logging.INFO,
    format="%(asctime)s — %(levelname)s — %(message)s"
)

# === Google Sheets Auth ===
def get_gsheet():
    creds_json = {
  "type": "service_account",
  "project_id": "empirical-envoy-298802",
  "private_key_id": "22d8c04a968b68d4d70174c1a6542d7e4e41406f",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCP8hJ+W/kN8luo\ntnDFfWFhyy239pIFR/XijROYkCJ0zOpxXags5T6LGj5EamamJ3JDG0Ubgj5Z7nWC\nsCfUcbNyWeoQZuc9L4+GoHN49sBXpF6N54fRvqTsuqvBf9uw9VLDxEQCFfqNCvOJ\ndVAGGEoXU0eG4+aRAWE/FKpvEvuuTMxNZ+osk+cUNcUtgq4HlJ9qSNDsWjI+R9bS\nUga6BoQ09FtJlA8qRiuwWfnREzr9Tv7JmEMbTsJrj/dJPQAKHhqBayuu/xVjrzDd\ntlbHm4NUyCF884ngDGfcGPS5dMkk3y1CsByk6cPs/GJyk1AQ2HigrJCNJfhLMGkH\n3HJpE66HAgMBAAECggEAFLwxpssX4sbtJi31q7UmcIBkmxHlMeaOSG67CmiE1h9o\njCEKJ0F0k3QZ0SAknj2ja4BDobVOxwSfH87BRgyE5W2HVoqEN9+ghKubRqsAxP8z\n8awO+AtG1aUENdD1tBV6sSGWDFjfKS8RKtVfzCj2j0qbTJaKsYup1vzimjJ5V7+Y\nAaKYy74ZyyF/SVeFxXe3d30PD4rvNOaQBxECS5znP0kTEXftmjKL8NejixSuj9Ab\nwjwYWt0u3IKKR7IKd0m/g7zQZ2Eojrie0+geM5KNDTKakdq5FtbsA8j6nZXWe8GS\nrZQZ6WblghG6fOMzraCvpadoM+3/7oZ7pfgYMUAxJQKBgQDE/5798iAiQIZfRu2N\niApMQHV1L9mj8iNZV1PeGlXsMjvVP4wLkYRxt9rRWkMan7wEsfo7iA6b/qvLylLl\n3VBi/2zqUGpxnxtlTbB3GFa7I/ylaMHLMvVaQft1qW1fm+MroiIoPS86zTOQw4q9\nf+z3QDdyw+smLFTd3Je39G4UqwKBgQC7Dr+D1NjLBFNWXe43q41ITCDRO4F4mDZq\npN/U80lqpughvroXQNa2H4CuAqn0gOqy+0weoD0bWzaqiJKy+LgcGXYDwQA3I72G\n+AhPttdR7PvsHWENZUwEWXRUDZADaL2SHfpC13TtnxfkLK0JXwcoUI1BKjV++n7o\nEukfPa71lQKBgCTWZAW6pBWjmTzxx3Qiz0Io/43VT85fdgq70LwEkrKjRhr/UhHL\nuUeGiM2DIm81FXSPT2qYa5ryCXAHOm8vblvExbofJXhvtzC/UVND4twFw7WunCaC\nNe0Vz47WCtTJErbTD64UmuNVAeJ9HlGHPWmSwYudZThzK799A4XrmDYXAoGATUFj\nEZSH0RlBPgtfRnjAyho+94tHBsJ+vv7HPxEXwkea2c0G2HG7+834/GU3Qjc4N6GY\nJ5HwiuraIgZz6BzXFSvi1NwSNbO6JBMug5W1Si3BQhxEKB8tDSLQ66IKV44btUxS\nPubzcOxjFqbo9FTeBOV34XEIVSAp57lftLpqFx0CgYA5DKrlHBwUF7Oo/+wAbLmo\nzMV4BtjzPWkc8hk0C3JY0WGYCt9JXFQy+O5ezk/VtJUFFlxANj+6hR4w28nyspEN\n4O+YYSWYOPrYQbJ2AabXsupYQycGk8Tfdcy4fuc6pfUFssR9ZO8oLpQ3C25s4Gql\nxgwWcmlihd/LnrfRF4UdJQ==\n-----END PRIVATE KEY-----\n",
  "client_email": "acc2-64@empirical-envoy-298802.iam.gserviceaccount.com",
  "client_id": "101954012311503927338",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/acc2-64%40empirical-envoy-298802.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

    if not creds_json:
        raise Exception("Нет переменной GOOGLE_CREDENTIALS")

    if isinstance(creds_json, str):
        creds_json = creds_json.replace("\\n", "\n")
        creds_data = json.loads(creds_json)
    else:
        creds_data = creds_json

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_data, scope)
    client = gspread.authorize(credentials)
    sheet = client.open("Berlin Flats Seen").sheet1  # Название таблицы и листа
    return sheet

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

# === 2. Работа с Google Sheets вместо seen.json ===
def load_seen(sheet):
    try:
        values = sheet.col_values(1)[1:]  # Пропускаем заголовок
        return set(values)
    except Exception as e:
        print(f"Ошибка загрузки seen из Google Sheets: {e}")
        return set()

def save_seen(sheet, seen_ids):
    try:
        sheet.clear()
        sheet.append_row(["seen_ids"])
        for flat_id in seen_ids:
            sheet.append_row([flat_id])
    except Exception as e:
        print(f"Ошибка сохранения seen в Google Sheets: {e}")

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
        print(f"Ошибка отправки Telegram: {e}")

# === 4. Основной async-цикл ===
async def main():
    sheet = get_gsheet()
    while True:
        print("\U0001F50D Запуск проверки новых квартир")
        try:
            seen = load_seen(sheet)
            new_seen = set(seen)

            flats = parse_flat_info()
            new_count = 0

            for flat in flats:
                if flat["id"] not in seen:
                    await send_to_telegram(flat)
                    await asyncio.sleep(1)
                    new_seen.add(flat["id"])
                    new_count += 1

            save_seen(sheet, new_seen)
            print(f"Найдено и отправлено новых объявлений: {new_count}")

        except Exception as e:
            print(f"Ошибка в основном цикле: {e}")

        await asyncio.sleep(600)

# === 5. Запуск ===
print("\U0001F680 Скрипт стартовал, вызываем main()")
#asyncio.run(main())
asyncio.run(main())
