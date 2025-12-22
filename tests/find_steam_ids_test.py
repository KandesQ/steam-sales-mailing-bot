import logging
from unittest.mock import Mock

import aiosqlite
import pytest
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
async def test_if_success():
    """
    В базе должна появится запись полученной инфы из ответа API
    со статусом PENDING_PUBLISH
    """
    # Arrange
    db = await setup_in_memory_db()


    with open("counter.txt", "r") as f:
        expected_id = int(f.read()) + 1


    expected_info_json = {str(expected_id):
                    {'success': True, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }
    expected_discount_percent = 30
    expected_init_price = 1500.0
    expected_status = usecases.PostStatus.PENDING_PUBLISH

    logger_mock = Mock(spec=logging.Logger)
    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == expected_id:
            return expected_info_json
        raise AssertionError(f"app_id={expected_id} was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 1, logger_mock)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 1
        
        row_info = info_rows[0]
        assert expected_id == row_info[0]
        assert expected_discount_percent == row_info[1]
        assert float(expected_init_price) == row_info[2]
        assert expected_status == usecases.PostStatus(row_info[3])
    
    await db.close()


@pytest.mark.asyncio
async def test_if_not_success():
    """
    В базу ничего не должно сохраняться
    """
    # Arrange
    db = await setup_in_memory_db()

    with open("counter.txt", "r") as f:
        expected_id = int(f.read()) + 1

    expected_info_json = {str(expected_id):
                    {'success': False, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }

    logger_mock = Mock(spec=logging.Logger)
    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == expected_id:
            return expected_info_json
        raise AssertionError(f"app_id={expected_id} was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 1, logger_mock)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 0
    
    await db.close()



@pytest.mark.asyncio
async def test_if_api_response_format_is_wrong():
    """
    Если API возвращает неправильный формат, юзкейс 
    должен пропустить обработку
    """

    db = await setup_in_memory_db()

    json_without_data_key = {'1': {'success': True}}
    json_without_id_key = {"Some": "key"}

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)

    steam_api_mock.apps.get_app_details.return_value = json_without_id_key
    await usecases.find_steam_ids(db, steam_api_mock, 2, logger_mock)

    steam_api_mock.apps.get_app_details.return_value = json_without_data_key
    await usecases.find_steam_ids(db, steam_api_mock, 2, logger_mock)

    await db.close()


@pytest.mark.asyncio
async def test_if_api_request_limit_is_exceeded():
    """
    Если превышен лимит запросов к API, то оно
    возвращает None. Код должен ожидать 6 минут
    """
    db = await setup_in_memory_db()

    none_response = None

    logger_mock = Mock(spec=logging.Logger)
    steam_api_mock = Mock(spec=Steam)

    steam_api_mock.apps.get_app_details.return_value = none_response
    await usecases.find_steam_ids(db, steam_api_mock, 2, logger_mock, 2, 2)

    await db.close()