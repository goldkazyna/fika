from aiogram import Bot, Router
from aiogram import types
from aiogram.filters import CommandObject, CommandStart, Command
from aiogram.types import BotCommandScopeChat
from aiogram_dialog import DialogManager, StartMode

from src.bot.filters import StatusFilter
from src.bot.routers.admin import AdminStates
from src.bot.routers.waiter import WaiterStates
from src.bot.waiter_repository import waiter_repository
from src.config import settings

from aiogram.filters.logic import or_f

router = Router(name="commands")


@router.message(CommandStart(), StatusFilter("waiter"))
async def start_waiter(message: types.Message, dialog_manager: DialogManager, bot: Bot):
    await bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id=message.chat.id))
    await message.answer("Добро пожаловать! Ваш статус: <i>официант</i>.", parse_mode="HTML")
    await dialog_manager.start(WaiterStates.menu, mode=StartMode.RESET_STACK)


@router.message(CommandStart(), StatusFilter("admin"))
async def start_admin(message: types.Message, bot: Bot):
    await bot.set_my_commands(
        (settings.bot_commands or [])
        + [
            types.BotCommand(command="admin", description="Включить режим администратора"),
            types.BotCommand(command="waiter", description="Включить режим официанта"),
        ],
        scope=BotCommandScopeChat(chat_id=message.from_user.id),
    )
    await message.answer("Добро пожаловать! Ваш статус: <i>администратор</i>.", parse_mode="HTML")
    await message.answer("Перейти в режим администратора /admin\nПерейти в режим официанта /waiter")


@router.message(CommandStart())
async def start_none(message: types.Message, command: CommandObject, bot: Bot, dialog_manager: DialogManager):
    if command.args and command.args == settings.secret_for_waiter.get_secret_value():
        waiter_repository.add_waiter(message.from_user.id, message.from_user.model_dump_json(exclude_none=True))
        await bot.delete_my_commands(scope=types.BotCommandScopeChat(chat_id=message.chat.id))
        await message.answer("Добро пожаловать! Ваш статус: <i>официант</i>.", parse_mode="HTML")
        await dialog_manager.start(WaiterStates.menu, mode=StartMode.RESET_STACK)
    else:
        await message.answer("Добро пожаловать! Нам не удалось определить ваш статус, обратитесь к администратору.")


@router.message(Command("admin"), StatusFilter("admin"))
async def enable_admin_mode(message: types.Message, bot: Bot, dialog_manager: DialogManager):
    await dialog_manager.start(AdminStates.menu, mode=StartMode.RESET_STACK)


@router.message(Command("admin"), ~StatusFilter("admin"))
async def failed_enable_admin_mode(message: types.Message, bot: Bot):
    text = "Вы не админ!"
    await message.answer(text)
    await bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=message.from_user.id))


@router.message(Command("waiter"), or_f(StatusFilter("waiter"), StatusFilter("admin")))
async def enable_waiter_mode(message: types.Message, bot: Bot, dialog_manager: DialogManager):
    await dialog_manager.start(WaiterStates.menu, mode=StartMode.RESET_STACK)
