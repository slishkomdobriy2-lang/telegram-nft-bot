import asyncio
from telegram import Bot

TOKEN = "8613719930:AAEC4Ky7dgZL9yoQ1FJ6H3dRgsSjVqnQRA4"
USER_ID = "5524166026"

bot = Bot(token=TOKEN)

async def main():
    while True:

    nfts=get_getgems_nfts()

    deals=find_deals(nfts)

    for deal in deals:

        await send_deal(deal)

    await asyncio.sleep(30)

asyncio.run(main())

import requests

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
              address
            }
          }
        }
      }
    }
    """
    }

    r = requests.post(url, json=query)
    data = r.json()

    result=[]

    for item in data["data"]["nftSales"]["edges"]:

        name=item["node"]["nft"]["name"]
        price=int(item["node"]["price"])/1000000000

        result.append({
            "name":name,
            "price":price
        })

    return result

def calculate_profit(buy_price, sell_price):

    fee = sell_price * 0.05

    profit = sell_price - buy_price - fee

    return round(profit,2)

def find_deals(nfts):

    deals=[]

    for nft in nfts:

        if nft["price"] < 20:

            sell_price = nft["price"] * 1.4

            profit = calculate_profit(nft["price"], sell_price)

            if profit >= 3:

                deals.append({
                    "name": nft["name"],
                    "buy": nft["price"],
                    "sell": sell_price,
                    "profit": profit
                })

    return deals

async def send_deal(deal):

    text=f"""
🚨 NFT ARBITRAGE

NFT: {deal['name']}

Buy: {deal['buy']} TON
Sell: {deal['sell']} TON

Profit: {deal['profit']} TON
"""

    await bot.send_message(chat_id=USER_ID,text=text)
