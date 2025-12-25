import pandas as pd
import matplotlib.pyplot as plt
import datetime
import io
import matplotlib.colors as mcolors
from matplotlib import rcParams, ticker

rcParams["text.antialiased"] = True


def happiness_chart(reviews) -> bytes:
    # Подготовка данных
    df = pd.DataFrame(reviews)
    df["date"] = pd.to_datetime(df["publishedAt"]).dt.date  # Извлечение только даты
    df["rating"] = df["rating"].astype(int)

    # Подсчет количества отзывов на каждую дату
    review_counts_by_date = df.groupby("date").size()

    # Создание диапазона дат, включая самую раннюю дату отзывов
    today = datetime.date.today()
    earliest_date = min(df["date"].min(), today - datetime.timedelta(days=13))
    all_dates = pd.date_range(start=earliest_date, end=today)

    # Заполнение данных нулями для отсутствующих дней
    full_review_counts = pd.Series(0, index=all_dates)
    for date, count in review_counts_by_date.items():
        full_review_counts[pd.Timestamp(date)] = count

    # Карта перевода месяцев на русский
    month_translation = {
        "Jan": "Янв",
        "Feb": "Фев",
        "Mar": "Мар",
        "Apr": "Апр",
        "May": "Май",
        "Jun": "Июн",
        "Jul": "Июл",
        "Aug": "Авг",
        "Sep": "Сен",
        "Oct": "Окт",
        "Nov": "Ноя",
        "Dec": "Дек",
    }

    # Форматирование дат в русском формате
    formatted_full_dates_russian = [
        date.strftime("%d %b").replace(date.strftime("%b"), month_translation[date.strftime("%b")])
        for date in full_review_counts.index
    ]

    # Расчет средней шкалы счастья для доступных дат
    daily_happiness_scores = pd.Series(None, index=full_review_counts.index, dtype=float)
    daily_ratings = df.groupby("date")["rating"].mean()
    for date in daily_ratings.index:
        daily_happiness_scores[pd.Timestamp(date)] = daily_ratings[date]

    # Удаляем пропуски
    daily_happiness_scores = daily_happiness_scores.fillna(0)

    # Нормализация цветов на основе шкалы счастья
    norm = mcolors.Normalize(vmin=1, vmax=5)
    colormap = mcolors.LinearSegmentedColormap.from_list(
        "custom_colormap", ["#d73027", "#f46d43", "#ffc000", "#a6d96a", "#66bd63"]
    )

    # Построение графика
    fig, ax = plt.subplots(figsize=(12, 6), dpi=200)

    # Столбцы с улучшенным градиентом цвета
    colors = [colormap(norm(score)) for score in daily_happiness_scores]
    bars = ax.bar(
        full_review_counts.index, full_review_counts.values, color=colors, alpha=0.8, label="Количество отзывов"
    )

    # Добавление текста с оценками счастья внутри столбцов
    for bar, score in zip(bars, daily_happiness_scores):
        height = bar.get_height()
        score_str = f"{score:.1f}" if score > 0 else ""
        if score == 0:
            continue

        stars_str = "★" * int(score) + "☆" * (5 - int(score))
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height / 2,  # Positioning inside the bar
            score_str,
            ha="center",
            va="center",
            fontsize=12,
            weight="bold",
            color="white" if height > 0 else "black",
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height / 2 - 0.2,  # Positioning inside the bar
            stars_str,
            ha="center",
            va="center",
            fontsize=8,
            color="white" if height > 0 else "black",
        )

    ax.set_xlabel("Дата")
    ax.set_ylabel("Количество отзывов")
    ax.set_title("Отзывы и оценки")

    # Установка пределов для оси Y количества отзывов
    ax.set_ylim(0, max(5, full_review_counts.max()) * 1.03)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

    # Форматирование оси X
    ax.set_xticks(full_review_counts.index)
    xticks_colors = ["green" if date.date() == today else "black" for date in full_review_counts.index]
    for tick, color in zip(ax.set_xticklabels(formatted_full_dates_russian, rotation=45), xticks_colors):
        tick.set_color(color)

    total_reviews = len(reviews)
    mean_rating = df["rating"].mean()
    ax.annotate(
        f"Всего отзывов: {total_reviews}\n" f"Средняя оценка: {mean_rating:.1f}\n",
        (1, 1),
        (-140, -10),
        xycoords="axes fraction",
        textcoords="offset points",
        va="top",
        ha="left",
        fontsize=12,
        color="black",
    )
    fig.text(
        0.005,
        0.995,
        "Цвет и число внутри столбца - средняя оценка за этот день\n"
        "Высота столбца - количество отзывов за этот день",
        va="top",  # Выравнивание снизу
        ha="left",  # Выравнивание по центру
        fontsize=10,
        color="black",
    )

    # Сохранение графика в байты
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return buf.getvalue()


