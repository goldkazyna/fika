"""
Генерация PDF отчёта за 2 недели с Mood Meter
"""

import datetime
import statistics
import os
import math
from io import BytesIO

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Регистрируем шрифт с поддержкой кириллицы
def register_fonts():
    """Регистрирует шрифты с поддержкой кириллицы"""
    font_paths = [
        # Windows
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
        # Linux
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ),
    ]

    for regular, bold in font_paths:
        if os.path.exists(regular) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("CustomFont", regular))
                pdfmetrics.registerFont(TTFont("CustomFont-Bold", bold))
                return "CustomFont", "CustomFont-Bold"
            except Exception:
                continue

    return "Helvetica", "Helvetica-Bold"


FONT_NAME, FONT_BOLD = register_fonts()


def get_emoji_font():
    """Находит шрифт с поддержкой emoji"""
    emoji_fonts = [
        "C:/Windows/Fonts/seguiemj.ttf",  # Windows Segoe UI Emoji
        "C:/Windows/Fonts/segoe ui emoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",  # Linux
        "/System/Library/Fonts/Apple Color Emoji.ttc",  # macOS
    ]

    for font_path in emoji_fonts:
        if os.path.exists(font_path):
            return fm.FontProperties(fname=font_path)

    return None


def create_mood_meter(rating: float) -> bytes:
    """
    Создаёт изображение Mood Meter с помощью matplotlib
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-0.3, 1.3)
    ax.set_aspect("equal")
    ax.axis("off")

    # Цвета секторов
    colors = ["#D32F2F", "#F57C00", "#FDD835", "#9CCC65", "#388E3C"]

    # Рисуем секторы
    for i in range(5):
        start_angle = 180 - (i * 36)
        end_angle = 180 - ((i + 1) * 36)

        wedge = patches.Wedge(
            (0, 0), 1.0, end_angle, start_angle, facecolor=colors[i], edgecolor="white", linewidth=2, zorder=1
        )
        ax.add_patch(wedge)

    # Белый круг в центре
    inner_circle = patches.Circle((0, 0), 0.5, facecolor="white", edgecolor="white", zorder=2)
    ax.add_patch(inner_circle)

    # Emoji и их позиции (в центре каждого сектора)
    emojis = ["😞", "🙁", "😐", "🙂", "😊"]
    emoji_angles = [162, 126, 90, 54, 18]  # центры секторов

    emoji_font = get_emoji_font()

    for emoji, angle in zip(emojis, emoji_angles):
        angle_rad = math.radians(angle)
        x = 0.75 * math.cos(angle_rad)
        y = 0.75 * math.sin(angle_rad)

        # Белый круг-фон для emoji
        bg_circle = patches.Circle((x, y), 0.13, facecolor="white", edgecolor="#666666", linewidth=1.5, zorder=10)
        ax.add_patch(bg_circle)

        # Emoji текст
        if emoji_font:
            ax.text(x, y, emoji, fontsize=16, ha="center", va="center", fontproperties=emoji_font, zorder=11)
        else:
            ax.text(x, y, emoji, fontsize=16, ha="center", va="center", zorder=11)

    # Угол стрелки
    # rating 1.0 -> 180° (крайняя левая точка)
    # rating 5.0 -> 0° (крайняя правая точка)
    # Линейная интерполяция: angle = 180 - (rating - 1) * 45
    angle_deg = 180 - (rating - 1) * 45
    angle_rad = math.radians(angle_deg)

    # Стрелка
    arrow_length = 0.95
    arrow_x = arrow_length * math.cos(angle_rad)
    arrow_y = arrow_length * math.sin(angle_rad)

    base_width = 0.08
    base_angle1 = angle_rad + math.pi / 2
    base_angle2 = angle_rad - math.pi / 2

    triangle = plt.Polygon(
        [
            [arrow_x, arrow_y],
            [base_width * math.cos(base_angle1), base_width * math.sin(base_angle1)],
            [base_width * math.cos(base_angle2), base_width * math.sin(base_angle2)],
        ],
        facecolor="#1a1a1a",
        edgecolor="none",
        zorder=20,
    )
    ax.add_patch(triangle)

    # Круг в центре
    center_circle = patches.Circle((0, 0), 0.08, facecolor="#1a1a1a", zorder=21)
    ax.add_patch(center_circle)

    # Заголовок
    ax.text(0, 1.15, "FIKA MOOD METER", fontsize=14, fontweight="bold", ha="center", va="center", color="#333333")

    # Значение рейтинга
    ax.text(0, -0.15, f"{rating:.1f}", fontsize=18, fontweight="bold", ha="center", va="center", color="#333333")

    buffer = BytesIO()
    plt.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    buffer.seek(0)

    return buffer.getvalue()


def create_styles():
    """Создаёт стили для PDF"""
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TitleRu",
            fontName=FONT_BOLD,
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=HexColor("#2C3E50"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubtitleRu",
            fontName=FONT_NAME,
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=HexColor("#7F8C8D"),
        )
    )

    styles.add(
        ParagraphStyle(
            name="HeadingRu",
            fontName=FONT_BOLD,
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=HexColor("#2980B9"),
        )
    )

    styles.add(ParagraphStyle(name="NormalRu", fontName=FONT_NAME, fontSize=11, spaceAfter=8, leading=14))

    return styles


def generate_summary_pdf(reviews: list, waiter_reports: list, ai_summary: str = None) -> bytes:
    """Генерирует PDF отчёт"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm
    )

    styles = create_styles()
    story = []

    today = datetime.date.today()
    date_from = today - datetime.timedelta(days=13)

    # ЗАГОЛОВОК
    story.append(Paragraph("Сводка за 2 недели", styles["TitleRu"]))
    story.append(Paragraph(f"{date_from.strftime('%d.%m.%Y')} - {today.strftime('%d.%m.%Y')}", styles["SubtitleRu"]))

    # MOOD METER
    if reviews:
        mean_rating = statistics.mean([r.get("rating", 0) for r in reviews])

        try:
            mood_img_bytes = create_mood_meter(mean_rating)
            mood_img = Image(BytesIO(mood_img_bytes), width=130 * mm, height=85 * mm)
            story.append(mood_img)
            story.append(Spacer(1, 10))
        except Exception as e:
            story.append(Paragraph(f"Ошибка Mood Meter: {e}", styles["NormalRu"]))

    # СТАТИСТИКА
    story.append(Paragraph("Общая статистика", styles["HeadingRu"]))

    if reviews:
        positive = len([r for r in reviews if r.get("rating", 0) > 3])
        negative = len([r for r in reviews if r.get("rating", 0) < 3])
        neutral = len([r for r in reviews if r.get("rating", 0) == 3])
        mean_rating = statistics.mean([r.get("rating", 0) for r in reviews])

        stats_data = [
            ["Показатель", "Значение"],
            ["Всего отзывов", str(len(reviews))],
            ["Положительных (4-5)", str(positive)],
            ["Нейтральных (3)", str(neutral)],
            ["Отрицательных (1-2)", str(negative)],
            ["Средняя оценка", f"{mean_rating:.1f}"],
            ["Отчетов от сотрудников", str(len(waiter_reports))],
        ]

        stats_table = Table(stats_data, colWidths=[120 * mm, 50 * mm])
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#3498DB")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                    ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 1, HexColor("#BDC3C7")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ECF0F1"), HexColor("#FFFFFF")]),
                ]
            )
        )
        story.append(stats_table)
    else:
        story.append(Paragraph("Нет данных за период", styles["NormalRu"]))

    story.append(Spacer(1, 30))

    # AI СВОДКА
    if ai_summary:
        story.append(Paragraph("AI-сводка и рекомендации", styles["HeadingRu"]))
        for para in ai_summary.split("\n"):
            if para.strip():
                para = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(para, styles["NormalRu"]))

    doc.build(story)
    return buffer.getvalue()
