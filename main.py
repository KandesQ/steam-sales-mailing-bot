import asyncio
import logging
import os
from random import Random
import aiosqlite

from aiogram import Bot
from dotenv import load_dotenv


import usecases
import db

from db import init_db

from steam_web_api import Steam


load_dotenv()



async def find_steam_ids_task(db: aiosqlite.Connection, steam: Steam, logger: logging.Logger):
    """
    Каждый час ищет id игр из Steam
    """

    STEAM_REQUEST_LIMIT = 200 # через 200 запросов начинает давать None. Сбрасывается каждые 5 мин
    REQUEST_PERIOD = 3600 # 1 час

    # сейчас проблема что в юзкейсе логика лимитов, хотя он сам должен представлять одно действие а не повторение нескольких.
    # TODO: в будущем вынести лимит сюда, чтобы STEAM_REQUEST_LIMIT раз вызывался find_steam_ids, а не в нем самом цикл лимита был. Для
    # остальных юзкейсов аналогично
    while True:
        await usecases.find_steam_ids(db, steam, STEAM_REQUEST_LIMIT, logger)

        await asyncio.sleep(10)



async def update_steam_game_price_and_discount_task(db: aiosqlite.Connection, steam: Steam):
    """
    Каждый день обновляет данные о скидках и ценах игр стима
    """

    UPDATE_PRICE_OR_DICOUNT_PERIOD = 86400 # 1 день
    UPDATE_LIMIT = 100
    
    while True:
        await usecases.update_steam_game_price_and_discount(db, steam, UPDATE_LIMIT)

        await asyncio.sleep(10)



async def publish_steam_post_task(db: aiosqlite.Connection, steam: Steam, bot: Bot, group_chat_id: int):
    """
    В день отправляет 2 - 5 постов с переменной разницей отправки от 45 мин до 2 часов
    """
    
    PUBLISH_PERIOD = 86400 # 1 день
    rnd = Random()

    while True:
        post_limit = rnd.randint(2, 5)

        for _ in range(post_limit):
            await usecases.publish_steam_post(db, steam, bot, group_chat_id)
            
            # До след поста 45 мин или 120 мин (2 часа)
            POST_PERIOD = rnd.randint(45, 120) * 60
            await asyncio.sleep(10)
        
        await asyncio.sleep(10)



async def main():
    await init_db()

    BOT_TOKEN = os.getenv("TOKEN")
    CHAT_ID = int(os.getenv("CHAT_ID"))
    STEAM_API_KEY = os.getenv("STEAM_API_KEY")
    bot = Bot(token=BOT_TOKEN)
    STEAM_API = Steam(STEAM_API_KEY)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    asyncio.create_task(find_steam_ids_task(db.db, STEAM_API, logger))
    # asyncio.create_task(update_steam_game_price_and_discount_task(db.db, STEAM_API))
    # asyncio.create_task(publish_steam_post_task(db.db, STEAM_API, bot, CHAT_ID))

    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
