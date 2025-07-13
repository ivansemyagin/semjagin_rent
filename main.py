from bs4 import BeautifulSoup
import requests

def parse_flat_info():
    url = "https://inberlinwohnen.de/wohnungsfinder/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de,en;q=0.9",
        "Connection": "keep-alive",
    }

    response = requests.get(url, headers=headers)
    html = response.text  # вот это нужно передавать в BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    flats = []

    for li in soup.select("li.tb-merkflat"):
        flat_id = None
        address = None
        area = None
        rooms = None
        detail_url = None

        # ID объявления из атрибута id="flat_1273643"
        flat_id_attr = li.get("id", "")
        if flat_id_attr.startswith("flat_"):
            flat_id = flat_id_attr.replace("flat_", "").strip()

        # Ссылка на подробности
        link_tag = li.find("a", class_="org-but", href=True)
        if link_tag:
            detail_url = 'https://inberlinwohnen.de'+link_tag["href"].strip()


        # Адрес: ищем <th>Adresse:</th> → ближайший <td>
        address_row = li.find("th", string="Adresse: ")
        if address_row:
            address = address_row.find_next_sibling("td").get_text(strip=True)

        # Кол-во комнат: <th>Zimmeranzahl:</th>
        rooms_row = li.find("th", string="Zimmeranzahl: ")
        if rooms_row:
            rooms = rooms_row.find_next_sibling("td").get_text(strip=True)
            try:
                rooms_value = float(rooms.replace(",", "."))
                if rooms_value < 3:
                    continue  # пропускаем квартиры с < 3 комнатами
                rooms = rooms_value
            except ValueError:
                continue  # если не удалось распарсить число

        # Площадь: <th>Wohnfläche:</th>
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


from telegram import Bot

TELEGRAM_TOKEN = '8198318307:AAHB4T4za1rrCXToh92i0IV7oFf-OVIk1C4'
CHAT_ID = '-4736861986'  # можно временно руками

bot = Bot(token=TELEGRAM_TOKEN)

import asyncio
async def send_to_telegram(flat):
    message = (
        f"🏠 *{flat['rooms']} Zimmer* – *{flat['area']}*\n"
        f"📍 {flat['address']}\n"
        f"[Подробнее]({flat['url']})"
    )
    await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown', disable_web_page_preview=False)



import json
import os

SEEN_FILE = "seen.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)


async def main():
    seen = load_seen()
    new_seen = set(seen)

    flats = parse_flat_info()
    for flat in flats:
        if flat["id"] not in seen:
            await send_to_telegram(flat)
            await asyncio.sleep(5)  # ⏱ пауза 1 секунда
            new_seen.add(flat["id"])

    save_seen(new_seen)

# === 5. Запуск ===
import asyncio
if __name__ == "__main__":
    asyncio.run(main())
