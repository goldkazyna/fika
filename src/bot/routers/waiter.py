"""
5. Обратная связь от сотрудников
- Функционал для персонала:
   Сотрудники в конце смены отправляют в бот общую обратную связь от посетителей через текстовые сообщения.
- Анализ обратной связи:
   Бот обрабатывает данные и формирует отдельный отчет в Telegram с указанием роли сотрудника.
"""

import json
from io import BytesIO

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import SwitchTo
from aiogram_dialog.widgets.text import Const

from aiogram_dialog.widgets.input import MessageInput

from src.bot.app import bot
from src.bot.logging_ import logger
from src.bot.openai_repository import openai_repository
from src.bot.waiter_repository import waiter_repository
from src.config import settings


class WaiterStates(StatesGroup):
    menu = State("menu")
    add_feedback = State("add_feedback")


menu_ww = Window(
    Const("<b>Меню сотрудника 🍽</b>"),
    SwitchTo(Const("Добавить обратную связь"), id="new_feedback", state=WaiterStates.add_feedback),
    state=WaiterStates.menu,
    parse_mode="HTML",
)


def get_user_role(telegram_id: int) -> str:
    """Получает роль пользователя из базы в родительном падеже"""

    # Склонения ролей (Именительный -> Родительный падеж)
    ROLE_GENITIVE = {
        "Управляющий": "Управляющего",
        "Соучредитель": "Соучредителя",
        "Учредитель": "Учредителя",
        "Шеф-концепт": "Шеф-концепта",
        "Шеф-бара": "Шеф-бара",
        "Шеф-пекарь-кондитер": "Шеф-пекаря-кондитера",
        "Официант": "Официанта",
        "Кассир": "Кассира",
        "Хостесс": "Хостесс",
        "Су-шеф": "Су-шефа",
        "Менеджер": "Менеджера",
        "Закупщик": "Закупщика",
        "Администратор": "Администратора",
        "Сотрудник": "Сотрудника",
    }

    waiter = waiter_repository.get_waiter(telegram_id)
    if waiter:
        role = waiter[3] if len(waiter) > 3 else None
        if role:
            return ROLE_GENITIVE.get(role, role)

    # Проверяем, админ ли это
    if telegram_id in settings.admins:
        return "Администратора"

    return "Сотрудника"


async def add_feedback_handler(
    message: Message,
    widget: MessageInput,
    manager: DialogManager,
):
    from src.bot.routers.admin import AdminStates

    # Получаем роль пользователя
    user_role = get_user_role(message.from_user.id)

    logger.info(f"Feedback from {user_role}: {message.text or message.caption or message.voice}")

    as_dict = message.model_dump(exclude_none=True)

    transcription = None
    if message.voice:
        try:
            file = await bot.get_file(message.voice.file_id)
            buffer = BytesIO()
            await bot.download_file(file_path=file.file_path, destination=buffer)
            extension = file.file_path.split(".")[1]
            buffer.name = f"file.{extension}"
            transcription = await openai_repository.transript(buffer)
            as_dict["transcription"] = transcription
            logger.info(f"Transcripted: {transcription}")
        except Exception as e:
            logger.error(f"Error while transcription voice message {e}")

    waiter_repository.add_report(waiter_id=message.from_user.id, message=json.dumps(as_dict))

    # Отправляем в канал с указанием роли
    await bot.send_message(
        chat_id=settings.fika_channel_id,
        text=f"<b>📝 Обратная связь от {user_role}:</b>",
        disable_notification=True,
        parse_mode="HTML",
    )
    forwarded = await message.forward(chat_id=settings.fika_channel_id)

    if transcription:
        await forwarded.reply(
            text=f"<b>🎤 Транскрипция:</b>\n<blockquote>{transcription}</blockquote>",
            disable_notification=True,
            parse_mode="HTML",
        )
        await message.reply(
            text=f"Спасибо за обратную связь!\n\nТранскрипция:\n<blockquote>{transcription}</blockquote>",
            parse_mode="HTML",
        )
    else:
        # Добавляем разделитель после сообщения без голоса
        await message.reply("Спасибо за обратную связь!")

    # Возвращаемся в меню
    # Проверяем откуда пришли - из админки или из меню сотрудника
    if message.from_user.id in settings.admins:
        await manager.switch_to(AdminStates.menu)
    else:
        await manager.switch_to(WaiterStates.menu)


feedback_ww = Window(
    Const("Введите общую обратную связь от посетителей"),
    MessageInput(add_feedback_handler),
    state=WaiterStates.add_feedback,
)


router = Dialog(menu_ww, feedback_ww, name="waiter")
