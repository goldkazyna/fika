"""
5. Обратная связь от официантов
• Функционал для персонала:
   Официанты в конце смены отправляют в бот общую обратную связь от посетителей через текстовые сообщения.
• Анализ обратной связи:
   Бот обрабатывает данные и формирует отдельный отчет в Telegram с указанием, что информация поступила от официантов.
"""

import json
from functools import partial
from io import BytesIO
from typing import Literal

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
    Const("<b>Меню официанта 🍽</b>"),
    SwitchTo(Const("Добавить обратную связь"), id="new_feedback", state=WaiterStates.add_feedback),
    state=WaiterStates.menu,
    parse_mode="HTML",
)


async def add_feedback_handler(
    message: Message,
    widget: MessageInput,
    manager: DialogManager,
    /,
    mode: Literal["admin", "waiter"],
):
    from src.bot.routers.admin import AdminStates

    logger.info(f"Feedback from {mode}: {message.text or message.caption or message.voice}")

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
    await bot.send_message(
        chat_id=settings.fika_channel_id,
        text="<b>Обратная связь от официанта:</b>" if mode == "waiter" else "<b>Обратная связь от администратора:</b>",
        disable_notification=True,
        parse_mode="HTML",
    )
    forwarded = await message.forward(chat_id=settings.fika_channel_id)
    if transcription:
        await forwarded.reply(
            text=f"<b>Транскрипция:</b>\n<blockquote>{transcription}</blockquote>",
            disable_notification=True,
            parse_mode="HTML",
        )
        await message.reply(
            text=f"Спасибо за обратную связь!\n\nТранскрипция:\n<blockquote>{transcription}</blockquote>",
            parse_mode="HTML",
        )
    else:
        await message.reply("Спасибо за обратную связь!")
    await manager.switch_to(WaiterStates.menu if mode == "waiter" else AdminStates.menu)


feedback_ww = Window(
    Const("Введите общую обратную связь от посетителей"),
    MessageInput(partial(add_feedback_handler, mode="waiter")),
    state=WaiterStates.add_feedback,
)


router = Dialog(menu_ww, feedback_ww, name="waiter")
