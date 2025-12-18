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




async def collect_steam_app_ids_task(db: aiosqlite.Connection, logger: logging.Logger, steam_api_key: str):
    """
    Каждый час делает запрос на проверку существования игры с айдишником.
    Это костыль, потому что для доступа к нормальному API
    со всей нужной инфой об играх нужно оформить платный партнерский аккаунт
    """

    PARSE_GAMES_PERIOD = 3600 # каждый час

    while True:
        await usecases.collect_steam_app_ids(db=db, logger=logger, steam_api_key=steam_api_key)

        await asyncio.sleep(PARSE_GAMES_PERIOD)



async def clean_old_posts_task(db: aiosqlite.Connection, logger: logging.Logger):
    """
    Каждый день ищет и удаляет посты, которые не менялись 3 месяца.
    Не менялись значит, что статус = PUBLISHED
    """
    
    CLEAN_OLD_POSTS_PERIOD = 86400 # каждый день

    while True:
        await usecases.clean_old_posts(db=db, logger=logger)

        await asyncio.sleep(CLEAN_OLD_POSTS_PERIOD)


# TODO: переписать + тесты. Теперь этот метод должен брать из базы айдишник 
# и собирать инфу (обложку, скрины, название, описание и тп),
# делая запросы через steam_web_api библиотеку. Подробнее в apps.py у steam_web_api
async def publish_post_task(db: aiosqlite.Connection, bot: Bot, logger: logging.Logger, chat_id: int):
    """
    Получает посты со статусом PENDING_PUBLISH из базы,
    отправляет их в группу,
    ставит статус PUBLISHED,
    обновляет updated_at у этих опубликованных постов
    """
    
    PUBLISH_POST_PERIOD = 5400 # каждые 1.5 часа
    
    while True:
        await usecases.publish_posts(db=db, bot=bot, logger=logger, chat_id=chat_id)

        await asyncio.sleep(PUBLISH_POST_PERIOD)



async def main():
    await init_db()

    BOT_TOKEN = os.getenv("TOKEN")
    CHAT_ID = int(os.getenv("CHAT_ID"))
    STEAM_API_KEY = os.getenv("STEAM_API_KEY")
    bot = Bot(token=BOT_TOKEN)
    STEAM_API = Steam(STEAM_API_KEY)

    asyncio.create_task(find_steam_ids_task(db.db, STEAM_API))



    

    # TODO: Это удалить
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    # TODO: Это все переделать
    asyncio.create_task(publish_post_task(db.db, bot, logger, chat_id=CHAT_ID))
    asyncio.create_task(clean_old_posts_task(db.db, logger))
    asyncio.create_task(collect_steam_app_ids_task(db=db.db, logger=logger, steam_api_key=STEAM_API_KEY))

    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
