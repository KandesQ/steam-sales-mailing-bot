


import datetime
import logging
from unittest.mock import Mock
from steam_web_api import Steam


import aiosqlite
import pytest

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
async def test_if_init_price_has_changed():
    """
    Базовая цена (без скидки) на игру изменилась
    """

    # Arrange
    db = await setup_in_memory_db()

    expected_id = 1
    old_init_price = 2500.0
    old_discount_percent = 0
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")

    await db.execute(
    """
    INSERT INTO steam_apps_info (
        app_id,
        discount_percent,
        init_price,
        status,
        updated_at
    ) VALUES (?, ?, ?, ?, ?)
    """,
    (
        expected_id, old_discount_percent,
        old_init_price, usecases.PostStatus.PUBLISHED.value,
        old_date
    )
    )
    await db.commit()

    new_init_price = 16994.0
    expected_info_json = {'1': 
                {'success': True, 'data': 
                    {'price_overview': 
                        {'currency': 'RUB', 'initial': new_init_price, 'final': new_init_price, 'discount_percent': old_discount_percent, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                    }
                }
            }

    logger_mock = Mock(spec=logging.Logger)
    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect


    # Act
    await usecases.update_steam_game_price_and_discount(db, steam_mock, 1, logger_mock)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 1
        row_info = info_rows[0]

        assert expected_id == row_info[0]
        assert old_discount_percent == row_info[1]

        # Делю на сто потому что с апи возвращается в копейках, а в базе цену храню в рублях
        assert old_init_price / 100 != row_info[2]
        assert usecases.PostStatus.PENDING_PUBLISH.value == usecases.PostStatus(row_info[3]).value
        assert row_info[4] != old_date

    await db.close()



@pytest.mark.asyncio
async def test_if_discount_has_changed():
    """
    Скидка на игру изменилась
    """

    # Arrange
    db = await setup_in_memory_db()

    expected_id = 1
    old_init_price = 2500.0
    old_discount_percent = 0
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
    """
    INSERT INTO steam_apps_info (
        app_id,
        discount_percent,
        init_price,
        status,
        updated_at
    ) VALUES (?, ?, ?, ?, ?)
    """,
    (
        expected_id, old_discount_percent,
        old_init_price, usecases.PostStatus.PUBLISHED.value, 
        old_date
    )
    )
    await db.commit()

    new_discount_percent = 20
    expected_info_json = {'1': 
                {'success': True, 'data': 
                    {'price_overview': 
                        {'currency': 'RUB', 'initial': old_init_price, 'final': old_init_price, 'discount_percent': new_discount_percent, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                    }
                }
            }

    logger_mock = Mock(spec=logging.Logger)
    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect


    # Act
    await usecases.update_steam_game_price_and_discount(db, steam_mock, 1, logger_mock)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 1
        info_row = info_rows[0]

        assert expected_id == info_row[0]
        assert old_discount_percent != info_row[1]

        # Делю на сто потому что с апи возвращается в копейках, а в базе цену храню в рублях
        assert old_init_price / 100 == info_row[2]
        assert usecases.PostStatus.PENDING_PUBLISH.value == usecases.PostStatus(info_row[3]).value
        assert info_row[4] != old_date

    await db.close()


@pytest.mark.asyncio
async def test_if_game_has_become_unavailable_in_Russia():
    """
    Игра стала недоступной в России
    """

    # Arrange
    db = await setup_in_memory_db()

    id = 1
    init_price = 2500.0
    discount_percent = 0
    old_status = usecases.PostStatus.PUBLISHED.value
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
    """
    INSERT INTO steam_apps_info (
        app_id,
        discount_percent,
        init_price,
        status,
        updated_at
    ) VALUES (?, ?, ?, ?, ?)
    """,
    (
        id, discount_percent,
        init_price, old_status,
        old_date
    )
    )
    await db.commit()

    expected_info_json = {'1': 
                {'success': False, 'data': 
                    {'price_overview': 
                        {'currency': 'RUB', 'initial': 0, 'final': 0, 'discount_percent': 0, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                    }
                }
            }

    logger_mock = Mock(spec=logging.Logger)
    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.update_steam_game_price_and_discount(db, steam_mock, 1, logger_mock)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 1
        info_row = info_rows[0]

        # проверяю что ничего не поменялось
        assert info_row[0] == id
        assert info_row[1] == discount_percent
        assert info_row[2] == init_price
        assert info_row[3] == old_status
        assert info_row[4] == old_date

    await db.close()



@pytest.mark.asyncio
async def test_if_api_response_format_is_wrong():
    """
    Если API возвращает неправильный формат, юзкейс 
    должен пропустить обработку
    """

    db = await setup_in_memory_db()
    id = 1
    init_price = 2500.0
    discount_percent = 0
    old_status = usecases.PostStatus.PUBLISHED.value
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
    """
    INSERT INTO steam_apps_info (
        app_id,
        discount_percent,
        init_price,
        status,
        updated_at
    ) VALUES (?, ?, ?, ?, ?)
    """,
    (
        id, discount_percent,
        init_price, old_status,
        old_date
    )
    )
    await db.commit()


    json_without_data_key = {str(id): {'success': True}}
    json_without_id_key = {"Some": "key"}

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)

    steam_api_mock.apps.get_app_details.return_value = json_without_id_key
    await usecases.update_steam_game_price_and_discount(db, steam_api_mock, 2, logger_mock)

    steam_api_mock.apps.get_app_details.return_value = json_without_data_key
    await usecases.update_steam_game_price_and_discount(db, steam_api_mock, 2, logger_mock)

    await db.close()


@pytest.mark.asyncio
async def test_if_api_request_limit_is_exceeded():
    """
    Если превышен лимит запросов к API, то оно
    возвращает None. Код должен ожидать 6 минут
    """

    db = await setup_in_memory_db()
    id = 1
    init_price = 2500.0
    discount_percent = 0
    old_status = usecases.PostStatus.PUBLISHED.value
    old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=31)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
    """
    INSERT INTO steam_apps_info (
        app_id,
        discount_percent,
        init_price,
        status,
        updated_at
    ) VALUES (?, ?, ?, ?, ?)
    """,
    (
        id, discount_percent,
        init_price, old_status,
        old_date
    )
    )
    await db.commit()

    none_response = None

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)

    steam_api_mock.apps.get_app_details.return_value = none_response
    await usecases.update_steam_game_price_and_discount(db, steam_api_mock, 2, logger_mock,2, 2)

    await db.close()