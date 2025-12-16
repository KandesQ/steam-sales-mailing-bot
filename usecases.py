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



class PostStatus(Enum):
    PENDING_PUBLISH = "PENDING_PUBLISH"
    PUBLISHED = "PUBLISHED"

@dataclass
class Post:
    id: int
    store_name: str
    game_title: str
    game_description: str
    price: float
    discounted_price: float
    discount: int
    updated_at: datetime # Создание засчитывается за обновление
    status: PostStatus
    store_link: str



# TODO: реализовать
# TODO: тесты
async def parse_steam_games(db: aiosqlite.Connection, logger: logging.Logger, steam_api_key: str):
    # TODO: Send request to api
    # TODO: Create Post model and save to db
    # При обновлении старой (триггер обновления - цена) или сохранении сущности в базе, статус - PENDING_PUBLISH
    # и изменяю updated_at
    logger.info("Requesting for sale games from Steam...")



async def clean_old_posts(db: aiosqlite.Connection, logger: logging.Logger):
    delete_query = """
    DELETE FROM posts
    WHERE status = ?
    AND updated_at <= datetime('now', '-3 months')
    """

    # TODO: добавить лимит на очистку?
    logger.info("Start cleaning old posts...")
    cursor = await db.execute(delete_query, (PostStatus.PUBLISHED.value, ))
    await db.commit()

    if cursor.rowcount != 0:
        logger.info(f"{cursor.rowcount} old posts were cleaned")
    else:
        logger.info("No old posts were found")



async def publish_posts(db: aiosqlite.Connection, bot: Bot, logger: logging.Logger, chat_id: int):
    select_query = """
        SELECT * FROM posts
        WHERE status = ?
    """

    update_query = """
    UPDATE posts
    SET status = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """

    rnd = Random()

    async with db.execute(select_query, (PostStatus.PENDING_PUBLISH.value, )) as cursor:
        rows = await cursor.fetchall() # TODO: сейчас выгружаются сразу в память. Сделать генератором?

        if not rows:
            logger.info("No pending posts were found")
        else:
            logger.info(f"Found {len(rows)} pending posts. Start publishing to group...")

        for row in rows:

            post = Post(
                id=int(row[0]),
                store_name=row[1],
                game_title=row[2],
                game_description=row[3],
                price=float(row[4]),
                discounted_price=(100 - int(row[5])) / 100 * float(row[4]),
                discount=int(row[5]),
                updated_at=datetime.fromisoformat(row[6]),
                status=PostStatus(row[7]),
                store_link=row[8],
            )

            text_message = (
                f"<h2>{html.escape(post.game_title)}</h2>"
                f"<br><br>"
                f"{html.escape(post.game_description)}"
                f"<br>"
                f"<i>Store:</i> {html.escape(post.store_name)}"
                f"<br>"
                f"<i>Price</i>: <s>{post.price}</s> -{post.discount}% → {post.discounted_price}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"Открыть в {post.store_name}",
                        url=post.store_link
                    )
                ]
            ])

            try:
                logger.info(f"Publishing post {post.id}...")
                # TODO: добавить лимит отправок?
                await bot.send_message(
                    chat_id=chat_id,
                    text=text_message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to send post {post.id}", exc_info=e)
                continue

            await db.execute(update_query, (PostStatus.PUBLISHED.value, post.id))
            logger.info(f"Post {post.id} is published")
            await db.commit()

            await asyncio.sleep(rnd.randint(2, 10))  # чтобы не заспамить группу
    