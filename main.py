import asyncio
import logging
import os
import aiosqlite

from aiogram import Bot
from dotenv import load_dotenv


import usecases
import db

from db import init_db



load_dotenv()



PARSE_GAMES_PERIOD = 3600 # каждый час
async def parse_steam_games_task(db: aiosqlite.Connection, logger: logging.Logger, steam_api_key: str):
    """
    Каждый час делает запросы к Steamworks API на получение игр, у которых есть скидки,
    формирует из них посты и сохраняет их в базу
    """

    PARSE_GAMES_PERIOD = 3600 # каждый час

    while True:
        await usecases.parse_steam_games(db=db, logger=logger, steam_api_key=steam_api_key)

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

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)


    asyncio.create_task(publish_post_task(db.db, bot, logger, chat_id=CHAT_ID))
    asyncio.create_task(clean_old_posts_task(db.db, logger))
    asyncio.create_task(parse_steam_games_task(db=db.db, logger=logger, steam_api_key=STEAM_API_KEY))

    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
