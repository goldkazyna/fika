import datetime
import json


from src.bot.db import conn, cur
from src.bot.logging_ import logger


class WaiterRepository:
    def get_waiter(self, telegram_id: int) -> tuple | None:
        cur.execute("SELECT * FROM waiters WHERE telegram_id = ?", (telegram_id,))
        if not (row := cur.fetchone()):
            return None
        # check if waiter is deleted
        if row[2]:
            return None
        return row

    def get_waiters(self) -> list[tuple]:
        cur.execute("SELECT * FROM waiters WHERE deleted = false")
        return cur.fetchall()

    def add_waiter(self, telegram_id: int, telegram_object: str) -> None:
        # Check if waiter exists
        cur.execute("SELECT * FROM waiters WHERE telegram_id = ?", (telegram_id,))
        if cur.fetchone():
            # Update the existing waiter and set deleted to false
            cur.execute(
                "UPDATE waiters SET object = ?, deleted = false WHERE telegram_id = ?",
                (telegram_object, telegram_id),
            )
        else:
            # Insert a new waiter
            cur.execute(
                "INSERT INTO waiters (telegram_id, object) VALUES (?, ?)",
                (telegram_id, telegram_object),
            )
        conn.commit()

    def remove_waiter(self, telegram_id: int) -> None:
        cur.execute("UPDATE waiters SET deleted = true WHERE telegram_id = ?", (telegram_id,))
        conn.commit()

    def add_report(self, waiter_id: int, message: str) -> None:
        date = datetime.datetime.now(datetime.UTC)
        cur.execute(
            "INSERT INTO waiter_reports (waiter_id, date, message) VALUES (?, ?, ?)",
            (waiter_id, date, message),
        )
        conn.commit()

    def update_report(self, report_id: int, message: str) -> None:
        cur.execute(
            "UPDATE waiter_reports SET message = ? WHERE report_id = ?",
            (message, report_id),
        )
        conn.commit()

    def get_reports(self, date_from: datetime.date) -> list[tuple]:
        cur.execute(
            "SELECT * FROM waiter_reports WHERE DATE(date) >= ?",
            (date_from,),
        )
        return cur.fetchall()

    def get_not_yet_transcripted(self) -> list[tuple]:
        cur.execute(
            "SELECT * FROM waiter_reports WHERE json_extract(message, '$.voice') IS NOT NULL AND json_extract(message, '$.transcription') IS NULL"
        )
        return cur.fetchall()

    def to_toweco_format(self, report: tuple) -> dict:
        report_id, waiter_id, date, message = report
        message_object = json.loads(message)

        if "text" in message_object:
            review_text = message_object["text"]
        elif "caption" in message_object:
            review_text = message_object["caption"]
        elif "transcription" in message_object:
            review_text = f"Транскрипция: {message_object['transcription']}"
        else:
            logger.warning(f"Bad message object: {message_object}")
            review_text = "Нет текста"

        author = " ".join(
            filter(
                None,
                (
                    message_object["from_user"].get("first_name"),
                    message_object["from_user"].get("last_name"),
                    "@" + username if (username := message_object["from_user"].get("username")) else None,
                ),
            )
        )

        return {
            "review": review_text,
            "provider": "Отчёт от официанта",
            "author": author,
            "publishedAt": date,
        }


waiter_repository: WaiterRepository = WaiterRepository()
