import asyncio
from telegram import Bot

TOKEN = "8613719930:AAEC4Ky7dgZL9yoQ1FJ6H3dRgsSjVqnQRA4"
USER_ID = "5524166026"

bot = Bot(token=TOKEN)

async def main():
    while True:
        await bot.send_message(chat_id=USER_ID, text="Бот работает 🚀")
        await asyncio.sleep(60)

asyncio.run(main())
