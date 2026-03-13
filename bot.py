import asyncio
import requests
import re
import time

from telegram import Bot
from telethon import TelegramClient

# --- НАСТРОЙКИ ---

TOKEN = "8789505484:AAFpqqn4AGC-DkDCC3Txjse6YSRSNij6Emw"
USER_ID = "5524166026"

api_id = 38895122
api_hash = "439555adbb1d50504cee21fd4ffc32d7"

PORTALS_CHANNEL = "portals_market"

SCAN_INTERVAL = 15

RARE_KEYWORDS = [
    "rare",
    "legend",
    "legendary",
    "epic",
    "ultra",
    "diamond",
    "gold"
]

RARE_PRICE_THRESHOLD = 30

bot = Bot(token=TOKEN)
client = TelegramClient("session", api_id, api_hash)

session = requests.Session()

# --- КЕШ СДЕЛОК (АНТИ ДУБЛИ) ---

sent_cache = set()

MAX_CACHE = 1000


# --- GETGEMS API ---

def fetch_getgems(offset):

    url = "https://api.getgems.io/graphql"

    query = {
        "query": f"""
        {{
          nftSales(first:100, skip:{offset}){{
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

    try:

        r = session.post(url, json=query, timeout=10)

        data = r.json()

        result = []

        edges = data["data"]["nftSales"]["edges"]

        for item in edges:

            name = item["node"]["nft"]["name"]

            price = int(item["node"]["price"]) / 1000000000

            result.append({
                "name": name,
                "price": price
            })

        return result

    except Exception as e:

        print("Getgems error:", e)

        return []


async def get_getgems():

    loop = asyncio.get_event_loop()

    tasks = []

    for i in range(5):

        tasks.append(
            loop.run_in_executor(
                None,
                fetch_getgems,
                i * 100
            )
        )

    batches = await asyncio.gather(*tasks)

    result = []

    for b in batches:

        result += b

    return result


# --- TELEGRAM MARKET ---

async def get_portals():

    messages = []

    try:

        async for msg in client.iter_messages(PORTALS_CHANNEL, limit=150):

            if msg.text:

                messages.append(msg.text)

    except Exception as e:

        print("Telegram error:", e)

    return messages


# --- ПАРСИНГ ЦЕНЫ ---

def parse_price(text):

    price = re.findall(r"\d+\.?\d*", text)

    if price:

        try:

            return float(price[0])

        except:

            return None

    return None


# --- ПРОВЕРКА РЕДКОСТИ NFT ---

def is_rare(name, price):

    name = name.lower()

    for k in RARE_KEYWORDS:

        if k in name:

            return True

    if price >= RARE_PRICE_THRESHOLD:

        return True

    return False


# --- ПОИСК АРБИТРАЖА ---

def compare_markets(getgems, portals):

    deals = []

    for g in getgems:

        g_name = g["name"]

        g_price = g["price"]

        for p in portals:

            if g_name.lower() in p.lower():

                portal_price = parse_price(p)

                if not portal_price:

                    continue

                profit = portal_price - g_price

                rare = is_rare(g_name, g_price)

                threshold = 2 if rare else 3

                if profit >= threshold:

                    deals.append({

                        "name": g_name,

                        "buy": round(g_price,2),

                        "sell": round(portal_price,2),

                        "profit": round(profit,2),

                        "rare": rare

                    })

    return deals


# --- ОТПРАВКА СИГНАЛА ---

async def send_deal(deal):

    key = f"{deal['name']}_{deal['buy']}_{deal['sell']}"

    if key in sent_cache:

        return

    sent_cache.add(key)

    if len(sent_cache) > MAX_CACHE:

        sent_cache.pop()

    tag = "💎 RARE" if deal["rare"] else "⚡ DEAL"

    text = f"""
{tag} NFT ARBITRAGE

NFT: {deal['name']}

Buy: {deal['buy']} TON
Sell: {deal['sell']} TON

Profit: {deal['profit']} TON
"""

    try:

        await bot.send_message(

            chat_id=USER_ID,

            text=text

        )

    except Exception as e:

        print("Send error:", e)


# --- ОСНОВНОЙ ЦИКЛ ---

async def main():

    await client.start()

    print("BOT STARTED")

    while True:

        start = time.time()

        try:

            print("Scanning markets...")

            getgems_task = asyncio.create_task(get_getgems())

            portals_task = asyncio.create_task(get_portals())

            getgems, portals = await asyncio.gather(

                getgems_task,

                portals_task

            )

            deals = compare_markets(

                getgems,

                portals

            )

            print("Deals found:", len(deals))

            for deal in deals[:10]:

                await send_deal(deal)

        except Exception as e:

            print("Main error:", e)

        elapsed = time.time() - start

        sleep = max(5, SCAN_INTERVAL - int(elapsed))

        await asyncio.sleep(sleep)


# --- ЗАПУСК ---

asyncio.run(main())
