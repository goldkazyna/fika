import asyncio
import calendar
import datetime
import statistics

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, InputMediaPhoto

from src.bot.logging_ import logger
from src.bot.openai_repository import openai_repository
from src.bot.plotting import happiness_chart, provider_pie_chart, rating_distribution_chart
from src.bot.toweco_repository import toweco_repository
from src.bot.utils import telegram_format
from src.bot.waiter_repository import waiter_repository
from src.config import settings
from dateutil import tz


def get_today():
    return datetime.datetime.now(tz=tz.gettz("Asia/Almaty")).date()


def is_summary_day(date: datetime.date) -> bool:
    """Проверяет, является ли день днём для генерации сводки (15-е или последний день месяца)"""
    if date.day == 15:
        return True
    # Последний день месяца
    last_day = calendar.monthrange(date.year, date.month)[1]
    if date.day == last_day:
        return True
    return False


async def daily_report_loop():
    if not settings.daily_report_time:
        logger.warning("Daily report time is not set")
        return
    await asyncio.sleep(10)  # wait for the bot to start
    while True:
        _now = datetime.datetime.now(datetime.UTC)
        to_notify = datetime.datetime(
            _now.year,
            _now.month,
            _now.day,
            hour=settings.daily_report_time.hour,
            minute=settings.daily_report_time.minute,
            tzinfo=datetime.UTC,
        )
        if _now >= to_notify:
            logger.info("Daily report time has passed. Waiting until tomorrow")
            to_notify += datetime.timedelta(days=1)

        wait = (to_notify - _now).total_seconds()
        logger.info(f"Waiting {round(wait)} seconds until next daily report: {to_notify}")
        await asyncio.sleep(wait)
        logger.info("Sending daily report")

        reviews = None

        today = get_today()
        date_from = today - datetime.timedelta(days=13)

        for _ in range(5):
            error_message, reviews = await fetch_reviews(date_from)

            if error_message:
                logger.warning(f"Coudn't fetch reviews: {error_message}")
                await asyncio.sleep(100)
                continue
            else:
                break
        waiter_reports = await fetch_reports(date_from)
        ai_advice = await get_ai_advice(reviews, waiter_reports)

        for chat_id in [settings.fika_channel_id] + settings.admins:
            for _ in range(3):
                try:
                    error_message = await send_report(chat_id, reviews, waiter_reports, ai_advice)
                    if error_message:
                        logger.warning("Couldn't send the report to %s: %s", chat_id, error_message)
                    else:
                        logger.info(f"Successfully sent the report to {chat_id}")
                    break
                except TelegramBadRequest as e:  # Bad Request
                    logger.warning("Couldn't send the report to %s. Please check: %s", chat_id, e)
                    break
                except Exception as e:
                    logger.warning("Couldn't send the report to %s. Please check: %s", chat_id, e)
                    await asyncio.sleep(100)
            await asyncio.sleep(1)


async def summary_report_loop():
    """Цикл для автоматической отправки PDF сводки 15-го и в последний день месяца в 10:00"""
    await asyncio.sleep(15)  # wait for the bot to start

    summary_hour = 10
    summary_minute = 0

    while True:
        # Текущее время в Алматы
        now_almaty = datetime.datetime.now(tz=tz.gettz("Asia/Almaty"))
        today = now_almaty.date()

        # Определяем следующую дату для отправки
        next_summary_date = None

        # Проверяем сегодня
        if is_summary_day(today):
            target_time = now_almaty.replace(hour=summary_hour, minute=summary_minute, second=0, microsecond=0)
            if now_almaty < target_time:
                next_summary_date = today
            else:
                # Уже прошло время, ищем следующую дату
                next_summary_date = None

        # Если сегодня не подходит, ищем следующую дату
        if next_summary_date is None:
            check_date = today + datetime.timedelta(days=1)
            for _ in range(31):  # максимум месяц вперёд
                if is_summary_day(check_date):
                    next_summary_date = check_date
                    break
                check_date += datetime.timedelta(days=1)

        if next_summary_date is None:
            logger.error("Could not find next summary date")
            await asyncio.sleep(3600)
            continue

        # Вычисляем время до отправки
        target_datetime = datetime.datetime(
            next_summary_date.year,
            next_summary_date.month,
            next_summary_date.day,
            hour=summary_hour,
            minute=summary_minute,
            tzinfo=tz.gettz("Asia/Almaty"),
        )

        wait_seconds = (target_datetime - now_almaty).total_seconds()

        if wait_seconds > 0:
            logger.info(
                f"Next PDF summary scheduled for {target_datetime.strftime('%d.%m.%Y %H:%M')} "
                f"(in {round(wait_seconds / 3600, 1)} hours)"
            )
            await asyncio.sleep(wait_seconds)

        # Отправляем сводку
        logger.info("Sending scheduled PDF summary")
        await send_summary_to_all()


