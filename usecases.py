import asyncio
import html
import logging
from enum import Enum
from random import Random

import aiosqlite
from aiogram import Bot
from aiogram.types import InputMediaPhoto
from steam_web_api import Steam

from db import db_lock


class PostStatus(Enum):
    PUBLISHED = 0
    PENDING_PUBLISH = 1



async def find_steam_ids(
        db: aiosqlite.Connection, steam: Steam,
        steam_request_limit: int, logger: logging.Logger, retry_request_period: int = 420,
        retry_attempts: int = 3
        ):
    """
    Проверяет, существует ли игра c предположительным app_id. Если да - сохраняет
    этот app_id, цену игры, скидку на нее в базу
    """
    
    BATCH_SIZE = 30

    # Храню счетчик возможных айдишников в файле. Между перезапусками он не должн теряться
    try:
        with open("counter.txt", "r") as f:
            start_value = int(f.read())
    except FileNotFoundError:
        logger.error("Could not load app id counter. File doesn't exist")
        return

    logger.info("Start finding steam ids from start_value=%s", start_value + 1)
    
    async with db_lock:
        insert_count = 0
        for possible_app_id in range(start_value + 1, start_value + steam_request_limit + 1):
            for attempt in range(1, retry_attempts + 1):
                response = steam.apps.get_app_details(possible_app_id, country="RU", filters="price_overview")

                if response is None:
                    if attempt != retry_attempts:
                        logger.info(f"Steam API request limit reached. Waiting for {int(retry_request_period / 60)} minutes. Retry attempt: {attempt}")
                        await asyncio.sleep(retry_request_period)
                    else:
                        logger.error(f"Retry attempts for app_id={possible_app_id} exceeded. Task will be delayed")
                        return
                    continue

                break


            if str(possible_app_id) not in response:
                logger.error("The response with app_id=%s has no app_id attribute. "
                             "General response format might have changed", possible_app_id)
                return

            if "data" not in response[str(possible_app_id)] and response[str(possible_app_id)]["success"] is True:
                logger.warning(f"The response with app_id=%s has no data attribute. "
                               f"app_id=%s may have wrong response format or is unavailable in Russia",
                               possible_app_id, possible_app_id)
                continue

            if response[str(possible_app_id)]["success"] is True:
                logger.info("Successfully found a game with app_id=%s", possible_app_id)

                app_id = possible_app_id
                if not response[str(app_id)]["data"]:
                    logger.info("The game with app_id=%s has no pricing data. It's probably free", possible_app_id)
                    continue
                discount_percent = response[str(app_id)]["data"]["price_overview"]["discount_percent"]
                initial_price = float(response[str(app_id)]["data"]["price_overview"]["initial"]) / 100

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
                    logger.info("Inserted %d rows into steam_apps_info", insert_count)
                    await db.commit()

        # Коммит остатка, если есть
        if insert_count % BATCH_SIZE != 0:
            logger.info("Inserted %d rows into steam_apps_info", insert_count)
            await db.commit()

        # обновляю счетчик
        with open("counter.txt", "w") as f:
            f.write(str(start_value + steam_request_limit))
            logger.info("Counter is updated with value=%s",
                        start_value + steam_request_limit)



