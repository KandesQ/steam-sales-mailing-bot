import logging

import aiosqlite
import pytest

from aiogram import Bot
from unittest.mock import Mock
from steam_web_api import Steam

import usecases


async def setup_in_memory_db():
    db = await aiosqlite.connect(":memory:")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS steam_apps_info (
        app_id INTEGER PRIMARY KEY,
        discount_percent INTEGER NOT NULL,
        init_price REAL NOT NULL,
        status INTEGER NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)
    await db.commit()

    return db




@pytest.mark.asyncio
async def test_if_api_response_format_is_wrong():
    """
    Если API возвращает неправильный формат, юзкейс 
    должен пропустить обработку
    """

    db = await setup_in_memory_db()
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
            1, 20,
            2000, usecases.PostStatus.PENDING_PUBLISH.value
        )
    )
    await db.commit()

    json_without_data_key = {'1': {'success': True}}
    json_without_id_key = {"Some": "key"}

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)
    bot_mock = Mock(spec=Bot)


    steam_api_mock.apps.get_app_details.return_value = json_without_id_key
    await usecases.publish_steam_post(db, steam_api_mock, bot_mock, -1, logger_mock)

    steam_api_mock.apps.get_app_details.return_value = json_without_data_key
    await usecases.publish_steam_post(db, steam_api_mock, bot_mock, -1, logger_mock)

    await db.close()



@pytest.mark.asyncio
async def test_if_api_request_limit_is_exceeded():
    """
    Если превышен лимит запросов к API, то оно
    возвращает None. Код должен ожидать 6 минут
    """
    db = await setup_in_memory_db()
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
            1, 20,
            2000, usecases.PostStatus.PENDING_PUBLISH.value
        )
    )
    await db.commit()
    
    none_response = None

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)
    bot_mock = Mock(spec=Bot)

    steam_api_mock.apps.get_app_details.return_value = none_response
    await usecases.publish_steam_post(db, steam_api_mock, bot_mock, -1, logger_mock, 2, 1)

    await db.close()