async def send_summary_to_all():
    """Отправляет PDF сводку в канал и всем админам"""
    recipients = [settings.fika_channel_id] + settings.admins

    for chat_id in recipients:
        for attempt in range(3):
            try:
                error_message = await send_summary(chat_id)
                if error_message:
                    logger.warning(f"Couldn't send PDF summary to {chat_id}: {error_message}")
                else:
                    logger.info(f"Successfully sent PDF summary to {chat_id}")
                break
            except TelegramBadRequest as e:
                logger.warning(f"Couldn't send PDF summary to {chat_id}: {e}")
                break
            except Exception as e:
                logger.warning(f"Couldn't send PDF summary to {chat_id} (attempt {attempt + 1}): {e}")
                await asyncio.sleep(30)
        await asyncio.sleep(2)


async def fetch_reviews(date_from: datetime.date) -> tuple[str | None, list]:
    try:
        reviews = await toweco_repository.get_reviews(date_from=date_from)
        reviews.sort(key=lambda x: datetime.datetime.fromisoformat(x["publishedAt"]))
    except Exception as e:
        if isinstance(e, RuntimeError) and e.args:
            first = e.args[0]
            if (
                isinstance(first, dict)
                and "error" in first
                and "code" in first.get("error", {})
                and first["error"]["code"] == 429
            ):
                return "Слишком много запросов к API, попробуйте через минуту", []

        logger.error(f"Failed to fetch reviews: {e}", exc_info=True)
        return "Ошибка при получении отзывов", []
    if not reviews:
        return f"Отзывов с {date_from} нет", []

    return None, reviews


async def fetch_reports(date_from: datetime.date) -> list:
    reports = waiter_repository.get_reports(date_from)

    return [waiter_repository.to_toweco_format(r) for r in reports]


async def get_ai_advice(reviews: list, waiter_reports: list) -> str:
    today = get_today()
    to_ai_reviews = []
    to_ai_waiter_reports = []
    # filter out only today and yesterday reviews
    for review in reviews:
        at = datetime.datetime.fromisoformat(review["publishedAt"]).astimezone(tz=tz.gettz("Asia/Almaty"))
        if at.date() >= today - datetime.timedelta(days=1):
            to_ai_reviews.append(review)
    for report in waiter_reports:
        at = datetime.datetime.fromisoformat(report["publishedAt"]).astimezone(tz=tz.gettz("Asia/Almaty"))
        if at.date() >= today - datetime.timedelta(days=1):
            to_ai_waiter_reports.append(report)

    logger.info(f"Sending {len(to_ai_reviews)} reviews and {len(to_ai_waiter_reports)} waiter reports to AI")

    return await openai_repository.get_advice(to_ai_reviews, to_ai_waiter_reports)


