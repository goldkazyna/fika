import os
import sqlite3

db_path = os.getenv("DATABASE_PATH", "./data/sqlite.db")

os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# create staff table if not exists
cur.execute(
    "CREATE TABLE IF NOT EXISTS waiters (telegram_id INTEGER PRIMARY KEY, object TEXT, role TEXT, deleted BOOLEAN DEFAULT false)"
)

# add role column if not exists (for existing databases)
try:
    cur.execute("ALTER TABLE waiters ADD COLUMN role TEXT")
except sqlite3.OperationalError:
    pass  # column already exists

# create staff reports table if not exists
cur.execute(
    """CREATE TABLE IF NOT EXISTS waiter_reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        waiter_id INTEGER,
        date DATETIME,
        message TEXT
    )"""
)
conn.commit()

# Available roles
ROLES = [
    "Управляющий",
    "Соучредитель",
    "Учредитель",
    "Шеф-концепт",
    "Шеф-бара",
    "Шеф-пекарь-кондитер",
    "Официант",
    "Кассир",
    "Хостесс",
    "Су-шеф",
]
