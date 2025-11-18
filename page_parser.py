import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import csv
import json
from config import TRUSTED_DOMAINS, FAKE_DOMAINS, PLATFORM_DOMAINS, CLICKBAIT_TRIGGERS
from loguru import logger
import dateparser
from newspaper import Article

def get_domain_rating(url):
    try:
        domain = urlparse(url).netloc
        # Убираем 'www.' для универсальности
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

def save_report(report_data):
    if not report_data:
        logger.warning("Нет данных для сохранения отчета.")
        return

    try:
        with open("report.json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=4)
        logger.success("Отчет сохранен в report.json")
    except Exception as e:
        logger.error(f"Ошибка при сохранении отчета: {e}")

    try:
        fieldnames = report_data[0].keys()
        with open("report.csv", "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_data)
        logger.success("Финальный отчет сохранен в report.csv")
    except Exception as e:
        logger.error(f"Ошибка сохранения CSV: {e}")

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

async def fetch_and_parse_url(client: httpx.AsyncClient, url: str) -> dict:
    logger.info(f"Обрабатываем: {url}")
    domain_rating = get_domain_rating(url)
    report_item = {
        'url': url,
        'title': None,
        'published_date': None,
        'rating': domain_rating,
        'status': 'Failed' # По умолчанию
    }
    try:
        response = await client.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        article = Article(url)
        article.set_html(response.text)
        article.parse()

        title = article.title
        if not title:
            logger.debug("Пробую найти заголовок вручную")
            title_tag = soup.find("title")
            h1_tag = soup.find("h1")
            title = title_tag.text.strip() if title_tag else (h1_tag.text.strip() if h1_tag else None)
        if title:
            logger.success(f"Название: {title}")
            report_item['title'] = title
        else:
            logger.warning("Название не найдено")

        sentiment_tag = analyze_title_sentiment(title)
        final_rating = f"{domain_rating}{sentiment_tag}"

        publish_date = article.publish_date
        if publish_date:
            iso_date = publish_date.isoformat()
            logger.success(f"Дата публикации: {iso_date}")
            report_item['published_date'] = iso_date
        else:
            logger.debug("Пробую найти дату вручную")
            raw_date_str = extract_date(soup)
            if raw_date_str:
                parsed_date = dateparser.parse(str(raw_date_str))
                if parsed_date:
                    iso_date = parsed_date.isoformat()
                    logger.success(f"Дата публикации: {iso_date}")
                    report_item['published_date'] = iso_date
                else:
                    logger.warning(f"Найдена строка даты, но не удалось разобрать: {raw_date_str}")
            else:
                logger.warning("Дата публикации не найдена")
        report_item['status'] = 'Success'
        logger.success(f"{final_rating}")
        print("\n")

    except Exception as e:
        logger.error(f"Не удалось загрузить {url}: {e}")
        report_item['status'] = f"Failed: {e}"
        print("\n")

    return report_item

async def run_parser(search_results_data):
    links = [item["link"] for item in search_results_data.get("items", [])]

    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Upgrade-Insecure-Requests': '1',
}

    tasks = []
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for url in links:
            tasks.append(fetch_and_parse_url(client, url))
        logger.info(f"Запускаю {len(tasks)} задач одновременно...")
        final_report_data = await asyncio.gather(*tasks)

    save_report(final_report_data)