async def send_report(
    chat_id: int, reviews: list | None = None, waiter_reports: list | None = None, ai_advice: str | None = None
) -> None | str:
    from src.bot.app import bot

    today = get_today()
    date_from = today - datetime.timedelta(days=13)

    if reviews is None:
        error_message, reviews = await fetch_reviews(date_from)

        if error_message:
            return error_message

    if waiter_reports is None:
        waiter_reports = await fetch_reports(date_from)

    today_reviews = []
    today_reports = []

    for review in reviews:
        at = datetime.datetime.fromisoformat(review["publishedAt"]).astimezone(tz=tz.gettz("Asia/Almaty"))
        if at.date() >= today:
            today_reviews.append(review)

    for report in waiter_reports:
        at = datetime.datetime.fromisoformat(report["publishedAt"]).astimezone(tz=tz.gettz("Asia/Almaty"))
        if at.date() >= today:
            today_reports.append(report)

    text = f"<b>Отчёт с {date_from} по {today}</b>\n\n"

    positive = len([review for review in reviews if review["rating"] > 3])
    negative = len([review for review in reviews if review["rating"] < 3])
    mean_rate = f"{statistics.mean([review['rating'] for review in reviews]):.1f}"
    text += "<b>Общая статистика</b>\n"
    text += f"Отзывы: {len(reviews)} всего, {positive} 😊 {negative} 😞     ⭐️ {mean_rate}\n"
    text += f"Отчёты от официантов: {len(waiter_reports)} всего\n\n"

    if today_reviews:
        positive = len([review for review in today_reviews if review["rating"] > 3])
        negative = len([review for review in today_reviews if review["rating"] < 3])
        mean_rate = f"{statistics.mean([review['rating'] for review in today_reviews]):.1f}"

        text += f"<b>Отзывы за сегодня: {positive} 😊 {negative} 😞     ⭐️ {mean_rate}</b>:\n"
        text += "\n\n".join([toweco_repository.format_review(review) for review in today_reviews])
        text += "\n\n"
    else:
        text += "<b>Нет отзывов за сегодня</b> 🥹\n\n"

    if today_reports:
        text += f"<b>Отчёты от официантов за сегодня ({len(today_reports)})</b>\n"
        text += "\n\n".join([toweco_repository.format_review(report) for report in today_reports])
        text += "\n\n"

    message = await bot.send_message(chat_id, text=text, parse_mode="HTML")

    await message.reply_media_group(
        media=[
            InputMediaPhoto(media=BufferedInputFile(happiness_chart(reviews), filename="happiness_chart.png")),
            InputMediaPhoto(media=BufferedInputFile(provider_pie_chart(reviews), filename="provider_pie_chart.png")),
            InputMediaPhoto(
                media=BufferedInputFile(rating_distribution_chart(reviews), filename="rating_distribution_chart.png")
            ),
        ],
    )
    if not ai_advice:
        ai_advice = await get_ai_advice(reviews, waiter_reports)

    if ai_advice:
        ai_advice_text = f"<b>Советы:</b>\n<blockquote expandable>{telegram_format(ai_advice)}</blockquote>"
        await message.reply(ai_advice_text, parse_mode="HTML")


async def send_summary(chat_id: int) -> None | str:
    """Отправляет сводку в виде PDF файла"""
    from src.bot.app import bot
    from src.bot.pdf_report import generate_summary_pdf

    today = get_today()
    date_from = today - datetime.timedelta(days=13)

    # Отправляем сообщение о начале генерации (только для личных чатов, не каналов)
    status_msg = None
    if chat_id > 0:  # Личный чат
        status_msg = await bot.send_message(chat_id, "⏳ Генерирую PDF отчёт, подождите...")

    try:
        # Получаем данные
        error_message, reviews = await fetch_reviews(date_from)
        if error_message:
            if status_msg:
                await status_msg.edit_text(f"❌ {error_message}")
            return error_message

        waiter_reports = await fetch_reports(date_from)

        # Получаем AI сводку
        if status_msg:
            await status_msg.edit_text("🤖 Генерирую AI-анализ...")
        ai_summary = await openai_repository.summary(reviews, waiter_reports)

        # Генерируем PDF
        if status_msg:
            await status_msg.edit_text("📄 Создаю PDF...")
        pdf_bytes = generate_summary_pdf(reviews, waiter_reports, ai_summary)

        # Считаем статистику
        mean_rating = statistics.mean([r.get("rating", 0) for r in reviews]) if reviews else 0

        # Отправляем файл
        filename = f"Сводка_{date_from.strftime('%d.%m')}-{today.strftime('%d.%m.%Y')}.pdf"
        await bot.send_document(
            chat_id,
            document=BufferedInputFile(pdf_bytes, filename=filename),
            caption=f"📊 Сводка за период {date_from.strftime('%d.%m.%Y')} — {today.strftime('%d.%m.%Y')}\n\n"
            f"📝 Отзывов: {len(reviews)}\n"
            f"⭐️ Средняя оценка: {mean_rating:.1f}\n"
            f"👥 Отчётов от сотрудников: {len(waiter_reports)}",
        )

        # Удаляем статусное сообщение
        if status_msg:
            await status_msg.delete()

    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        if status_msg:
            await status_msg.edit_text(f"❌ Ошибка при генерации отчёта: {str(e)}")
        return f"Ошибка: {str(e)}"

    return None
