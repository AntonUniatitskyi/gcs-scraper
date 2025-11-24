import os
import asyncio
from google import genai
from loguru import logger

async def generate_cynical_digest(articles_data: list, cynicism_level: int):
    valid_articles = [ a for a in articles_data if a.get('text_content')]
    if not valid_articles:
        return "⚠️ Нет данных для генерации дайджеста."

    context_text = ""
    for i, art in enumerate(valid_articles[:5]):
        context_text += f"\n=== ИСТОЧНИК {i+1}: {art.get('title')} ===\n{art['text_content'][:2000]}\n"

        style_instuction = ""

        if cynicism_level < 30:
            style_instruction = """
            Тон: Повествовательный, мягкий, контекстный.
            Задача: Расскажи историю. Объясни, почему это важно, какие эмоции это вызывает у сторон, дай бэкграунд.
            Можно использовать прилагательные и объяснять мнения аналитиков.
            """
        elif cynicism_level < 70:
            style_instruction = """
            Тон: Деловой, нейтральный, информационный.
            Задача: Напиши классическую новостную заметку (Who, What, Where, When, Why).
            Сбалансируй факты и контекст. Убери явную пропаганду, но оставь суть заявлений.
            """
        else:
            style_instruction = """
            Тон: ЭКСТРЕМАЛЬНО СУХОЙ, РОБОТИЗИРОВАННЫЙ, ФАКТОЛОГИЧЕСКИЙ.
            ЗАПРЕЩЕНО: Использовать прилагательные (ошеломляющий, страшный, великий), вводные слова, мнения, эмоции.
            ОСТАВИТЬ ТОЛЬКО: Даты, цифры, имена, конкретные действия (глаголы), геолокации.
            Формат: Маркированный список сухих фактов. Если факт не подтвержден цифрой или документом — пометь как "Заявление".
            Игнорируй "воду" и пиар-шум.
            """

        prompt = f"""
        Ты — редактор новостной ленты. Твоя задача — синтезировать одну сводку из нескольких источников.

        ВХОДНЫЕ ДАННЫЕ:
        {context_text}

        НАСТРОЙКИ ГЕНЕРАЦИИ:
        Уровень фильтрации "шума": {cynicism_level}/100.
        {style_instruction}

        Напиши сводку на русском языке. Используй Markdown.
        """

        try:
            client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if response.text:
                return response.text
        except Exception as e:
            logger.error(f"Ошибка генерации дайджеста: {e}")
            return f"Ошибка AI: {e}"
