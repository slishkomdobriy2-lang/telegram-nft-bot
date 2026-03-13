
import asyncio
import requests
import re

from telegram import Bot
from telethon import TelegramClient

# --- НАСТРОЙКИ ---

TOKEN = "8613719930:AAEC4Ky7dgZL9yoQ1FJ6H3dRgsSjVqnQRA4"
USER_ID = "5524166026"

api_id = 38895122
api_hash = "439555adbb1d50504cee21fd4ffc32d7"

bot = Bot(token=TOKEN)

client = TelegramClient("session", api_id, api_hash)


# --- ПОЛУЧЕНИЕ NFT С GETGEMS ---

def get_getgems_nfts():

    url = "https://api.getgems.io/graphql"

    query = {
        "query": """
        {
          nftSales(first:50){
            edges{
              node{
                price
                nft{
                  name
                }
              }
            }
          }
        }
        """
    }

    try:

        r = requests.post(url, json=query, timeout=10)
        data = r.json()

        result = []

        for item in data["data"]["nftSales"]["edges"]:

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


# --- ЧТЕНИЕ TELEGRAM NFT MARKET ---

async def get_portals_market():

    messages = []

    try:

        async for message in client.iter_messages("portals_market", limit=50):

            if message.text:
                messages.append(message.text)

    except Exception as e:

        print("Telegram parse error:", e)

    return messages


# --- ПАРСИНГ ЦЕНЫ (ПУНКТ 7) ---

def parse_price(text):

    price = re.findall(r"\d+\.?\d*", text)

    if price:
        return float(price[0])

    return None


# --- СРАВНЕНИЕ МАРКЕТОВ ---

def compare_markets(getgems, portals):

    deals = []

    for g in getgems:

        for p in portals:

            if g["name"].lower() in p.lower():

                portal_price = parse_price(p)

                if portal_price:

                    profit = portal_price - g["price"]

                    if profit > 3:

                        deals.append({
                            "name": g["name"],
                            "buy": g["price"],
                            "sell": portal_price,
                            "profit": round(profit, 2)
                        })

    return deals


# --- ОТПРАВКА СДЕЛКИ В TELEGRAM ---

async def send_deal(deal):

    text = f"""
🚨 NFT ARBITRAGE

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

        print("Send message error:", e)


# --- ОСНОВНОЙ ЦИКЛ БОТА ---

async def main():

    await client.start()

    while True:

        try:

            print("Scanning markets...")

            getgems = get_getgems_nfts()

            portals = await get_portals_market()

            deals = compare_markets(getgems, portals)

            for deal in deals:

                await send_deal(deal)

        except Exception as e:

            print("Main loop error:", e)

        await asyncio.sleep(30)


# --- ЗАПУСК ---

asyncio.run(main())
