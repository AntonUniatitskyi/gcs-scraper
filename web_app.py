import streamlit as st
import asyncio
import sqlite3
import pandas as pd
import page_parser as parser
from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from database import DatabaseHandler
import plotly.express as px

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

db = DatabaseHandler()

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
    st.markdown("---")
    st.subheader("📊 Статистика Базы")

    stats = db.get_stats()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Всего статей", stats['total'])
    with col2:
        st.metric("Доверенные", stats['trusted'])

    st.metric("Подозрительные / Пропаганда", stats['fake'], delta_color="inverse")

if st.session_state.report_data:
    st.subheader("📊 Результаты Текущего Анализа")
    df_report = pd.DataFrame(st.session_state.report_data)
    st.dataframe(
        df_report.style.applymap(color_rating, subset=['rating'] ), # type: ignore[attr-defined]
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large")
        }
    )

st.markdown("---")
st.subheader("📚 История Анализов (data.db)")
df_history = db.get_all_articles_df()
if not df_history.empty:
    st.dataframe(
        df_history.style.applymap(color_rating, subset=['rating']), # type: ignore[attr-defined]
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large"),
            "retrieved_at": st.column_config.DatetimeColumn("Дата Анализа", format="YYYY-MM-DD HH:mm:ss")
        }
    )
else:
    st.info("База данных пока пуста.")

df_history = db.get_all_articles_df()

if not df_history.empty:
    df_history['clean_rating'] = df_history['rating'].astype(str).apply(
        lambda x: x.split('|')[0].replace('Рейтинг:', '').split('(')[0].strip()
    )

    df_history['published_date'] = df_history['published_date'].astype(str)

    df_history['published_date_dt'] = pd.to_datetime(
        df_history['published_date'],
        errors='coerce',
        utc=True
    )

    df_history['date_parsed'] = df_history['published_date_dt'].dt.date

    st.markdown("### 📈 Визуализация данных")
    col1, col2 = st.columns(2)

    with col1:
        rating_counts = df_history['clean_rating'].value_counts().reset_index()
        rating_counts.columns = ['Тип источника', 'Количество']

        fig_pie = px.pie(
            rating_counts,
            values='Количество',
            names='Тип источника',
            title='Распределение источников',
            hole=0.4,
            color='Тип источника',
            color_discrete_map={
                'Высокое доверие': '#28a745',
                'Низкое доверие / Пропаганда': '#dc3545',
                'Платформа': '#ffc107',
                'Неизвестен': '#6c757d'
            }
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        valid_dates = df_history.dropna(subset=['date_parsed'])
        if not valid_dates.empty:
            date_counts = valid_dates['date_parsed'].value_counts().reset_index()
            date_counts.columns = ['Дата публикации', 'Количество статей']
            date_counts = date_counts.sort_values('Дата публикации')

            fig_bar = px.bar(
                date_counts,
                x='Дата публикации',
                y='Количество статей',
                title='Хронология публикаций',
                color_discrete_sequence=['#3498db']
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Недостаточно данных с датами для построения графика.")
else:
    st.info("База данных пока пуста.")
