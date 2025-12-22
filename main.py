import asyncio
import datetime
import logging
import os
from zoneinfo import ZoneInfo

from aiogram import Bot
from dotenv import load_dotenv
from steam_web_api import Steam

import db
import usecases
from db import init_db

load_dotenv()



BOT_TOKEN = os.getenv("TOKEN")
BOT = Bot(token=BOT_TOKEN)

CHAT_ID = int(os.getenv("CHAT_ID"))

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_API = Steam(STEAM_API_KEY)

logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
logger = logging.getLogger(__name__)


MSK = ZoneInfo("Europe/Moscow")
def now_msk_time():
    return datetime.datetime.now(tz=MSK).time()



async def dispatch_tasks():
    while True:
        now = now_msk_time()

        if datetime.time(18, 0) <= now or now < datetime.time(2, 0):

            # С 18:00 до 2:00 по мск ищет id игр из Steam
            STEAM_REQUEST_LIMIT = 200
            await usecases.find_steam_ids(db.db, STEAM_API, STEAM_REQUEST_LIMIT, logger)

        elif datetime.time(2, 0) <= now < datetime.time(8, 0):

            # С 2:00 до 8:00 по мск обновляет данные о скидках и ценах игр стим
            UPDATE_LIMIT = 100
            await usecases.update_steam_game_price_and_discount(db.db, STEAM_API, UPDATE_LIMIT, logger)

        elif datetime.time(8, 0) <= now < datetime.time(18, 0):

            # С 8:00 до 18:00 отправляет посты о распродажал и скидках на игры из steam
            await usecases.publish_steam_post(db.db, STEAM_API, BOT, CHAT_ID, logger)

        await asyncio.sleep(30)


async def main():
    await init_db()

    await dispatch_tasks()

if __name__ == '__main__':
    asyncio.run(main())
