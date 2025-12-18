import aiosqlite

DB_PATH = "posts.db"

db: aiosqlite.Connection | None = None

async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)

    await db.execute("PRAGMA journal_mode=WAL;")

    await db.execute("""
    CREATE TABLE IF NOT EXISTS steam_apps_info (
        app_id INTEGER PRIMARY KEY,
        discount_percent INTEGER NOT NULL,
        init_price REAL NOT NULL,
        status INTEGER NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP NOT NULL
    )
    """)

    await db.execute("CREATE INDEX IF NOT EXISTS steam_apps_info_status_and_updated_at ON steam_apps_info(status, updated_at);")

    await db.commit()

async def close_db():
    await db.close()