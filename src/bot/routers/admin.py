import json
from functools import partial

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    KeyboardButtonRequestUsers,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram_dialog import Dialog, DialogManager, ShowMode, SubManager, Window
from aiogram_dialog.widgets.input import MessageInput
from aiogram_dialog.widgets.kbd import Back, Button, SwitchTo, ListGroup
from aiogram_dialog.widgets.text import Const, Format

from src.bot.routers.waiter import add_feedback_handler
from src.bot.waiter_repository import waiter_repository
from src.config import settings


class AdminStates(StatesGroup):
    menu = State("menu")
    manage_waiters = State("manage_waiters")
    add_waiter = State("add_waiter")
    list_waiters = State("list_waiters")
    add_feedback = State("add_feedback")
    summary = State("summary")


async def report(callback: CallbackQuery, button: Button, manager: DialogManager):
    from src.bot.daily_report import send_report

    telegram_id = callback.from_user.id
    error_message = await send_report(telegram_id)
    if error_message:
        await callback.answer(error_message)
    await manager.switch_to(AdminStates.menu, show_mode=ShowMode.DELETE_AND_SEND)


async def summary(callback: CallbackQuery, button: Button, manager: DialogManager):
    from src.bot.daily_report import send_summary

    telegram_id = callback.from_user.id
    error_message = await send_summary(telegram_id)
    if error_message:
        await callback.answer(error_message)
    await manager.switch_to(AdminStates.menu, show_mode=ShowMode.DELETE_AND_SEND)


admin_menu_ww = Window(
    Const(f'<a href="{settings.fika_channel_link}">Канал с отзывами</a>\n\n<b>Меню администратора 🛠</b>'),
    SwitchTo(Const("Управление официантами"), id="manage_waiters", state=AdminStates.manage_waiters),
    SwitchTo(Const("Добавить обратную связь"), id="add_feedback", state=AdminStates.add_feedback),
    Button(Const("Сводка за 2 недели 📈"), id="summary", on_click=summary),
    Button(Const("Отчёт 📊"), id="report", on_click=report),
    state=AdminStates.menu,
    parse_mode="HTML",
)


async def switch_to_add_waiter(callback: CallbackQuery, widget: Button, manager: DialogManager):
    await callback.message.answer(
        "☕️",
        reply_markup=ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(
                        text="Выбрать официантов",
                        request_users=KeyboardButtonRequestUsers(
                            request_id=108,
                            user_is_bot=False,
                            request_name=True,
                            request_username=True,
                            max_quantity=10,
                        ),
                    ),
                ]
            ],
        ),
    )
    await manager.switch_to(AdminStates.add_waiter)


manage_waiters_ww = Window(
    Const("Управление официантами"),
    Button(Const("Добавить официанта"), id="add_waiter", on_click=switch_to_add_waiter),
    SwitchTo(Const("Список официантов"), id="list_waiters", state=AdminStates.list_waiters),
    Back(Const("Назад")),
    state=AdminStates.manage_waiters,
)


async def add_waiter(message: Message, widget: MessageInput, manager: DialogManager):
    if not message.users_shared:
        await message.answer("Пожалуйста, отправьте контакты")
        return

    users = message.users_shared.users
    users_texts = []
    for user in users:
        if user.username:
            users_texts.append(
                f'- <a href="tg://user?id={user.user_id}">{user.first_name} {user.last_name} @{user.username}</a>'
            )
        else:
            users_texts.append(f'- <a href="tg://user?id={user.user_id}">{user.first_name} {user.last_name}</a>')
    text = "\n".join(users_texts)
    for user in users:
        waiter_repository.add_waiter(user.user_id, user.model_dump_json(exclude_none=True))
    await message.answer(f"Добавленые официанты:\n{text}", reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    await manager.switch_to(AdminStates.manage_waiters)


add_waiter_ww = Window(
    Const("Пожалуйста, отправьте контакт официанта"),
    MessageInput(add_waiter),
    SwitchTo(Const("Назад"), state=AdminStates.manage_waiters, id="manage_waiters"),
    state=AdminStates.add_waiter,
)


def get_showname(user: dict) -> str:
    """
    FirstName [LastName] [@Username]
    """
    parts = [user.get("first_name")]
    if user.get("last_name"):
        parts.append(user["last_name"])
    if user.get("username"):
        parts.append("@" + user["username"])
    return " ".join(parts)


async def list_waiters_getter(**kwargs):
    waiters_raw = waiter_repository.get_waiters()
    waiters = []
    for waiter_id, json_string, deleted in waiters_raw:
        item = json.loads(json_string)
        item["id"] = waiter_id
        item["deleted"] = deleted
        item["show_name"] = get_showname(item)
        waiters.append(item)

    return {"waiters": waiters}


async def delete_waiter_handler(callback: CallbackQuery, button: Button, manager: SubManager):
    item_id = manager.item_id
    waiter_repository.remove_waiter(int(item_id))


list_waiters_ww = Window(
    Const("Список официантов"),
    ListGroup(
        Button(
            Format("{item[show_name]}"),
            id="name",
        ),
        Button(Const("❌"), id="delete", on_click=delete_waiter_handler),  # noqa
        id="waiters_list",
        item_id_getter=lambda item: item["id"],
        items="waiters",
    ),
    SwitchTo(Const("Назад"), state=AdminStates.manage_waiters, id="manage_waiters"),
    getter=list_waiters_getter,
    state=AdminStates.list_waiters,
)

feedback_ww = Window(
    Const("Введите общую обратную связь от посетителей"),
    MessageInput(partial(add_feedback_handler, mode="admin")),
    state=AdminStates.add_feedback,
)


router = Dialog(admin_menu_ww, manage_waiters_ww, add_waiter_ww, list_waiters_ww, feedback_ww, name="admin")
