import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import html
import logging
from random import Random

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import aiosqlite

from steam_web_api import Steam

from db import db_lock


class PostStatus(Enum):
    PUBLISHED = 0
    PENDING_PUBLISH = 1



async def find_steam_ids(
        db: aiosqlite.Connection, steam: Steam,
        steam_request_limit: int, retry_request_period: int = 420,
        retry_attempts: int = 3
        ):
    """
    Проверяет, существует ли игра c предположительным app_id. Если да - сохраняет
    этот app_id, цену игры, скидку на нее в базу
    """
    
    BATCH_SIZE = 30
    
    # Если база пустая - начинаю искать с 1, иначе беру максимальный айдишник и стартую со следующего после него
    start_value = 0
    
    async with db_lock:
        print("start finding...")
        async with db.execute("SELECT EXISTS(SELECT 1 FROM steam_apps_info)") as c:
            if (await c.fetchone())[0] != 0:
                async with db.execute("SELECT MAX(app_id) FROM steam_apps_info") as cr:
                    start_value = int((await cr.fetchone())[0])
        
        insert_count = 0
        for possible_app_id in range(start_value + 1, start_value + steam_request_limit):

            for attempt in range(1, retry_attempts + 1):
                response = steam.apps.get_app_details(possible_app_id, country="RU", filters="price_overview")

                if response is None:
                    # TODO: Log...
                    if attempt != retry_attempts:
                        await asyncio.sleep(retry_request_period)
                        # TODO: Log..
                    else:
                        # TODO: Log..
                        return
                    continue

                break

            if (str(possible_app_id) not in response) or ("data" not in response[str(possible_app_id)]):
                # TODO: Log...
                return

            if response[str(possible_app_id)]["success"] is True:
                app_id = possible_app_id
                if not response[str(possible_app_id)]["data"]:
                    continue
                discount_percent = response[str(possible_app_id)]["data"]["price_overview"]["discount_percent"]
                initial_price = float(response[str(possible_app_id)]["data"]["price_overview"]["initial"]) / 100
                print(f"Finded: {response}")
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
        print("end finding...")




async def update_steam_game_price_and_discount(
        db: aiosqlite.Connection, steam: Steam, update_limit: int,
        retry_request_period: int = 420,
        retry_attempts: int = 3
        ):
    """
    Берет {update_limit} уже опубликованных записей из базы, которым больше 1 месяца, и проверяет, изменилась ли
    скидка или цена на эти игры. Если да - обновляет цену и скидку и меняет на статус PENDING_PUBLISH
    """
    
    async with db_lock:
        print("start udpating...")
        async with db.execute("""
        SELECT app_id, discount_percent, init_price FROM steam_apps_info
        WHERE updated_at <= datetime('now', '-1 month') AND status = ?
        LIMIT ?
        """, (PostStatus.PUBLISHED.value, update_limit)) as c:
            rows = await c.fetchall()

        for app_id, old_discount_percent, old_init_price in rows:


            for attempt in range(1, retry_attempts + 1):
                response = steam.apps.get_app_details(app_id, country="RU", filters="price_overview")

                if response is None:
                    # TODO: Log...
                    if attempt != retry_attempts:
                        # TODO: Log...
                        await asyncio.sleep(retry_request_period)
                    else:
                        # TODO: Log...
                        return

                    continue

                break




            if str(app_id) not in response or ("data" not in response[str(app_id)]):
                # TODO: Log..
                return


            # Проверка что за это время не запретили игру в России
            if response[str(app_id)]["success"] is True:
                new_discount_percent = response[str(app_id)]["data"]["price_overview"]["discount_percent"]
                new_init_price = float(response[str(app_id)]["data"]["price_overview"]["initial"]) / 100

                if new_init_price != old_init_price or new_discount_percent != old_discount_percent:
                    await db.execute("""
                    UPDATE steam_apps_info
                    SET
                        init_price = ?,
                        discount_percent = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE app_id = ?
                    """, (
                        new_init_price, new_discount_percent,
                        PostStatus.PENDING_PUBLISH.value,
                        app_id
                    ))
        
        await db.commit()
        print("end udpating...")

    



