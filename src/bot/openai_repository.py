import datetime
from io import BytesIO

import httpx
from openai import AsyncOpenAI

from src.bot.toweco_repository import toweco_repository
from src.config import settings

ADVICE_SYSTEM_PROMPT = """
Вы — помощник администратора ресторана Fika. Ваша задача — анализировать отзывы посетителей ресторана и предлагать короткие и конкретные советы, которые помогут улучшить работу ресторана. Учитывайте, что ваши рекомендации должны быть применимыми, основанными на отзывах и содержать максимум полезной информации без избыточных деталей.
"""

USER_MESSAGE_ADVICE_TEMPLATE = """
Вот последние отзывы посетителей ресторана Fika:

[reviews]

Проанализируйте отзывы и предложите конкретные советы для улучшения работы ресторана. Рекомендации должны быть лаконичными и полезными. Не более 3 параграфов.
"""

SUMMARY_SYSTEM_PROMPT = """
Вы — помощник для анализа отзывов клиентов и отчетов официантов ресторана. Ваша задача — сгруппировать отзывы по категориям и выделить проблемы.
"""

USER_MESSAGE_SUMMARY_TEMPLATE = """
Вот отзывы клиентов и отчеты официантов:

[reviews]

Проанализируйте их и сгруппируйте по категориям:
- Продукт (качество еды, напитков, блюд)
- Атмосфера (интерьер, музыка, чистота, комфорт)
- Сервис (обслуживание, скорость, вежливость персонала)
- Прочее (всё остальное)

Формат ответа:

📍 ПРОБЛЕМЫ (отрицательные отзывы):

**Продукт:** (только если 2+ жалобы, иначе пропустить)
конкретные замечания

**Атмосфера:** (только если 2+ жалобы, иначе пропустить)
конкретные замечания

**Сервис:** (только если 2+ жалобы, иначе пропустить)
конкретные замечания

**Прочее:** (только если 2+ жалобы, иначе пропустить)
конкретные замечания

──────────────────────────────

📍 ПОЛОЖИТЕЛЬНОЕ:

**Продукт:**
что хвалят

**Атмосфера:**
что хвалят

**Сервис:**
что хвалят

**Прочее:**
что хвалят

Будьте конкретны — указывайте названия блюд и конкретные замечания.
НЕ давайте рекомендации, только факты из отзывов.
Категории без отзывов пропускайте.
"""

# Прокси для обхода блокировки OpenAI
PROXY_URL = "http://6dPrK3hR:VP2zxuMP@154.196.75.167:64380"


class OpenAIRepository:
    def __init__(self):
        # Создаём HTTP клиент с прокси
        http_client = httpx.AsyncClient(proxy=PROXY_URL)
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), http_client=http_client)

    async def get_advice(self, reviews, waiter_reports) -> str | None:
        today = datetime.date.today()
        if not reviews and not waiter_reports:
            return None

        # split into today reviews and previous reviews
        today_reviews = [review for review in reviews if review["publishedAt"].startswith(str(today))]
        previous_reviews = [review for review in reviews if review["publishedAt"].startswith(str(today)) is False]
        today_reviews.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))
        previous_reviews.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))
        waiter_reports.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))

        text_reviews = ""
        if today_reviews:
            text_reviews += "Новые отзывы (Сегодня):\n"
            text_reviews += "\n\n".join([toweco_repository.format_review(review) for review in today_reviews])
            text_reviews += "\n---\n"

        if previous_reviews:
            text_reviews += "Отзывы (Ранее):\n"
            text_reviews += "\n\n".join([toweco_repository.format_review(review) for review in previous_reviews])
            text_reviews += "\n---\n"

        if waiter_reports:
            text_reviews += "Отчеты от официантов:\n"
            text_reviews = "\n\n".join([toweco_repository.format_review(report) for report in waiter_reports])

        response = await self.client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": ADVICE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": USER_MESSAGE_ADVICE_TEMPLATE.replace("[reviews]", text_reviews),
                },
            ],
            timeout=60,
        )
        return response.choices[0].message.content

    async def summary(self, reviews, waiter_reports) -> str | None:
        if not reviews and not waiter_reports:
            return None

        # Сортировка и форматирование отзывов и отчетов
        reviews.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))
        waiter_reports.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))

        # Объединение отзывов и отчетов
        text_reviews = "Отзывы:\n"
        if reviews:
            text_reviews += "\n\n".join([toweco_repository.format_review(review) for review in reviews])
        if waiter_reports:
            text_reviews += "\n\nОтчеты официантов:\n"
            text_reviews += "\n\n".join([toweco_repository.format_review(report) for report in waiter_reports])

        # Запрос к OpenAI
        response = await self.client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[
                {
                    "role": "system",
                    "content": SUMMARY_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": USER_MESSAGE_SUMMARY_TEMPLATE.replace("[reviews]", text_reviews),
                },
            ],
            timeout=60,
        )
        return response.choices[0].message.content

    async def transript(self, audio: BytesIO) -> str:
        transcription = await self.client.audio.transcriptions.create(
            file=audio, model="whisper-1", language="ru", response_format="text"
        )
        return transcription


openai_repository: OpenAIRepository = OpenAIRepository()
