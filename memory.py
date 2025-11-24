import chromadb
from sentence_transformers import SentenceTransformer
import os
import uuid
from loguru import logger

class MemoryHandler:
    def __init__(self, db_path="chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="news_knowledge")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def add_article(self, article_data):
        if not article_data.get('text_content') or len(article_data['text_content']) < 100:
            return

        url = article_data.get('url')
        text = article_data.get('text_content')[:1000] # Берем первый кусок для индексации
        title = article_data.get('title') or "Без названия"
        date = article_data.get('published_date') or "Неизвестно"
        vector = self.model.encode(text).tolist()

        try:
            self.collection.upsert(
                documents=[text],
                embeddings=[vector],
                metadatas=[{"url": url, "title": title, "date": str(date)}],
                ids=[url] # URL как уникальный ID
            )
            logger.debug(f"💾 Запомнил статью: {title}")
        except Exception as e:
            logger.error(f"Ошибка памяти: {e}")

    def find_similar_context(self, query_text, n_results=3):
        if not query_text: return ""
        vector = self.model.encode(query_text).tolist()
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=n_results
        )

        context_str = ""
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                context_str += f"\n[Архив: {meta['date']} | {meta['title']}]\n{doc[:300]}...\n"

        return context_str
