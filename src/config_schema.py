import datetime
from enum import StrEnum
from pathlib import Path

import yaml
from aiogram.types import BotCommand
from pydantic import BaseModel, Field, SecretStr, ConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class SettingBaseModel(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")


class Settings(SettingBaseModel):
    """
    Settings for the application.
    """

    schema_: str = Field(None, alias="$schema")
    environment: Environment = Environment.DEVELOPMENT
    "App environment flag"
    redis_url: SecretStr | None = Field(None, examples=["redis://localhost:6379/0", "redis://redis:6379/0"])
    "Redis URL"
    bot_token: SecretStr
    "Telegram bot token from @BotFather"
    bot_name: str = None
    "Desired bot name"
    bot_description: str = None
    "Bot description"
    bot_short_description: str = None
    "Bot short description"
    bot_commands: list[BotCommand] = None
    "Bot commands (displayed in telegram menu)"
    fika_channel_link: str
    "Fika channel link"
    fika_channel_id: int
    "Fika channel ID (for sending reports)"
    admins: list[int] = []
    "Admin' telegram IDs"
    toweco_username: str
    "Toweco username"
    toweco_password: SecretStr
    "Toweco password"
    openai_api_key: SecretStr
    "OpenAI API key"
    openai_chat_model: str = "gpt-4o"
    "OpenAI chat model"
    daily_report_time: datetime.time | None = None
    "Time for daily report (UTC)"
    secret_for_waiter: SecretStr
    "Secret key for waiter on /start command"

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        with open(path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            schema = {"$schema": "http://json-schema.org/draft-07/schema#", **cls.model_json_schema()}
            yaml.dump(schema, f, sort_keys=False)
