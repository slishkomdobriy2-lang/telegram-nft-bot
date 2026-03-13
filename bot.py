import asyncio
import requests
import re
import time

from telegram import Bot
from telethon import TelegramClient

# --- НАСТРОЙКИ ---

TOKEN = "8613719930:AAEC4Ky7dgZL9yoQ1FJ6H3dRgsSjVqnQRA4"
USER_ID = "5524166026"

api_id = 38895122
api_hash = "439555adbb1d50504cee21fd4ffc32d7"

# канал/чат маркета в Telegram (измени при необходимости)
PORTALS_CHANNEL = "portals_market"

# скорость и лимиты
GETGEMS_BATCH_SIZE = 200       # сколько NFT за один запрос
GETGEMS_BATCHES = 5            # сколько батчей параллельно (итого ~500 NFT)
PORTALS_LIMIT = 150            # сколько сообщений читать из канала
SCAN_INTERVAL = 15             # секунд между циклами

# фильтр "редкости"
RARE_KEYWORDS = ["rare", "legend", "legendary", "epic", "ultra", "gold", "diamond"]
RARE_PRICE_THRESHOLD = 30.0    # если цена >= 30 TON — считаем "редким" (эвристика)

bot = Bot(token=TOKEN)
client = TelegramClient("session", api_id, api_hash)

# общий HTTP-сеанс для ускорения
session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

# --- ПОЛУЧЕНИЕ NFT С GETGEMS (ПАРАЛЛЕЛЬНЫЕ БАТЧИ) ---

GETGEMS_URL = "https://api.getgems.io/graphql"

def build_query(offset: int, limit: int):
    return {
        "query": f"""
        {{
          nftSales(first:{limit}, skip:{offset}){{
            edges{{
              node{{
                price
                nft{{
                  name
                }}
              }}
            }}
          }}
        }}
        """
    }

def fetch_getgems_batch(offset: int, limit: int):
    try:
        r = session.post(GETGEMS_URL, json=build_query(offset, limit), timeout=10)
        r.raise_for_status()
        data = r.json()

        result = []
        edges = data.get("data", {}).get("nftSales", {}).get("edges", [])
        for item in edges:
            node = item.get("node", {})
            nft = node.get("nft", {})
            name = nft.get("name", "Unknown")
            price_raw = node.get("price", 0)
            try:
                price = int(price_raw) / 1_000_000_000
            except:
                price = 0.0

            result.append({
                "name": name,
                "price": price
            })
        return result
    except Exception as e:
        print("Getgems batch error:", e)
        return []

async def get_getgems_nfts_parallel():
    loop = asyncio.get_event_loop()
    tasks = []
    for i in range(GETGEMS_BATCHES):
        offset = i * GETGEMS_BATCH_SIZE
        tasks.append(loop.run_in_executor(None, fetch_getgems_batch, offset, GETGEMS_BATCH_SIZE))
    batches = await asyncio.gather(*tasks, return_exceptions=True)

    nfts = []
    for b in batches:
        if isinstance(b, list):
            nfts.extend(b)
    return nfts

# --- ЧТЕНИЕ TELEGRAM MARKET ---

async def get_portals_market():
    messages = []
    try:
        async for message in client.iter_messages(PORTALS_CHANNEL, limit=PORTALS_LIMIT):
            if message and message.text:
                messages.append(message.text)
    except Exception as e:
        print("Telegram parse error:", e)
    return messages

# --- ПАРСИНГ ЦЕНЫ ---

def parse_price(text: str):
    # ищем числа типа 12 или 8.5
    price = re.findall(r"\d+\.?\d*", text)
    if price:
        try:
            return float(price[0])
        except:
            return None
    return None

# --- ФИЛЬТР РЕДКИХ NFT (ЭВРИСТИКА) ---

def is_rare(nft_name: str, price: float):
    name = (nft_name or "").lower()
    if any(k in name for k in RARE_KEYWORDS):
        return True
    if price >= RARE_PRICE_THRESHOLD:
        return True
    return False

# --- СРАВНЕНИЕ МАРКЕТОВ ---

def compare_markets(getgems, portals):
    deals = []

    for g in getgems:
        g_name = g.get("name", "")
        g_price = g.get("price", 0.0)

        if not g_name or g_price <= 0:
            continue

        for p in portals:
            if g_name.lower() in p.lower():

                portal_price = parse_price(p)
                if not portal_price:
                    continue

                profit = portal_price - g_price
                rare = is_rare(g_name, g_price)

                # если редкий — допускаем меньший порог прибыли
                threshold = 2.0 if rare else 3.0

                if profit >= threshold:
                    deals.append({
                        "name": g_name,
                        "buy": round(g_price, 2),
                        "sell": round(portal_price, 2),
                        "profit": round(profit, 2),
                        "rare": rare
                    })

    return deals

# --- ОТПРАВКА СДЕЛКИ ---

async def send_deal(deal):
    tag = "💎 RARE" if deal.get("rare") else "⚡ DEAL"
    text = f"""
{tag} NFT ARBITRAGE

NFT: {deal['name']}

Buy: {deal['buy']} TON
Sell: {deal['sell']} TON

Profit: {deal['profit']} TON
"""
    try:
        await bot.send_message(chat_id=USER_ID, text=text)
    except Exception as e:
        print("Send message error:", e)

# --- ОСНОВНОЙ ЦИКЛ (ПАРАЛЛЕЛЬНЫЙ СБОР ДАННЫХ) ---

async def main():
    await client.start()
    print("Bot started")

    while True:
        start = time.time()

        try:
            print("Scanning markets...")

            # параллельно собираем данные
            getgems_task = asyncio.create_task(get_getgems_nfts_parallel())
            portals_task = asyncio.create_task(get_portals_market())

            getgems, portals = await asyncio.gather(getgems_task, portals_task)

            deals = compare_markets(getgems, portals)

            if deals:
                print(f"Found deals: {len(deals)}")
                # отправляем не более 10 за цикл, чтобы не спамить
                for deal in deals[:10]:
                    await send_deal(deal)
            else:
                print("No deals found")

        except Exception as e:
            print("Main loop error:", e)

        elapsed = time.time() - start
        sleep_time = max(5, SCAN_INTERVAL - int(elapsed))
        await asyncio.sleep(sleep_time)

# --- ЗАПУСК ---

if __name__ == "__main__":
    asyncio.run(main())
