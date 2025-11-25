import asyncio
import logging
import sys
from os import getenv
from urllib.parse import urlparse
import re

from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold, hlink
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from config import TELEGRAM_TOKEN, API_KEY, SEARCH_ENGINE_ID
from search_client import SearchClient
import page_parser as parser
from aiogram.types import CallbackQuery
from database import DatabaseHandler

dp = Dispatcher()
db = DatabaseHandler()


async def keep_typing(chat_id: int, bot: Bot):
    try:
        while True:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Ошибка в typing loop: {e}")

@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    if not message.from_user:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇸 Выборы в США", callback_data="demo_usa"),
            InlineKeyboardButton(text="📈 Курс Биткоина", callback_data="demo_btc")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Как это работает?", callback_data="help")
        ]
    ])

    caption = (
        f"👋 <b>Привет, {html.quote(message.from_user.first_name)}!</b>\n\n"
        "Я — <b>AI-News Shield</b> 🛡️.\n"
        "Я читаю новости быстрее тебя и вижу то, что скрыто между строк.\n\n"
        "🤖 <b>Что я умею:</b>\n"
        "• Выявлять <b>фейки</b> и пропаганду.\n"
        "• Находить <b>первоисточники</b>.\n"
        "• Делать <b>выжимку</b> из десятков статей.\n\n"
        "👇 <b>Нажми на кнопку для теста или просто пришли мне ссылку/запрос!</b>"
    )
    try:
        photo = FSInputFile("welcome.png")
        await message.answer_photo(photo, caption=caption, reply_markup=kb)
    except Exception:
        await message.answer(caption, reply_markup=kb)

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    text = (
        "🧠 <b>Как это работает?</b>\n\n"
        "1. Ты отправляешь тему или ссылку.\n"
        "2. Я запускаю <b>Google Search</b> и нахожу топ-5 свежих статей.\n"
        "3. Мой движок скачивает тексты, обходя блокировки.\n"
        "4. <b>Gemini AI</b> анализирует текст на манипуляции, эмоциональную окраску и факты.\n\n"
        "<i>Просто напиши мне запрос, и я начну!</i>"
    )
    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data.startswith("demo_"))
async def demo_callback(callback: CallbackQuery, bot: Bot):
    if not callback.message:
        await callback.answer("Ошибка: сообщение не найдено.")
        return

    topic = "Выборы в США 2025" if callback.data == "demo_usa" else "Курс Биткоина прогнозы"

    await callback.message.answer(f"🚀 Запускаю демо-поиск по теме: <b>{topic}</b>")
    await callback.answer()

    real_message = callback.message

    class FakeMessage:
        text = topic
        chat = real_message.chat
        from_user = callback.from_user
        async def answer(self, text, **kwargs):
            return await real_message.answer(text, **kwargs)

    await analyze_message(FakeMessage(), bot)

@dp.message(F.text)
async def analyze_message(message: Message, bot: Bot) -> None:
    if not message.text:
        return

    user_query = message.text

    status_msg = await message.answer("🕵️ Анализирую... (15-20 сек)")
    typing_task = asyncio.create_task(keep_typing(message.chat.id, bot))

    try:
        final_data = []

        if user_query.startswith("http"):
            fake_search_results = {"items": [{"link": user_query, "title": "Проверка ссылки"}]}
            final_data = await parser.run_parser(fake_search_results, query="Link Check", show_logs=True)
        else:
            client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
            results_data = client.search(user_query, num_results=3, show_logs=True) # Можно увеличить до 5, раз мы фильтруем

            if not results_data or not results_data.get('items'):
                await status_msg.edit_text("⚠️ Ничего не найдено.")
                return

            final_data = await parser.run_parser(results_data, user_query, show_logs=True)

        if not final_data:
            await status_msg.edit_text("❌ Ошибка чтения данных.")
            return

        success_items = []
        failed_items = []

        for item in final_data:
            ai_text = item.get('ai_analysis')
            if ai_text and "слишком короткий" not in ai_text and "Пропущено" not in ai_text:
                success_items.append(item)
            else:
                failed_items.append(item)

        response_text = f"🔎 <b>Анализ:</b> {html.quote(user_query)}\n\n"
        if success_items:
            for item in success_items:
                url = item.get('url', '#')
                domain = urlparse(url).netloc.replace('www.', '')
                title = item.get('title')
                if not title or title == "Без заголовка":
                    title = f"Статья на {domain}"

                rating_raw = item.get('rating') or ""
                clean_rating = rating_raw.split('|')[0].replace("Рейтинг:", "").strip()

                icon = "❓"
                if "Высокое доверие" in clean_rating: icon = "✅"
                elif "Пропаганда" in clean_rating or "Низкое" in clean_rating: icon = "⛔"
                elif "Платформа" in clean_rating: icon = "⚠️"

                ai_text = item.get('ai_analysis', '')
                clean_ai = ai_text.replace("SCORE:", "").replace("###", "").replace("**", "").strip()
                if clean_ai[:4].isdigit() or clean_ai.startswith("Оценка"):
                     clean_ai = re.sub(r'^.*?%\s*', '', clean_ai)

                summary = clean_ai[:220] + "..."
                response_text += f"{icon} {hlink(title, url)}\n"
                response_text += f"<b>Источник:</b> {domain} | <b>{clean_rating}</b>\n"
                response_text += f"<blockquote>{html.quote(summary)}</blockquote>\n\n"
        else:
            response_text += "🤷‍♂️ <i>Детальный анализ невозможен (статьи закрыты или слишком короткие).</i>\n\n"

        if failed_items:
            response_text += "🔗 <b>Также найдено (без AI-анализа):</b>\n"
            for item in failed_items:
                url = item.get('url', '#')
                domain = urlparse(url).netloc.replace('www.', '')
                title = item.get('title') or domain
                response_text += f"• {hlink(title, url)} ({domain})\n"

        if len(response_text) > 4000:
            response_text = response_text[:4000] + "\n(обрезано)"

        await status_msg.edit_text(response_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Error: {e}")
        try: await status_msg.edit_text(f"❌ Ошибка: {e}")
        except: pass
    finally:
        typing_task.cancel()

async def main() -> None:
    bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform == "win32":
        pass
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
