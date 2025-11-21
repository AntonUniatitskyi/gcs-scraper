from fpdf import FPDF
import os
import re
from urllib.parse import urlparse

class PDFReport(FPDF):
    def header(self):
        self.set_fill_color(44, 62, 80) # Midnight Blue
        self.rect(0, 0, 210, 40, 'F')
        self.set_y(10)
        self.set_font('DejaVu', 'B', 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 15, 'AI News Analysis', ln=True, align='C')
        self.set_font('DejaVu', '', 10)
        self.set_text_color(200, 200, 200)
        self.cell(0, 5, 'Automated OSINT & Propaganda Detection Report', ln=True, align='C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Страница {self.page_no()} | Сгенерировано AI-Анализатором', align='C')

def clean_text_for_pdf(text):
    if not isinstance(text, str):
        return str(text)
    cleaned = "".join(c for c in text if ord(c) < 65536)
    replacements = {
        "–": "-", "—": "-", "“": '"', "”": '"',
        "«": '"', "»": '"', "…": "..."
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned

def clean_markdown(text):
    if not text: return ""
    text = text.replace('```markdown', '').replace('```', '')
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = text.replace('**', '').replace('__', '').replace('*', '')
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    return text.strip()

def create_pdf(query, articles, cross_check_text=None, filename="report.pdf"):
    pdf = PDFReport()
    pdf.set_auto_page_break(auto=True, margin=20)

    font_path = 'DejaVuSans.ttf'
    bold_font_path = 'DejaVuSans-Bold.ttf'

    try:
        pdf.add_font('DejaVu', '', font_path, uni=True)
        if os.path.exists(bold_font_path):
            pdf.add_font('DejaVu', 'B', bold_font_path, uni=True)
        else:
            pdf.add_font('DejaVu', 'B', font_path, uni=True)
        pdf.add_font('DejaVu', 'I', font_path, uni=True)
    except RuntimeError:
        pdf.set_font("Arial", size=12)

    pdf.add_page()

    pdf.set_font('DejaVu', '', 12)
    pdf.set_text_color(100, 100, 100)
    pdf.write(8, "Поисковый запрос: ")
    clean_query = clean_text_for_pdf(query)
    pdf.set_font('DejaVu', 'B', 14)
    pdf.set_text_color(0, 0, 0)
    pdf.write(8, f"{clean_query}")
    pdf.ln(15)

    if cross_check_text and "минимум 2" not in cross_check_text:
        pdf.set_font('DejaVu', 'B', 16)
        pdf.set_text_color(44, 62, 80)
        pdf.cell(0, 10, "Сводный Анализ (Cross-Check)", ln=True) # Убрал эмодзи из заголовка
        pdf.ln(5)

        # Очистка текста AI
        clean_text = clean_text_for_pdf(clean_markdown(cross_check_text))

        pdf.set_font('DejaVu', '', 11)
        pdf.set_text_color(50, 50, 50)
        start_y = pdf.get_y()
        pdf.multi_cell(0, 6, clean_text)
        end_y = pdf.get_y()
        pdf.set_draw_color(52, 152, 219)
        pdf.set_line_width(1.5)
        pdf.line(10, start_y, 10, end_y)
        pdf.set_line_width(0.2)
        pdf.ln(15)
    elif cross_check_text:
        pdf.set_font('DejaVu', 'I', 10)
        pdf.set_text_color(150, 50, 50)
        pdf.multi_cell(0, 6, "Сводный анализ не проведен: Недостаточно данных.")
        pdf.ln(10)

    pdf.set_font('DejaVu', 'B', 16)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 10, "Детальный разбор источников", ln=True)
    pdf.ln(5)
    valid_count = 0
    for item in articles:
        if not item: continue

        raw_title = item.get('title')
        if not raw_title or "Captcha" in raw_title or "Just a moment" in raw_title:
             continue

        title = clean_text_for_pdf(raw_title) # Чистим заголовок

        url = item.get('url', '')
        domain = urlparse(url).netloc.replace('www.', '')
        valid_count += 1
        pdf.set_font('DejaVu', 'B', 13)
        pdf.set_text_color(41, 128, 185)
        pdf.write(6, f"{valid_count}. {title}", link=url)
        pdf.ln(8)
        pdf.set_font('DejaVu', '', 9)
        pdf.set_text_color(128, 128, 128)
        short_url = url.replace('https://', '').replace('http://', '').replace('www.', '')
        if len(short_url) > 60:
            short_url = short_url[:60] + "..."

        pdf.cell(0, 5, f"Источник: {domain}  | {short_url}", link=url, ln=True)
        pdf.ln(3)
        rating = item.get('rating', '')
        pdf.set_font('DejaVu', 'B', 10)
        if "Высокое доверие" in rating:
            pdf.set_text_color(39, 174, 96); icon = "[+]" # Green Plus
        elif "Пропаганда" in rating or "Низкое доверие" in rating:
            pdf.set_text_color(192, 57, 43); icon = "[!]" # Red Exclamation
        elif "Платформа" in rating:
            pdf.set_text_color(243, 156, 18); icon = "[~]" # Yellow Tilde
        else:
            pdf.set_text_color(127, 140, 141); icon = "[?]" # Grey Question

        clean_rating = clean_text_for_pdf(rating.split('|')[0].strip())
        pdf.cell(0, 6, f"{icon} {clean_rating}", ln=True)
        ai_text = item.get('ai_analysis', '')
        if ai_text and len(ai_text) > 10 and "Пропущено" not in ai_text:
            pdf.ln(2)
            pdf.set_font('DejaVu', '', 10)
            pdf.set_text_color(44, 62, 80)
            clean_ai = clean_text_for_pdf(clean_markdown(ai_text))
            clean_ai = re.sub(r'SCORE:\s*\d+%?', '', clean_ai, flags=re.IGNORECASE).strip()
            if len(clean_ai) > 600: clean_ai = clean_ai[:600] + "..."
            pdf.set_x(15)
            pdf.multi_cell(0, 5, clean_ai)

        pdf.ln(5)
        pdf.set_draw_color(230, 230, 230)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    try:
        return pdf.output(dest='S').encode('latin-1')
    except AttributeError:
        return pdf.output()
