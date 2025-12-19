import pytest
import aiosqlite

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
async def test_if_database_is_empty():
    """
    Точкой старта поиска должна быть единица
    """
    # Arrange
    db = await setup_in_memory_db() # пустая база
    expected_info_json = {'1': 
                    {'success': True, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }
    expected_id = 1
    expected_discount_percent = 30
    expected_init_price = 1500.0
    expected_status = usecases.PostStatus.PENDING_PUBLISH.value

    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 2)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 1
        row_info = info_rows[0]

        assert expected_id == row_info[0]
        assert expected_discount_percent == row_info[1]
        assert float(expected_init_price) == row_info[2]
        assert expected_status == usecases.PostStatus(row_info[3]).value
    
    await db.close()


@pytest.mark.asyncio
async def test_if_database_is_not_empty():
    """
    Точкой старта поиска должен быть максимальный айдишник в базе
    """
    # Arrange
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
            4, 20,
            2000, usecases.PostStatus.PUBLISHED.value
        )
    )
    await db.commit()

    expected_info_json = {'5': 
                    {'success': True, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }
    expected_id = 5
    expected_discount_percent = 30
    expected_init_price = 1500.0
    expected_status = usecases.PostStatus.PENDING_PUBLISH

    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 5:
            return expected_info_json
        raise AssertionError("app_id=5 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 2)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 2
        row_info = info_rows[1]

        assert expected_id == row_info[0]
        assert expected_discount_percent == row_info[1]
        assert float(expected_init_price) == row_info[2]
        assert expected_status == usecases.PostStatus(row_info[3])
    
    await db.close()


@pytest.mark.asyncio
async def test_if_success():
    """
    В базе должна появится запись полученной инфы из ответа API
    со статусом PENDING_PUBLISH
    """
    # Arrange
    db = await setup_in_memory_db()

    expected_info_json = {'1': 
                    {'success': True, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }
    expected_id = 1
    expected_discount_percent = 30
    expected_init_price = 1500.0
    expected_status = usecases.PostStatus.PENDING_PUBLISH

    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 2)

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

    expected_info_json = {'1': 
                    {'success': False, 'data': 
                        {'price_overview': 
                            {'currency': 'RUB', 'initial': 150000, 'final': 105000, 'discount_percent': 30, 'initial_formatted': '1500 руб.', 'final_formatted': '1050 руб.'}
                        }
                    }
                }

    steam_mock = Mock(spec=Steam)
    def side_effect(app_id, country, filters):
        if app_id == 1:
            return expected_info_json
        raise AssertionError("app_id=1 was not requested")

    steam_mock.apps.get_app_details.side_effect = side_effect

    # Act
    await usecases.find_steam_ids(db, steam_mock, 2)

    # Assert
    async with db.execute("SELECT * FROM steam_apps_info") as c:
        info_rows = await c.fetchall()
        assert len(info_rows) == 0
    
    await db.close()