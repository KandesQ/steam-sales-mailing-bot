import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot
from dotenv import load_dotenv


import usecases
import db

from db import init_db

from steam_web_api import Steam


load_dotenv()



async def find_steam_ids_task(db: aiosqlite.Connection, steam: Steam):
    """
    Каждый час ищет id игр из Steam
    """

    STEAM_REQUEST_LIMIT = 200 # через 200 запросов начинает давать None. Сбрасывается каждые 5 мин
    REQUEST_PERIOD = 3600 # 1 час

    while True:
        await usecases.find_steam_ids(db, steam, STEAM_REQUEST_LIMIT)

        await asyncio.sleep(REQUEST_PERIOD)



async def update_steam_game_price_and_discount_task(db: aiosqlite.Connection, steam: Steam):
    """
    Каждый день обновляет данные о скидках и ценах игр стима
    """

    UPDATE_PRICE_OR_DICOUNT_PERIOD = 86400 # 1 день
    UPDATE_LIMIT = 100
    
    while True:
        await usecases.update_steam_game_price_and_discount(db, steam, UPDATE_LIMIT)

        await asyncio.sleep(UPDATE_PRICE_OR_DICOUNT_PERIOD)




async def main():
    await init_db()

    BOT_TOKEN = os.getenv("TOKEN")
    CHAT_ID = int(os.getenv("CHAT_ID"))
    STEAM_API_KEY = os.getenv("STEAM_API_KEY")
    bot = Bot(token=BOT_TOKEN)
    STEAM_API = Steam(STEAM_API_KEY)

    asyncio.create_task(find_steam_ids_task(db.db, STEAM_API))
    asyncio.create_task(update_steam_game_price_and_discount_task(db.db, STEAM_API))    


    # # TODO: Это удалить
    # logging.basicConfig(
    #     level=logging.INFO,
    #     format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    #     datefmt='%Y-%m-%d %H:%M:%S'
    # )


    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