async def update_steam_game_price_and_discount(
        db: aiosqlite.Connection, steam: Steam, update_limit: int,
        logger: logging.Logger, retry_request_period: int = 420,
        retry_attempts: int = 3
        ):
    """
    Берет {update_limit} уже опубликованных записей из базы, которым больше 1 месяца, и проверяет, изменилась ли
    скидка или цена на эти игры. Если да - обновляет цену и скидку и меняет на статус PENDING_PUBLISH
    """
    
    async with db_lock:
        logger.info("Start updating existing posts info...")
        async with db.execute("""
        SELECT app_id, discount_percent, init_price FROM steam_apps_info
        WHERE updated_at <= datetime('now', '-1 month') AND status = ?
        LIMIT ?
        """, (PostStatus.PUBLISHED.value, update_limit)) as c:
            rows = await c.fetchall()
            logger.info("Found %d requiring update rows", len(rows))

        for app_id, old_discount_percent, old_init_price in rows:

            for attempt in range(1, retry_attempts + 1):
                response = steam.apps.get_app_details(app_id, country="RU", filters="price_overview")

                if response is None:
                    if attempt != retry_attempts:
                        logger.info(f"Steam API request limit reached. Waiting for {int(retry_request_period / 60)} minutes. Retry attempt: {attempt}")
                        await asyncio.sleep(retry_request_period)
                    else:
                        logger.error(f"Retry attempts for app_id={app_id} exceeded. Task will be delayed")
                        return

                    continue

                break


            if str(app_id) not in response:
                logger.error("The response with app_id=%s has no app_id attribute. "
                             "General response format might have changed", app_id)
                return

            if "data" not in response[str(app_id)] and response[str(app_id)]["success"] is True:
                logger.warning(f"The response with app_id=%s has no data attribute. "
                               f"app_id=%s may have wrong response format or is unavailable in Russia",
                               app_id, app_id)
                continue

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
                    logger.info("Successfully updated price info of game with app_id=%s", app_id)
    



async def publish_steam_post(
        db: aiosqlite.Connection, steam: Steam,
        bot: Bot, group_chat_id: int, logger: logging.Logger, retry_attempts: int = 3,
        request_retry_period: int = 420
        ):
    """
    Берет запись из базы со статусом PENDING_PUBLISH и опубликовывает ее через бота в группу с
    id=group_chat_id.
    В день отправляет 2-5 постов с переменной разницей отправки от 45 мин до 2 часов
    """
    
    async with (db_lock):
        rnd = Random()
        post_limit = rnd.randint(2, 5)
        for post_number in range(1, post_limit + 1):
            logger.info("Start publish game sales posts from steam...")
            async with db.execute("""
            SELECT app_id, discount_percent, init_price FROM steam_apps_info
            WHERE status = ?
            LIMIT 1
            """, (PostStatus.PENDING_PUBLISH.value, )) as c:
                row = await c.fetchone()
                if not row:
                    logger.info("No games available for publishing")
                    return
                app_id, discount_percent, init_price = row


            for attempt in range(1, retry_attempts + 1):
                response = steam.apps.get_app_details(app_id, country="RU")

                # Если превышен лимит обращений к steam API
                if response is None:
                    if attempt != retry_attempts:
                        logger.info(f"Steam API request limit reached. Waiting for {int(request_retry_period / 60)} minutes. Retry attempt: {attempt}")
                        await asyncio.sleep(request_retry_period)
                    else:
                        logger.error(f"Retry attempts for app_id={app_id} exceeded. Task will be delayed")
                        return
                    continue

                break

            if str(app_id) not in response:
                logger.error("The response with app_id=%s has no app_id attribute. "
                             "General response format might have changed", app_id)
                return

            if "data" not in response[str(app_id)] and response[str(app_id)]["success"] is True:
                logger.warning(f"The response with app_id=%s has no data attribute. "
                               f"app_id=%s may have wrong response format or is unavailable in Russia",
                               app_id, app_id)
                return

            game_title = response[str(app_id)]["data"]["name"]

            # Если нужно описание на русском, тогда надо подключать нейронку переводчика. steam_web_api не позволяет указать язык для запроса
            game_description_eng = response[str(app_id)]["data"]["short_description"]
            game_cover = response[str(app_id)]["data"]["header_image"]


            for attempt in range(1, retry_attempts + 1):
                screenshot_and_developers_response = steam.apps.get_app_details(app_id, country="RU", filters="screenshots,developers")

                if screenshot_and_developers_response is None:
                    if attempt != retry_attempts:
                        logger.info(f"Steam API request limit reached. Waiting for {int(request_retry_period / 60)} minutes. Retry attempt: {attempt}")
                        await asyncio.sleep(request_retry_period)
                    else:
                        logger.error(f"Retry attempts for app_id={app_id} exceeded. Task will be delayed")
                        return
                    continue

                break


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
            logger.info("Successfully published game with app_id=%s", app_id)
            await db.commit()

            # Пауза между постами от 45 мин до 2 часов
            post_period = rnd.randint(2700, 7200)
            await asyncio.sleep(post_period)

    