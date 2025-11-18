from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from loguru import logger
import argparse
from logger_config import setup_logger
import page_parser as parser
import asyncio
import sqlite3

def setup_dtabase(show_logs: bool):
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            title TEXT,
            published_date TEXT,
            rating TEXT,
            status TEXT,
            search_query TEXT,
            retrieved_at TEXT,
            ai_analysis TEXT
        )
        ''')
        conn.commit()
        cursor.close()
    except Exception as e:
        if show_logs:
            logger.critical(f"Не удалось создать базу данных: {e}")
        exit()

def main():
    setup_logger()
    arg_parser = argparse.ArgumentParser(description="Анализ и поиск статей по запросу.")
    arg_parser.add_argument(
        '-q', '--query',
        type=str,
        required=True,
        help="Поисковый запрос (в кавычках, если из нескольких слов)"
    )
    arg_parser.add_argument(
        '-n', '--num',
        type=int,
        default=5,
        help="Количество результатов для поиска (по умолчанию: 5)"
    )
    arg_parser.add_argument(
        '-l', '--logs',
        action='store_true',
        help="Включить режим логов (вместо красивых рамок)"
    )
    args = arg_parser.parse_args()
    query = args.query
    num_results = args.num
    show_logs = args.logs
    setup_dtabase(show_logs)
    if show_logs:
        logger.info(f"Запуск с запросом: '{query}' (результатов: {num_results})")
    else:
        print(f"🔎 Поиск: {query}...")
    try:
        client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
    except ValueError:
        logger.critical("Запуск невозможен: нет ключей API.")
        return
    results_data = client.search(query, num_results, show_logs)
    if results_data:
        asyncio.run(parser.run_parser(results_data, show_logs))
    if show_logs:
        logger.info("Приложение завершило работу.")


if __name__ == "__main__":
    main()
