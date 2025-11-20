from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from loguru import logger
import argparse
from logger_config import setup_logger
import page_parser as parser
import asyncio
import sqlite3
import subprocess
from database import DatabaseHandler


def main():
    setup_logger()
    db = DatabaseHandler()
    arg_parser = argparse.ArgumentParser(description="Анализ и поиск статей по запросу.")
    arg_parser.add_argument(
        '-q', '--query',
        type=str,
        required=False,
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
    arg_parser.add_argument(
        '-w', '--web',
        action='store_true',
        help="Открыть веб-интерфейс после выполнения поиска"
    )
    args = arg_parser.parse_args()
    query = args.query
    num_results = args.num
    show_logs = args.logs
    if args.web:
        if show_logs: logger.info("Запуск веб-интерфейса Streamlit...")
        subprocess.run(["streamlit", "run", "web_app.py"])
        return
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
        asyncio.run(parser.run_parser(results_data, query, show_logs))
    if show_logs:
        logger.info("Приложение завершило работу.")


if __name__ == "__main__":
    main()
