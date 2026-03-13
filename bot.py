import asyncio
import os
import re
import time
import requests

from collections import deque

from telegram import Bot
from telethon import TelegramClient
from telethon.errors import FloodWaitError


# =========================
# ENV (Railway variables)
# =========================

BOT_TOKEN = os.getenv("8789505484:AAFpqqn4AGC-DkDCC3Txjse6YSRSNij6Emw")
USER_ID = int(os.getenv("5524166026"))

API_ID = int(os.getenv("38895122"))
API_HASH = os.getenv("439555adbb1d50504cee21fd4ffc32d7")

PORTALS_CHANNEL = os.getenv("Tonnel_Network_bot", "portals_community")

SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "15"))


# =========================
# SETTINGS
# =========================

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
MIN_ROI = 0.15


# =========================
# INIT
# =========================

bot = Bot(token=BOT_TOKEN)

client = TelegramClient(
    "session",
    API_ID,
    API_HASH,
    system_version="4.16.30"
)

session = requests.Session()

sent_cache = deque(maxlen=1000)

getgems_cache = []
getgems_cache_time = 0


# =========================
# GETGEMS API
# =========================

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

        if r.status_code != 200:
            return []

        data = r.json()

        edges = data.get("data", {}).get("nftSales", {}).get("edges", [])

        result = []

        for item in edges:

            node = item.get("node", {})
            nft = node.get("nft", {})

            name = nft.get("name")
            price_raw = node.get("price")

            if not name or not price_raw:
                continue

            try:
                price = float(price_raw) / 1e9
            except:
                continue

            result.append({
                "name": name,
                "price": price
            })

        return result

    except Exception as e:

        print("Getgems error:", e)
        return []


async def get_getgems():

    global getgems_cache
    global getgems_cache_time

    if time.time() - getgems_cache_time < 30:
        return getgems_cache

    loop = asyncio.get_running_loop()

    tasks = [
        loop.run_in_executor(None, fetch_getgems, i * 100)
        for i in range(6)
    ]

    batches = await asyncio.gather(*tasks)

    result = []

    for b in batches:
        result.extend(b)

    getgems_cache = result
    getgems_cache_time = time.time()

    return result


# =========================
# TELEGRAM MARKET
# =========================

async def get_portals():

    messages = []

    try:

        async for msg in client.iter_messages(PORTALS_CHANNEL, limit=200):

            if msg.text:
                messages.append(msg.text)

    except FloodWaitError as e:

        print("FloodWait:", e.seconds)
        await asyncio.sleep(e.seconds)

    except Exception as e:

        print("Telegram error:", e)

    return messages


# =========================
# MESSAGE INDEX
# =========================

def build_index(messages):

    index = {}

    for msg in messages:

        words = re.findall(r"[a-zA-Z0-9]+", msg.lower())

        for w in words:
            index.setdefault(w, []).append(msg)

    return index


# =========================
# NAME MATCH
# =========================

def name_match(a, b):

    a_words = set(a.lower().split())
    b_words = set(b.lower().split())

    common = a_words & b_words

    return len(common) >= 2


# =========================
# PRICE PARSER
# =========================

def parse_price(text):

    price = re.findall(r"\d+(?:\.\d+)?", text)

    if not price:
        return None

    try:
        return float(price[0])
    except:
        return None


# =========================
# RARE CHECK
# =========================

def is_rare(name, price):

    name = name.lower()

    if any(k in name for k in RARE_KEYWORDS):
        return True

    if price >= RARE_PRICE_THRESHOLD:
        return True

    return False


# =========================
# MARKET COMPARISON
# =========================

def compare_markets(getgems, portals):

    deals = []

    if not getgems or not portals:
        return deals

    portal_index = build_index(portals)

    for g in getgems:

        g_name = g["name"]
        g_price = g["price"]

        words = g_name.lower().split()

        candidates = []

        for w in words:
            candidates.extend(portal_index.get(w, []))

        checked = set()

        for p in candidates:

            if p in checked:
                continue

            checked.add(p)

            if not name_match(g_name, p):
                continue

            portal_price = parse_price(p)

            if not portal_price:
                continue

            profit = portal_price - g_price

            if profit <= 0:
                continue

            roi = profit / g_price

            if roi < MIN_ROI:
                continue

            rare = is_rare(g_name, g_price)

            threshold = 2 if rare else 3

            if profit >= threshold:

                deals.append({

                    "name": g_name,
                    "buy": round(g_price, 2),
                    "sell": round(portal_price, 2),
                    "profit": round(profit, 2),
                    "roi": round(roi * 100, 1),
                    "rare": rare

                })

    deals.sort(key=lambda x: x["profit"], reverse=True)

    return deals


# =========================
# SEND DEAL
# =========================

async def send_deal(deal):

    key = f"{deal['name']}_{deal['buy']}_{deal['sell']}"

    if key in sent_cache:
        return

    sent_cache.append(key)

    tag = "💎 RARE" if deal["rare"] else "⚡ DEAL"

    text = (
        f"{tag} NFT ARBITRAGE\n\n"
        f"NFT: {deal['name']}\n\n"
        f"Buy: {deal['buy']} TON\n"
        f"Sell: {deal['sell']} TON\n\n"
        f"Profit: {deal['profit']} TON\n"
        f"ROI: {deal['roi']} %"
    )

    try:

        await bot.send_message(
            chat_id=USER_ID,
            text=text
        )

    except Exception as e:

        print("Send error:", e)


# =========================
# MAIN LOOP
# =========================

async def main():

    await client.start()

    print("BOT STARTED")

    await bot.send_message(
        chat_id=USER_ID,
        text="✅ Arbitrage bot started"
    )

    while True:

        start = time.time()

        try:

            getgems_task = asyncio.create_task(get_getgems())
            portals_task = asyncio.create_task(get_portals())

            getgems, portals = await asyncio.gather(
                getgems_task,
                portals_task
            )

            deals = compare_markets(getgems, portals)

            print("Deals found:", len(deals))

            for deal in deals[:10]:
                await send_deal(deal)

        except Exception as e:

            print("Main error:", e)

        elapsed = time.time() - start

        sleep = max(5, SCAN_INTERVAL - elapsed)

        await asyncio.sleep(sleep)


# =========================
# RUN
# =========================

if __name__ == "__main__":

    asyncio.run(main())