def provider_pie_chart(reviews) -> bytes:
    PROVIDERS = [
        {"sign": "TO", "name": "Товеко QR-код", "color": "#FF9F00"},
        {"sign": "YA", "name": "Яндекс", "color": "#f43"},
        {"sign": "2G", "name": "2ГИС", "color": "#50A739"},
        {"sign": "GL", "name": "Google", "color": "#3d83f3"},
        {"sign": "RC", "name": "Restoclub", "color": "#ed0f08"},
        {"sign": "FL", "name": "Фламп", "color": "#2967e8"},
        {"sign": "ZN", "name": "Zoon", "color": "#614ba0"},
        {"sign": "TR", "name": "Tripadvisor", "color": "#34e0a1"},
        {"sign": "YL", "name": "Yell", "color": "#ff3b3b"},
        {"sign": "OZ", "name": "Отзовик", "color": "#ce2457"},
        {"sign": "IR", "name": "Irecommend", "color": "#fd6540"},
        {"sign": "AF", "name": "Афиша", "color": "#ce1f1d"},
        {"sign": "FC", "name": "Foursquare", "color": "#fa4778"},
        {"sign": "TN", "name": "Т-Банк", "color": "#ffdd2d"},
        {"sign": "NM", "name": "Нет монет", "color": "#3e3467"},
        {"sign": "ZT", "name": "Zomato", "color": "#e33745"},
        {"sign": "VD", "name": "Ваш Досуг", "color": "#374A3B"},
        {"sign": "DC", "name": "Деливери", "color": "#6fe250"},
        {"sign": "OS", "name": "Островок", "color": "#0e41d2"},
        {"sign": "OTT", "name": "OneTwoTrip", "color": "#000"},
        {"sign": "101H", "name": "101hotels", "color": "#ff4141"},
        {"sign": "WAH", "name": "WhatsApp", "color": "#25d366"},
        {"sign": "TGH", "name": "Telegram", "color": "#25a2e0"},
        {"sign": "IGH", "name": "Instagram", "color": "#c2328b"},
        {"sign": "VK_H", "name": "Вконтакте", "color": "#07f"},
        {"sign": "TLF", "name": "Телефон", "color": "#fdc73e"},
        {"sign": "EMH", "name": "Email", "color": "#F4F778"},
        {"sign": "YE", "name": "Яндекс.Еда", "color": "#5381ae"},
        {"sign": "DD", "name": "DOCDOC", "color": "#F0F0F0"},
        {"sign": "NP", "name": "NAPOPRAVKU", "color": "#F0F0F0"},
    ]

    # Подготовка данных
    df = pd.DataFrame(reviews)

    if "provider" not in df.columns:
        raise ValueError("The reviews data must contain a 'provider' field.")

    # Подсчет количества отзывов для каждого провайдера
    provider_counts = df["provider"].value_counts()

    # Создание карты цветов для провайдеров
    provider_colors = {provider["name"]: provider["color"] for provider in PROVIDERS}

    # Упорядочивание цветов в соответствии с данными
    colors = [provider_colors.get(name, "#cccccc") for name in provider_counts.index]

    # Построение круговой диаграммы
    fig, ax = plt.subplots(figsize=(10, 10), dpi=200)

    def autopct_with_counts(pct, all_values):
        absolute = int(round(pct / 100.0 * sum(all_values)))
        return f"{pct:.0f}% ({absolute})"

    wedges, texts, autotexts = ax.pie(
        provider_counts,
        labels=provider_counts.index,
        autopct=lambda pct: autopct_with_counts(pct, provider_counts.values),
        startangle=140,
        colors=colors,
        textprops={"fontsize": 18},
    )

    # Форматирование текста внутри сегментов
    for autotext in autotexts:
        autotext.set_fontsize(18)
        autotext.set_color("white")

    # Заголовок графика
    ax.set_title("Распределение отзывов по площадкам", fontsize=18)

    # Сохранение графика в байты
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return buf.getvalue()


def rating_distribution_chart(reviews) -> bytes:
    # Подготовка данных
    df = pd.DataFrame(reviews)
    df["rating"] = df["rating"].astype(int)

    # Подсчет количества отзывов для каждого рейтинга
    rating_counts = df["rating"].value_counts().sort_index()

    # Заполнение отсутствующих рейтингов нулями (1-5 звезды)
    full_rating_counts = pd.Series({i: 0 for i in range(1, 6)})
    full_rating_counts.update(rating_counts)

    # Подсчет процентов для каждого рейтинга
    total_reviews = len(reviews)
    rating_percentages = (full_rating_counts / total_reviews * 100).round(1)

    # Формирование меток на оси X
    star_labels = [f'{"★" * i}{"☆" * (5 - i)}' for i in range(1, 6)]

    # Построение графика
    fig, ax = plt.subplots(figsize=(10, 6), dpi=200)

    bars = ax.bar(
        star_labels, full_rating_counts.values, color=["#ff3b3b", "#f46d43", "#ffc000", "#a6d96a", "#66bd63"], alpha=0.8
    )

    # Добавление текста с количеством и процентами отзывов
    for bar, count, pct in zip(bars, full_rating_counts, rating_percentages):
        if count > 0:  # Исключить метки для нулевых значений
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() / 2 + 0,
                f"{pct:.1f}% ({count})",
                ha="center",
                va="bottom",
                fontsize=14,
                color="white",
            )

    ax.set_xlabel("Рейтинг", fontsize=14)
    ax.set_ylabel("Количество отзывов", fontsize=14)
    ax.set_title("Распределение отзывов по рейтингу", fontsize=16)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    # Сохранение графика в байты
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)

    return buf.getvalue()


if __name__ == "__main__":
    reviews = [
        {"publishedAt": "2024-12-11T16:13:37Z", "rating": 3, "provider": "2ГИС"},
        {"publishedAt": "2024-12-12T16:13:37Z", "rating": 2, "provider": "Google"},
        {"publishedAt": "2024-12-12T04:41:01Z", "rating": 5, "provider": "2ГИС"},
        {"publishedAt": "2024-12-12T03:13:34Z", "rating": 5, "provider": "Яндекс"},
        {"publishedAt": "2024-12-16T03:13:34Z", "rating": 5, "provider": "Яндекс"},
    ]

    image_bytes = happiness_chart(reviews)

    with open("chart.png", "wb") as f:
        f.write(image_bytes)

    image_bytes = provider_pie_chart(reviews)

    with open("pie_chart.png", "wb") as f:
        f.write(image_bytes)

    image_bytes = rating_distribution_chart(reviews)

    with open("rating_distribution_chart.png", "wb") as f:
        f.write(image_bytes)
