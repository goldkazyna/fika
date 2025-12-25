from aiogram.types import BotCommand
from pydantic import TypeAdapter

commands_type_adapter = TypeAdapter(list[BotCommand])


def check_commands_equality(x: list[BotCommand], y: list[BotCommand]) -> bool:
    return commands_type_adapter.dump_json(x) == commands_type_adapter.dump_json(y)


def telegram_format(text: str) -> str:
    import chatgpt_md_converter

    text = chatgpt_md_converter.telegram_format(text)
    text = text.strip()
    return text
