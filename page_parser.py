import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import csv
import json
import re
from config import TRUSTED_DOMAINS, FAKE_DOMAINS, PLATFORM_DOMAINS, CLICKBAIT_TRIGGERS
from loguru import logger
import dateparser
from newspaper import Article
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

console = Console()
genai.configure(api_key=os.getenv("GEMINI_KEY"))

def print_rich_card(item: dict):
    title = item.get('title') or "Без названия"
    url = item.get('url')
    rating = item.get('rating', '')
    date = item.get('published_date') or "Неизвестно"
    ai_text = item.get('ai_analysis')

    ai_score_display = ""
    if ai_text and "Пропущено" not in ai_text and "короткий" not in ai_text:
        # Ищем "85%", "100%", "5%" в тексте
        match = re.search(r'SCORE:\s*(\d{1,3})%', ai_text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            if score >= 80:
                ai_score_display = f" | [bold green]AI: {score}%[/bold green]"
            elif score >= 50:
                ai_score_display = f" | [bold yellow]AI: {score}%[/bold yellow]"
            else:
                ai_score_display = f" | [bold red]AI: {score}%[/bold red]"
            ai_text = re.sub(r'SCORE:\s*\d{1,3}%\s*', '', ai_text, flags=re.IGNORECASE).strip()

    border_style = "white"
    if "Высокое доверие" in rating:
        border_style = "green"
    elif "Низкое доверие" in rating or "Пропаганда" in rating:
        border_style = "red"
    elif "Платформа" in rating:
        border_style = "yellow"

    content = Table.grid(padding=(0, 1))
    content.add_column(style="bold white", justify="right")
    content.add_column(style="white")

    content.add_row("📅 Дата:", f"[cyan]{date}[/cyan]")
    content.add_row("🔗 URL:", f"[blue underline]{url}[/blue underline]")

    rating_colored = rating \
        .replace("Высокое доверие", "[bold green]Высокое доверие[/bold green]") \
        .replace("Пропаганда", "[bold red]Пропаганда[/bold red]") \
        .replace("Низкое доверие", "[bold red]Низкое доверие[/bold red]") \
        .replace("Платформа", "[yellow]Платформа[/yellow]") \
        .replace("Неизвестен", "[grey70]Неизвестен[/grey70]")

    content.add_row("🛡️ Рейтинг:", f"{rating_colored}{ai_score_display}")

    if ai_text and "Пропущено" not in ai_text and "короткий" not in ai_text:
        clean_text = ai_text.replace("**", "").replace("###", "").replace("\n", " ").strip()
        ai_preview = clean_text[:150] + "..."
        content.add_row("🤖 Мнение:", f"[italic grey70]{ai_preview}[/italic grey70]")

    panel = Panel(
        content,
        title=f"[bold]{title}[/bold]",
        subtitle=f"[dim]Источник: {urlparse(url).netloc}[/dim]",
        border_style=border_style,
        box=box.ROUNDED,
        expand=False
    )

    console.print(panel)

async def get_ai_analyzis(text: str) -> str:
    if not text or len(text) < 100:
        return None
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = f"""
    Проанализируй этот новостной текст.
    ВАЖНО: Твой ответ ОБЯЗАН начинаться строго с такой строки:
    SCORE: [число от 0 до 100]%
    Далее напиши краткий анализ:
    1. Причины оценки.
    2. Признаки манипуляций (если есть).
    3. Вердикт (1-2 предложения).

    Текст статьи:
    "{text[:3000]}"
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                wait_time = 20 + (attempt * 10)
                logger.warning(f"Лимит API (429). Жду {wait_time} сек и пробую снова...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Gemini Error: {e}")
                return f"Ошибка AI: {e}"
    return "Ошибка AI: Лимит исчерпан после 3 попыток"

def get_domain_rating(url):
    try:
        domain = urlparse(url).netloc
        if domain.startswith('www.'):
            domain = domain[4:]

        if domain in TRUSTED_DOMAINS:
            return "Рейтинг: Высокое доверие"
        if domain in FAKE_DOMAINS:
            return "Рейтинг: Низкое доверие / Пропаганда"
        if domain in PLATFORM_DOMAINS:
            return "Рейтинг: Платформа (Не СМИ)"

        return "Рейтинг: Неизвестен"
    except Exception:
        return "Рейтинг: Ошибка (невалидный URL)"

def extract_date(soup):
    time_tag = soup.find("time")
    if time_tag and time_tag.has_attr("datetime"):
        return time_tag["datetime"]

    meta_properties = [
        "article:published_time",
        "datePublished",
        "og:updated_time",
        "og:published_time",
        "pubdate"
    ]
    for prop in meta_properties:
        meta_tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
        if meta_tag and meta_tag.has_attr("content"):
            return meta_tag["content"]
    return None

def save_report(report_data, show_logs: bool):
    if not report_data:
        if show_logs:
            logger.warning("Нет данных для сохранения отчета.")
        return
    try:
        with open("report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=4)
        if show_logs:
            logger.success("Отчет сохранен в report.json")
    except Exception as e:
        if show_logs:
            logger.error(f"Ошибка при сохранении отчета: {e}")
        else:
            console.print(f"[red]❌ Ошибка JSON: {e}[/red]")

    try:
        fieldnames = report_data[0].keys()
        with open("report.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_data)
        if show_logs:
            logger.success("Финальный отчет сохранен в report.csv")
        else:
            console.print(f"\n[bold green]💾 Отчеты сохранены: report.json, report.csv[/bold green]")
    except Exception as e:
        if show_logs:
            logger.error(f"Ошибка сохранения CSV: {e}")
        else:
            console.print(f"[red]❌ Ошибка CSV: {e}[/red]")

def analyze_title_sentiment(title: str | None) -> str:
    if not title:
        return ""
    title_lower = title.lower()
    for trigger in CLICKBAIT_TRIGGERS:
        if trigger in title_lower:
            logger.debug(f"Найдено триггер-слово: '{trigger}'")
            return " (Кликбейт: Триггер-слово)"
    if '!!!' in title or '???' in title or '!?' in title:
        logger.debug("Найдена чрезмерная пунктуация")
        return " (Кликбейт: Пунктуация)"
    if title.isupper() and len(title) > 10:
        logger.debug("Заголовок написан в ALL CAPS")
        return " (Кликбейт: ALL CAPS)"
    return ""

async def fetch_and_parse_url(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore, show_logs: bool) -> dict:
    async with semaphore:
        if show_logs:
            logger.info(f"Обрабатываем: {url}")
        else:
            console.print(f"[grey50]⏳ Обработка: {urlparse(url).netloc}...[/grey50]")
        domain_rating = get_domain_rating(url)
        report_item = {
            'url': url,
            'title': None,
            'published_date': None,
            'rating': domain_rating,
            'status': 'Failed', # По умолчанию
            'ai_analysis': None
        }
        ai_score_short = ""
        try:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            article = Article(url)
            article.set_html(response.text)
            article.parse()

            if "youtube.com" in url or "youtu.be" in url:
                report_item['ai_analysis'] = "Пропущено (Видео контент)"
                if show_logs: logger.info("AI пропущен (YouTube)")
            elif not article.text or len(article.text) < 100:
                report_item['ai_analysis'] = "Текст слишком короткий для анализа"
                if show_logs: logger.warning("AI пропущен (Мало текста)")
            else:
                if show_logs: logger.info("Отправляю текст в AI...")
                ai_result = await get_ai_analyzis(article.text)
                if ai_result:
                    report_item['ai_analysis'] = ai_result
                    if show_logs: logger.success("AI анализ получен!")
                    match = re.search(r'(\d{1,3}%)', ai_result)
                    if match:
                        ai_score_short = f" | AI: {match.group(1)}"
                    await asyncio.sleep(2)

            title = article.title
            if not title:
                title_tag = soup.find("title")
                h1_tag = soup.find("h1")
                title = title_tag.text.strip() if title_tag else (h1_tag.text.strip() if h1_tag else None)
            if title and show_logs:
                logger.success(f"Название: {title}")
            else:
                if show_logs: logger.warning("Название не найдено")

            report_item['title'] = title
            sentiment_tag = analyze_title_sentiment(title)
            final_rating = f"{domain_rating}{sentiment_tag}{ai_score_short}"

            publish_date = article.publish_date
            if publish_date:
                iso_date = publish_date.isoformat()
                if show_logs: logger.success(f"Дата публикации: {iso_date}")
                report_item['published_date'] = iso_date
            else:
                if show_logs: logger.debug("Пробую найти дату вручную")
                raw_date_str = extract_date(soup)
                if raw_date_str:
                    parsed_date = dateparser.parse(str(raw_date_str))
                    if parsed_date:
                        iso_date = parsed_date.isoformat()
                        if show_logs: logger.success(f"Дата публикации: {iso_date}")
                        report_item['published_date'] = iso_date
                    else:
                        if show_logs: logger.warning(f"Найдена строка даты, но не удалось разобрать: {raw_date_str}")
                else:
                    if show_logs: logger.warning("Дата публикации не найдена")
            report_item['status'] = 'Success'
            if show_logs:
                logger.success(f"{final_rating}")
                if report_item['published_date']:
                    logger.success(f"Дата: {report_item['published_date']}")
                print("\n")
            else:
                print_rich_card(report_item)

        except Exception as e:
            if show_logs:
                logger.error(f"Не удалось загрузить {url}: {e}")
            else:
                console.print(f"[red]❌ Ошибка {urlparse(url).netloc}: {e}[/red]")
            report_item['status'] = f"Failed: {e}"
            print("\n")

        return report_item

async def run_parser(search_results_data, show_logs: bool):
    links = [item["link"] for item in search_results_data.get("items", [])]

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
}

    semaphore = asyncio.Semaphore(3)
    tasks = []
    if not show_logs:
        console.print(f"[bold cyan]🚀 Запуск анализа для {len(links)} ссылок...[/bold cyan]\n")
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for url in links:
            tasks.append(fetch_and_parse_url(client, url, semaphore, show_logs))
        if show_logs: logger.info(f"Запускаю {len(tasks)} задач одновременно...")
        final_report_data = await asyncio.gather(*tasks)

    save_report(final_report_data, show_logs)
