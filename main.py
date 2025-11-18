from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from loguru import logger
import argparse
from logger_config import setup_logger
import page_parser as parser
import asyncio


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
    args = arg_parser.parse_args()
    query = args.query
    num_results = args.num
    logger.info(f"Запуск с запросом: '{query}' (результатов: {num_results})")
    try:
        client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
    except ValueError:
        logger.critical("Запуск невозможен: нет ключей API.")
        return

    results_data = client.search(query, num_results=num_results)
    if results_data:
        for item in results_data["items"]:
            print(f"\nНазвание: {item['title']}")
            print(f"Ссылка: {item['link']}")
            print(f"Фрагмент: {item['snippet']}")
            print("-" * 30)
        asyncio.run(parser.run_parser(results_data))

    logger.info("Приложение завершило работу.")


if __name__ == "__main__":
    main()
