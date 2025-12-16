


from datetime import datetime, timedelta, timezone
import aiosqlite
import pytest

import usecases
from usecases import Post, PostStatus

# TODO: заменить на библиотекчный мок?
class FakeLogger:
    def info(self, msg): pass
    def error(self, msg, exc_info=None): pass

# TODO: заменить на библиотекчный мок?
class FakeBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.sent_messages.append({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
        })




@pytest.mark.asyncio
async def test_clean_old_posts():
    async with aiosqlite.connect(":memory:") as db:
        # Arrange
        await db.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )                 
        """)    

        now = datetime.now(timezone.utc)

        test_posts = [
            # Старые PUBLISHED должны удалиться
            (1, PostStatus.PUBLISHED.value, (now - timedelta(days=120)).isoformat()),
            (2, PostStatus.PUBLISHED.value, (now - timedelta(days=240)).isoformat()),

            # Новые PUBLISHED должны остаться
            (3, PostStatus.PUBLISHED.value, (now - timedelta(days=10)).isoformat()),


            # PENDING_PUBLISH должны остаться
            (4, PostStatus.PENDING_PUBLISH.value, (now - timedelta(days=3)).isoformat()),
            (5, PostStatus.PENDING_PUBLISH.value, (now - timedelta(days=10)).isoformat()),
            (6, PostStatus.PENDING_PUBLISH.value, (now - timedelta(days=400)).isoformat()),
        ]

        await db.executemany("INSERT INTO posts (id, status, updated_at) VALUES (?, ?, ?)", test_posts)
        await db.commit()

        expected_ids = [3, 4, 5, 6]

        # Act
        await usecases.clean_old_posts(db, FakeLogger())
        
        # Assert
        async with db.execute("SELECT id FROM posts ORDER BY id") as cursor:
            rows = await cursor.fetchall()

            actual_ids = [int(row[0]) for row in rows]

        
        assert expected_ids == actual_ids
            


@pytest.mark.asyncio
async def test_publish_posts():
    async with aiosqlite.connect(":memory:") as db:
        # Arrange
        await db.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL,
            game_title TEXT NOT NULL,
            game_description TEXT,
            price REAL NOT NULL,
            discount INTEGER,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status TEXT NOT NULL,
            store_link TEXT NOT NULL
        )                 
        """)    

        now = datetime.now(timezone.utc)
        old_time1 = (now - timedelta(days=1)).isoformat()
        old_time2 = (now - timedelta(days=3)).isoformat()

        test_posts = [
            (1, "Store1", "Title1", "Desc1", 312, 200, old_time1,  PostStatus.PUBLISHED.value, "storelink1"),
            (2, "Store2", "Title2", "Desc2", 1000, 910, old_time2,  PostStatus.PENDING_PUBLISH.value, "storelink2"),
        ]

        await db.executemany("""
            INSERT INTO posts (
                id, store_name, game_title,
                game_description, price, discount,
                updated_at, status, store_link
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, test_posts)
    
        # Act
        fake_bot = FakeBot()

        await usecases.publish_posts(db=db, bot=fake_bot, logger=FakeLogger(), chat_id=-123)

        # Assert
        assert len(fake_bot.sent_messages) == 1

        async with db.execute("SELECT status, updated_at FROM posts ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            actual_statuses = [PostStatus(row[0]) for row in rows]
            updated_times = [row[1] for row in rows]
            assert all(status == PostStatus.PUBLISHED for status in actual_statuses)

            assert updated_times[0] == old_time1
            assert updated_times[1] != old_time2
