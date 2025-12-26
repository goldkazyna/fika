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
from aiogram_dialog.widgets.kbd import Back, Button, SwitchTo, Select, Column
from aiogram_dialog.widgets.text import Const, Format

from src.bot.routers.waiter import add_feedback_handler
from src.bot.waiter_repository import waiter_repository
from src.bot.db import ROLES
from src.config import settings


class AdminStates(StatesGroup):
    menu = State("menu")
    manage_staff = State("manage_staff")
    add_staff = State("add_staff")
    select_role = State("select_role")
    list_staff = State("list_staff")
    staff_actions = State("staff_actions")  # новое
    edit_staff_role = State("edit_staff_role")
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
    SwitchTo(Const("Управление сотрудниками"), id="manage_staff", state=AdminStates.manage_staff),
    SwitchTo(Const("Добавить обратную связь"), id="add_feedback", state=AdminStates.add_feedback),
    Button(Const("Сводка за 2 недели 📈"), id="summary", on_click=summary),
    Button(Const("Отчёт 📊"), id="report", on_click=report),
    state=AdminStates.menu,
    parse_mode="HTML",
)


async def switch_to_add_staff(callback: CallbackQuery, widget: Button, manager: DialogManager):
    await callback.message.answer(
        "👤",
        reply_markup=ReplyKeyboardMarkup(
            resize_keyboard=True,
            one_time_keyboard=True,
            keyboard=[
                [
                    KeyboardButton(
                        text="Выбрать сотрудника",
                        request_users=KeyboardButtonRequestUsers(
                            request_id=108,
                            user_is_bot=False,
                            request_name=True,
                            request_username=True,
                            max_quantity=1,
                        ),
                    ),
                ]
            ],
        ),
    )
    await manager.switch_to(AdminStates.add_staff)


manage_staff_ww = Window(
    Const("<b>👥 Управление сотрудниками</b>"),
    Button(Const("➕ Добавить сотрудника"), id="add_staff", on_click=switch_to_add_staff),
    SwitchTo(Const("📋 Список сотрудников"), id="list_staff", state=AdminStates.list_staff),
    Back(Const("◀️ Назад")),
    state=AdminStates.manage_staff,
    parse_mode="HTML",
)


async def add_staff_handler(message: Message, widget: MessageInput, manager: DialogManager):
    if not message.users_shared:
        await message.answer("Пожалуйста, отправьте контакт", reply_markup=ReplyKeyboardRemove())
        return

    users = message.users_shared.users
    if not users:
        await message.answer("Не удалось получить контакт", reply_markup=ReplyKeyboardRemove())
        return

    user = users[0]

    manager.dialog_data["pending_user"] = {
        "user_id": user.user_id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "object": user.model_dump_json(exclude_none=True),
    }

    user_name = user.first_name
    if user.last_name:
        user_name += f" {user.last_name}"
    if user.username:
        user_name += f" @{user.username}"

    await message.answer(f"Выбран: {user_name}\nТеперь выберите должность:", reply_markup=ReplyKeyboardRemove())
    await manager.switch_to(AdminStates.select_role)


add_staff_ww = Window(
    Const("Пожалуйста, отправьте контакт сотрудника"),
    MessageInput(add_staff_handler),
    SwitchTo(Const("Назад"), state=AdminStates.manage_staff, id="manage_staff"),
    state=AdminStates.add_staff,
)


async def roles_getter(**kwargs):
    return {"roles": [(role, role) for role in ROLES]}


async def on_role_selected(callback: CallbackQuery, widget: Select, manager: DialogManager, role: str):
    pending_user = manager.dialog_data.get("pending_user")

    if not pending_user:
        await callback.answer("Ошибка: пользователь не найден")
        await manager.switch_to(AdminStates.manage_staff)
        return

    waiter_repository.add_waiter(
        telegram_id=pending_user["user_id"],
        telegram_object=pending_user["object"],
        role=role,
    )

    user_name = pending_user["first_name"]
    if pending_user.get("last_name"):
        user_name += f" {pending_user['last_name']}"

    await callback.message.answer(f"✅ Сотрудник {user_name} добавлен с должностью: {role}")
    manager.dialog_data.pop("pending_user", None)
    await manager.switch_to(AdminStates.manage_staff)


select_role_ww = Window(
    Const("Выберите должность сотрудника:"),
    Column(
        Select(
            Format("{item[0]}"),
            id="role_select",
            items="roles",
            item_id_getter=lambda item: item[1],
            on_click=on_role_selected,
        ),
    ),
    SwitchTo(Const("Отмена"), state=AdminStates.manage_staff, id="cancel"),
    getter=roles_getter,
    state=AdminStates.select_role,
)


def format_staff_card(item: dict) -> str:
    """Форматирует карточку сотрудника"""
    first_name = item.get("first_name", "")
    last_name = item.get("last_name", "")
    username = item.get("username")
    role = item.get("role")

    fio = f"{first_name} {last_name}".strip()
    username_str = f"@{username}" if username else "-"
    role_str = role if role else "-"

    return f"{fio} | {username_str} | {role_str}"