async def publish_steam_post(
        db: aiosqlite.Connection, steam: Steam,
        bot: Bot, group_chat_id: int, retry_attempts: int = 3,
        request_retry_period: int = 420
        ):
    """
    Берет запись из базы со статусом PENDING_PUBLISH и опубликовывает ее.

    retry_attempts: int - кол-во попыток запросов, если до этого был превышел лимит steam API.
    Например, другие методы могут делать много запросов, поэтому нужно
    """
    # TODO: написать сообщение для бота: обложка + 3 скрина, название игры, разработчик, краткое описание, старая зачеркнутая цена, стрелочка вправо, цена со скидкой, -{скидка}%
    # и в конце инлайн кнопка Open in Steam с переходом на страницу игры в стиме
    # Публиковать только те, на которые есть скидка. Если скидка=0 - игнорировать
    
    async with (db_lock):
        print("start publishing...")
        async with db.execute("""
        SELECT app_id, discount_percent, init_price FROM steam_apps_info
        WHERE status = ?
        LIMIT 1
        """, (PostStatus.PENDING_PUBLISH.value, )) as c:
            row = await c.fetchone()
            if not row:
                return
            app_id, discount_percent, init_price = row
        

        for attempt in range(1, retry_attempts + 1):
            response = steam.apps.get_app_details(app_id, country="RU")

            # Если превышен лимит обращений к steam API
            if response is None:
                # TODO: Log about attempt...
                if attempt != retry_attempts:
                    await asyncio.sleep(request_retry_period)
                    # TODO: Log...
                else:
                    # TODO: Log...
                    return
                continue

            break

        response = steam.apps.get_app_details(app_id, country="RU")

        # Если формат ответа стал отличаться
        if (str(app_id) not in response) or ("data" not in response[str(app_id)]):
            # TODO: Log...
            return
        
        game_title = response[str(app_id)]["data"]["name"]

        # Если нужно описание на русском, тогда надо подключать нейронку переводчика. steam_web_api не позволяет указать язык для запроса
        game_description_eng = response[str(app_id)]["data"]["short_description"]
        game_cover = response[str(app_id)]["data"]["header_image"]
        
        screenshot_and_developers_response = steam.apps.get_app_details(app_id, country="RU", filters="screenshots,developers")
        screenshot_1 = screenshot_and_developers_response[str(app_id)]["data"]["screenshots"][0]["path_full"]
        screenshot_2 = screenshot_and_developers_response[str(app_id)]["data"]["screenshots"][1]["path_full"]
        screenshot_3 = screenshot_and_developers_response[str(app_id)]["data"]["screenshots"][2]["path_full"]
        
        # Иногда больше одного разработчика
        developers = ", ".join(screenshot_and_developers_response[str(app_id)]["data"]["developers"])


        final_price = init_price - init_price * discount_percent / 100
        post_caption = (
        f"<b>{html.escape(game_title)}</b>\n\n"
        f"Разработчики: <i>{html.escape(developers)}</i>\n\n"
        f"{html.escape(game_description_eng)}\n\n"
        f"<s>{init_price}</s> <b>{final_price:.2f} ₽</b>\n\n<b>-{discount_percent}% 🔥</b>\n\n" 
        f"<a href='https://store.steampowered.com/app/{app_id}'>Открыть в Steam</a>"
        )

        post = [
            InputMediaPhoto(
                media=game_cover,
                caption=post_caption,
                parse_mode="HTML"
            )
        ]

        for screenshot_url in (screenshot_1, screenshot_2, screenshot_3):
            post.append(InputMediaPhoto(media=screenshot_url))
        
        await bot.send_media_group(
            chat_id=group_chat_id,
            media=post
        )

        await db.execute("""
                        UPDATE steam_apps_info
                        SET
                            status = ?
                        WHERE app_id = ?
                        """, (PostStatus.PUBLISHED.value, app_id))
        print("end publishing...")
        await db.commit()

    