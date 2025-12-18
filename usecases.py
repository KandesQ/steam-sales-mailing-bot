import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import html
import logging
from random import Random

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite

from steam_web_api import Steam



logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
logger = logging.getLogger(__name__)



class PostStatus(Enum):
    PUBLISHED = 0
    PENDING_PUBLISH = 1



async def find_steam_ids(db: aiosqlite.Connection, steam: Steam, steam_request_limit: int):
    """
    Проверяет, существует ли игра c предположительным app_id. Если да - сохраняет
    этот app_id, цену игры, скидку на нее в базу
    """
    
    BATCH_SIZE = 30
    
    # Если база пустая - начинаю искать с 1, иначе беру максимальный айдишник и стартую со следующего после него
    start_value = 0
    async with db.execute("SELECT EXISTS(SELECT 1 FROM steam_apps_info)") as c:
        if (await c.fetchone())[0] != 0:
            async with db.execute("SELECT MAX(app_id) FROM steam_apps_info") as cr:
                start_value = int((await cr.fetchone())[0])
    
    insert_count = 0
    for possible_app_id in range(start_value + 1, start_value + steam_request_limit):
        response = steam.apps.get_app_details(possible_app_id, country="RU", filters="price_overview")
        if response[str(possible_app_id)]["success"] is True:
            app_id = possible_app_id
            discount_percent = response[str(possible_app_id)]["data"]["price_overview"]["discount_percent"]
            initial_price = float(response[str(possible_app_id)]["data"]["price_overview"]["initial"]) / 100

            await db.execute(
                """
                INSERT INTO steam_apps_info (
                    app_id,
                    discount_percent,
                    init_price,
                    status
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    app_id, discount_percent,
                    initial_price, PostStatus.PENDING_PUBLISH.value
                )
            )
            insert_count += 1
            if insert_count % BATCH_SIZE == 0:
                await db.commit()
    
    # Коммит остатка, если есть
    if insert_count % BATCH_SIZE != 0:
        await db.commit()




async def update_price_and_discount():
    """
    Берет уже опубликованную запись из базы, которой больше 1 месяца, и проверяет, изменилась ли
    скидка или цена на эту игру. Если да - обновляет цену и скидку и меняет на статус PENDING_PUBLISH
    """
    pass



async def publish_post():
    """
    Берет запись из базы со статусом PENDING_PUBLISH и опубликовывает ее.
    DELETE: В день должен отправлять 2 - 5 постов с переменной разницей отправки от 45 мин до 2 часов. Этот коммент в таску
    положить, а отсюда удалить
    """
    # TODO: сделать запрос с фильтром на получение обложки, 3 скринов, разработчиков, цены и скидки
    # TODO: написать сообщение для бота: обложка + 3 скрина, название игры, разработчик, краткое описание, старая зачеркнутая цена, стрелочка вправо, цена со скидкой, -{скидка}%
    # Публиковать только те, на которые есть скидка. Если скидка=0 - игнорировать
    pass