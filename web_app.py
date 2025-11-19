import streamlit as st
import asyncio
import sqlite3
import pandas as pd
import page_parser as parser
from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID

def color_rating(val):
    if 'Высокое доверие' in val:
        return 'background-color: #d4edda; color: #155724'  # Green
    elif 'Пропаганда' in val or 'Низкое доверие' in val:
        return 'background-color: #f8d7da; color: #721c24'  # Red
    elif 'Платформа' in val:
        return 'background-color: #fff3cd; color: #856404'  # Yellow
    return ''
st.set_page_config(page_title="Анализатор Новостей с AI", layout="wide")
st.title("🛡️ AI-Анализатор Новостей и Пропаганды")

def get_articles_from_db():
    conn = sqlite3.connect('data.db')
    query = "SELECT url, title, published_date, rating, ai_analysis, retrieved_at FROM articles ORDER BY retrieved_at DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

async def run_analysis(query, num_results):
    st.session_state.is_running = True
    st.session_state.report_data = None

    status_placeholder = st.empty()
    status_placeholder.info(f"🔎 Ищу {num_results} результатов для: **{query}**...")

    try:
        client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
        results_data = client.search(query, num_results, show_logs=False) # Отключаем логи в консоль
    except ValueError as e:
        status_placeholder.error(f"❌ Ошибка конфигурации: {e}")
        st.session_state.is_running = False
        return

    if not results_data or not results_data.get('items'):
        status_placeholder.warning("⚠️ Результаты поиска не найдены.")
        st.session_state.is_running = False
        return

    links_count = len(results_data['items'])
    status_placeholder.info(f"🔗 Найдено {links_count} ссылок. Запускаю анализ AI и парсинг...")
    final_report_data = await parser.run_parser(results_data, query, show_logs=False)
    st.session_state.report_data = final_report_data
    status_placeholder.success(f"✅ Анализ {links_count} статей завершен!")
    st.session_state.is_running = False

if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None

with st.sidebar:
    st.header("Параметры Поиска")
    search_query = st.text_input("Поисковый запрос", key="search_query")
    num_results = st.slider("Количество результатов", min_value=1, max_value=10, value=5, step=1, key="num_results")

    if st.button("🚀 Начать Анализ", disabled=st.session_state.is_running):
        if search_query:
            try:
                asyncio.run(run_analysis(search_query, num_results))
            except RuntimeError as e:
                if "cannot run" in str(e) or "There is no current event loop" in str(e):
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(run_analysis(search_query, num_results))
                else:
                    st.error(f"Асинхронная ошибка: {e}")

if st.session_state.report_data:
    st.subheader("📊 Результаты Текущего Анализа")
    df_report = pd.DataFrame(st.session_state.report_data)
    st.dataframe(
        df_report.style.applymap(color_rating, subset=['rating']),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large")
        }
    )

st.markdown("---")
st.subheader("📚 История Анализов (data.db)")
parser.setup_dtabase(show_logs=False)
df_history = get_articles_from_db()
if not df_history.empty:
    st.dataframe(
        df_history.style.applymap(color_rating, subset=['rating']),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large"),
            "retrieved_at": st.column_config.DatetimeColumn("Дата Анализа", format="YYYY-MM-DD HH:mm:ss")
        }
    )
else:
    st.info("База данных пока пуста.")
