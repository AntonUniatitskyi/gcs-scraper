import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
import csv
import json
from config import TRUSTED_DOMAINS, FAKE_DOMAINS, PLATFORM_DOMAINS
from loguru import logger
import dateparser

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


def run_parser(search_results_data):

    links = [item["link"] for item in search_results_data.get("items", [])]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    final_report_data = []
    for url in links:
        logger.info(f"Обрабатываем: {url}")
        rating = get_domain_rating(url)
        report_item = {
            'url': url,
            'title': None,
            'published_date': None,
            'rating': rating,
            'status': 'Failed' # По умолчанию
        }
        try:
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            title_tag = soup.find("title")
            h1_tag = soup.find("h1")
            title = title_tag.text.strip() if title_tag else (h1_tag.text.strip() if h1_tag else None)
            if title:
                logger.success(f"Название: {title}")
            else:
                logger.warning("Название не найдено")
            raw_date_str = extract_date(soup)
            if raw_date_str:
                # А dateparser ее "нормализует"
                parsed_date = dateparser.parse(str(raw_date_str))
                if parsed_date:
                    logger.success(f"Дата публикации: {parsed_date.isoformat()}")
                    report_item['published_date'] = parsed_date.isoformat()
                else:
                    logger.warning(f"Найдена строка даты, но не удалось разобрать: {raw_date_str}")
            else:
                logger.warning("Дата публикации не найдена")
            report_item['status'] = 'Success'
            logger.success(f"{rating}")
            print("\n")

        except requests.RequestException as e:
            logger.error(f"Не удалось загрузить {url}: {e}")
            report_item['status'] = f"Failed: {e}"
            print("\n")

        # 7. Добавляем результат в общий список
        final_report_data.append(report_item)

    # 8. После окончания цикла - сохраняем всё
    save_report(final_report_data)
