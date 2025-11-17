import requests
import json
from loguru import logger
import os


class SearchClient:
    def __init__(self, api_key, search_engine_id):
        self.api_key = api_key
        self.search_engine_id = search_engine_id

        if not self.api_key or not self.search_engine_id:
            logger.error("API_KEY или SEARCH_ENGINE_ID отсутствуют!")
            raise ValueError("Переменные среды не найдены")

        self.url = "https://www.googleapis.com/customsearch/v1"

    def search(self, query: str, num_results: int = 5):
        params = {
            'key': self.api_key,
            'cx': self.search_engine_id,
            'q': query,
            'num': num_results
        }

        logger.info(f"Выполняю поиск: '{query}'")
        response = None

        try:
            response = requests.get(self.url, params=params)
            response.raise_for_status()
            data = response.json()

            if 'items' not in data:
                logger.warning("Результаты не найдены.")
                return None

            logger.success(f"Найдено результатов: {len(data['items'])}")
            return data

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP ошибка: {e}")
            if response:
                logger.debug(response.text)

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса: {e}")

        return None

    def save_results(self, data, filename="results.json"):
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        logger.success(f"Результаты сохранены в {filename}")
