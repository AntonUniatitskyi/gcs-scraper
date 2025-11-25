import feedparser
from loguru import logger

class TrendsClient:
    def __init__(self):
        self.rss_url = "https://news.google.com/rss?hl=ru&gl=UA&ceid=UA:ru"

    def get_top_trends(self, limit=5):
        logger.info(f"📰 Загружаю главные новости с Google News (UA/RU)...")

        try:
            feed = feedparser.parse(self.rss_url)

            trends = []
            if feed.entries:
                for entry in feed.entries:
                    clean_title = entry.title.split(" - ")[0]

                    if len(clean_title) > 10:
                        trends.append(clean_title)

                    if len(trends) >= limit:
                        break

            if not trends:
                logger.warning("RSS вернул пустой список.")
                return ["Война в Украине", "Курс доллара", "Ситуация на фронте"] # Fallback темы

            logger.success(f"Найдено тем: {len(trends)}")
            return trends

        except Exception as e:
            logger.error(f"Ошибка получения новостей: {e}")
            return []

# if __name__ == "__main__":
#     client = TrendsClient()
#     top_news = client.get_top_trends(limit=5)
#     print("\n🔥 ГОРЯЧИЕ ТЕМЫ СЕЙЧАС:")
#     for i, news in enumerate(top_news, 1):
#         print(f"{i}. {news}")