async def list_staff_getter(**kwargs):
    staff_raw = waiter_repository.get_waiters()
    staff = []
    text_lines = []

    for i, row in enumerate(staff_raw, 1):
        telegram_id = row[0]
        json_string = row[1]
        deleted = row[2]
        role = row[3] if len(row) > 3 else None

        if deleted:
            continue

        item = json.loads(json_string)
        item["id"] = telegram_id
        item["role"] = role

        # Данные сотрудника
        first_name = item.get("first_name", "")
        last_name = item.get("last_name", "")
        username = item.get("username")

        fio = f"{first_name} {last_name}".strip()
        username_str = f"@{username}" if username else "-"
        role_str = role if role else "-"

        # Для кнопки: ФИО | Логин | Должность
        item["button_name"] = f"{fio} | {username_str} | {role_str}"

        # Для текста
        text_lines.append(f"{i}. {fio} | {username_str} | {role_str}")
        staff.append(item)

    staff_text = "\n".join(text_lines) if text_lines else "Список пуст"

    return {"staff": staff, "staff_text": staff_text}


async def on_staff_selected(callback: CallbackQuery, widget: Select, manager: DialogManager, item_id: str):
    manager.dialog_data["selected_staff_id"] = int(item_id)
    await manager.switch_to(AdminStates.staff_actions)


async def edit_staff_handler(callback: CallbackQuery, button: Button, manager: SubManager):
    item_id = manager.item_id
    manager.dialog_data["edit_staff_id"] = int(item_id)
    await manager.switch_to(AdminStates.edit_staff_role)


async def delete_staff_handler(callback: CallbackQuery, button: Button, manager: SubManager):
    item_id = manager.item_id
    waiter_repository.remove_waiter(int(item_id))
    await callback.answer("Сотрудник удалён")


list_staff_ww = Window(
    Format("<b>📋 Список сотрудников</b>\n\n<i>ФИО | Телеграм | Должность</i>\n\n{staff_text}"),
    Const("\n<b>Выберите сотрудника:</b>"),
    Column(
        Select(
            Format("{item[button_name]}"),
            id="staff_select",
            items="staff",
            item_id_getter=lambda item: item["id"],
            on_click=on_staff_selected,
        ),
    ),
    SwitchTo(Const("◀️ Назад"), state=AdminStates.manage_staff, id="manage_staff"),
    getter=list_staff_getter,
    state=AdminStates.list_staff,
    parse_mode="HTML",
)


async def on_edit_role_selected(callback: CallbackQuery, widget: Select, manager: DialogManager, role: str):
    staff_id = manager.dialog_data.get("edit_staff_id")

    if not staff_id:
        await callback.answer("Ошибка: сотрудник не найден")
        await manager.switch_to(AdminStates.list_staff)
        return

    waiter_repository.update_role(staff_id, role)
    await callback.answer(f"Должность изменена на: {role}")
    manager.dialog_data.pop("edit_staff_id", None)
    await manager.switch_to(AdminStates.list_staff)


async def staff_actions_getter(dialog_manager: DialogManager, **kwargs):
    staff_id = dialog_manager.dialog_data.get("selected_staff_id")

    if not staff_id:
        return {"staff_name": "Не выбран", "staff_role": "-"}

    staff_raw = waiter_repository.get_waiters()

    for row in staff_raw:
        if row[0] == staff_id:
            item = json.loads(row[1])
            first_name = item.get("first_name", "")
            last_name = item.get("last_name", "")
            username = item.get("username")
            role = row[3] if len(row) > 3 else None

            staff_name = f"{first_name} {last_name}".strip()
            if username:
                staff_name += f" (@{username})"

            return {"staff_name": staff_name, "staff_role": role if role else "-"}

    return {"staff_name": "Не найден", "staff_role": "-"}


async def edit_from_actions(callback: CallbackQuery, button: Button, manager: DialogManager):
    staff_id = manager.dialog_data.get("selected_staff_id")
    manager.dialog_data["edit_staff_id"] = staff_id
    await manager.switch_to(AdminStates.edit_staff_role)


async def delete_from_actions(callback: CallbackQuery, button: Button, manager: DialogManager):
    staff_id = manager.dialog_data.get("selected_staff_id")
    if staff_id:
        waiter_repository.remove_waiter(staff_id)
        await callback.answer("✅ Сотрудник удалён")
    await manager.switch_to(AdminStates.list_staff)


staff_actions_ww = Window(
    Format("<b>👤 {staff_name}</b>\n\nДолжность: {staff_role}"),
    Button(Const("✏️ Редактировать должность"), id="edit", on_click=edit_from_actions),
    Button(Const("❌ Удалить сотрудника"), id="delete", on_click=delete_from_actions),
    SwitchTo(Const("◀️ Назад к списку"), state=AdminStates.list_staff, id="back"),
    getter=staff_actions_getter,
    state=AdminStates.staff_actions,
    parse_mode="HTML",
)

edit_staff_role_ww = Window(
    Const("Выберите новую должность:"),
    Column(
        Select(
            Format("{item[0]}"),
            id="edit_role_select",
            items="roles",
            item_id_getter=lambda item: item[1],
            on_click=on_edit_role_selected,
        ),
    ),
    SwitchTo(Const("Отмена"), state=AdminStates.list_staff, id="cancel"),
    getter=roles_getter,
    state=AdminStates.edit_staff_role,
)


feedback_ww = Window(
    Const("Введите общую обратную связь от посетителей"),
    MessageInput(partial(add_feedback_handler, mode="admin")),
    state=AdminStates.add_feedback,
)


router = Dialog(
    admin_menu_ww,
    manage_staff_ww,
    add_staff_ww,
    select_role_ww,
    list_staff_ww,
    staff_actions_ww,
    edit_staff_role_ww,
    feedback_ww,
    name="admin",
)
