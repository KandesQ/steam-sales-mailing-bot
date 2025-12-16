import aiosqlite

DB_PATH = "posts.db"

db: aiosqlite.Connection | None = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)

    await db.execute("PRAGMA journal_mode=WAL;")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_name TEXT NOT NULL,
        game_title TEXT NOT NULL,
        game_description TEXT,
        price REAL NOT NULL,
        discount INTEGER,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL,
        store_link TEXT NOT NULL
    );
    """)

    await db.execute("CREATE INDEX IF NOT EXISTS idx_posts_status_and_updated_at ON posts(status, updated_at);")

    await db.commit()

async def close_db():
    await db.close()