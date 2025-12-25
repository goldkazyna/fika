import os
import sqlite3

db_path = os.getenv("DATABASE_PATH", "./data/sqlite.db")

os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# create waiters table if not exists
cur.execute(
    "CREATE TABLE IF NOT EXISTS waiters (telegram_id INTEGER PRIMARY KEY, object TEXT, deleted BOOLEAN DEFAULT false)"
)
# create waiters' report table if not exists
cur.execute(
    """CREATE TABLE IF NOT EXISTS waiter_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        waiter_id INTEGER,
        date DATETIME,
        message TEXT
    )"""
)
conn.commit()
