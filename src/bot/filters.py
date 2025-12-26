from typing import Any, Literal

from aiogram.filters import Filter
from aiogram.types import User, TelegramObject

from src.bot.waiter_repository import waiter_repository
from src.config import settings


async def get_statuses(telegram_id: int) -> list[str]:
    statuses = []
    if telegram_id in settings.admins:
        statuses.append("admin")

    waiter = waiter_repository.get_waiter(telegram_id)
    if waiter:
        statuses.append("waiter")
        # Добавляем роль если есть
        role = waiter[3] if len(waiter) > 3 else None
        if role:
            statuses.append("staff")

    return statuses


class StatusFilter(Filter):
    _status: Literal["admin", "waiter", "staff"] | None

    def __init__(self, status: Literal["admin", "waiter", "staff"] | None = None):
        self._status = status

    async def __call__(self, event: TelegramObject, event_from_user: User) -> bool | dict[str, Any]:
        statuses = await get_statuses(event_from_user.id)
        if self._status is None:
            return {"status": statuses[0] if statuses else None}
        else:
            return self._status in statuses
