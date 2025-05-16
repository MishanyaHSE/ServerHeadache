import csv
import io
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.utils.verification import SMTP_CONFIG

try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
except:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'arial.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'arialbd.ttf'))

def prepare_note_content(note):
    content = []
    content.append(f"Дата: {note.date.strftime('%d.%m.%Y')}")

    if note.is_headache:
        content.append("Головная боль: Да")

        if note.headache_time:
            content.append(f"Начало: {note.headache_time.strftime('%H:%M')}")

        if note.duration:
            content.append(f"Длительность: {note.duration}")

        if note.headache_type:
            content.append(f"Тип: {', '.join(note.headache_type)}")

        if note.area:
            content.append(f"Локализация: {', '.join(note.area)}")

        if note.intensity:
            content.append(f"Интенсивность: {note.intensity}/10")

        if note.triggers:
            content.append(f"Триггеры: {', '.join(note.triggers)}")

        if note.symptoms:
            content.append(f"Симптомы: {', '.join(note.symptoms)}")

        if note.medicine:
            meds = [f"{m.get('name', '')} ({m.get('weight', '')})"
                    for m in note.medicine if m.get('name')]
            if meds:
                content.append(f"Медикаменты: {', '.join(meds)}")

        pressure = []
        if note.pressure_morning_up or note.pressure_morning_down:
            pressure.append(f"Утро: {note.pressure_morning_up or '-'}/{note.pressure_morning_down or '-'}")
        if note.pressure_evening_up or note.pressure_evening_down:
            pressure.append(f"Вечер: {note.pressure_evening_up or '-'}/{note.pressure_evening_down or '-'}")
        if pressure:
            content.append("Артериальное давление: " + "; ".join(pressure))

        if note.comment:
            content.append(f"Примечания: {note.comment}")
    else:
        content.append("Головная боль: Нет")

    return content


def create_pdf(content):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y_position = 750
    title_font_size = 14
    date_font_size = 12
    regular_font_size = 10
    line_height = 16

    try:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
    except:
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'arial.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'arialbd.ttf'))

    if content:
        c.setFont("DejaVuSans-Bold", title_font_size)
        start_date = content[0].date.strftime('%d.%m.%Y')
        end_date = content[-1].date.strftime('%d.%m.%Y')
        header_text = f"Дневник головной боли: {start_date} - {end_date}"
        c.drawString(100, y_position, header_text)
        y_position -= line_height * 2

    for note in content:
        note_lines = prepare_note_content(note)

        if y_position < 60:
            c.showPage()
            y_position = 750

        c.setFont("DejaVuSans-Bold", date_font_size)
        c.drawString(100, y_position, note_lines[0])  # Дата
        y_position -= line_height

        c.setFont("DejaVuSans", regular_font_size)
        for line in note_lines[1:]:
            if y_position < 40:
                c.showPage()
                y_position = 750
                c.setFont("DejaVuSans", regular_font_size)

            c.drawString(110, y_position, f"•  {line}")  # Добавили маркеры
            y_position -= line_height

        y_position -= line_height // 2
        c.line(100, y_position, width - 100, y_position)
        y_position -= line_height

    c.save()
    buffer.seek(0)
    return buffer


def create_csv(notes):
    buffer = io.BytesIO()
    text_buffer = io.StringIO()
    writer = csv.writer(text_buffer, delimiter=',', quoting=csv.QUOTE_MINIMAL)

    headers = [
        'Дата',
        'Головная боль',
        'Время начала',
        'Длительность',
        'Тип боли',
        'Локализация',
        'Интенсивность',
        'Триггеры',
        'Симптомы',
        'Медикаменты',
        'Давление утро верхнее',
        'Давление утро нижнее',
        'Давление вечер верхнее',
        'Давление вечер нижнее',
        'Комментарий'
    ]
    writer.writerow(headers)

    for note in notes:
        medicine_str = ''
        if note.medicine:
            meds = []
            for m in note.medicine:
                name = m.get('name', '')
                if not name:
                    continue
                weight = m.get('weight', '')
                if weight:
                    meds.append(f"{name} ({weight})")
                else:
                    meds.append(name)
            medicine_str = ', '.join(meds)

        row = [
            note.date.strftime('%d.%m.%Y') if note.date else '',
            'Да' if note.is_headache else 'Нет',
            note.headache_time.strftime('%H:%M') if note.headache_time else '',
            note.duration or '',
            ', '.join(note.headache_type) if note.headache_type else '',
            ', '.join(note.area) if note.area else '',
            str(note.intensity) if note.intensity is not None else '',
            ', '.join(note.triggers) if note.triggers else '',
            ', '.join(note.symptoms) if note.symptoms else '',
            medicine_str,
            str(note.pressure_morning_up) if note.pressure_morning_up is not None else '',
            str(note.pressure_morning_down) if note.pressure_morning_down is not None else '',
            str(note.pressure_evening_up) if note.pressure_evening_up is not None else '',
            str(note.pressure_evening_down) if note.pressure_evening_down is not None else '',
            note.comment or ''
        ]
        writer.writerow(row)

    buffer.write(text_buffer.getvalue().encode('utf-8'))
    buffer.seek(0)
    return buffer


def send_report_to_email(recipient, pdf_buffer, format):
    try:
        msg = MIMEMultipart()
        msg['Subject'] = format.upper() + ' Report'
        msg['From'] = SMTP_CONFIG["user"]
        msg['To'] = recipient

        text = MIMEText("Please find attached the PDF report.")
        msg.attach(text)
        attachment = MIMEApplication(pdf_buffer.read(), _subtype=format)
        attachment.add_header('Content-Disposition', 'attachment', filename='report.' + format)
        msg.attach(attachment)

        with smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as server:
            server.starttls()
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.send_message(msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")


