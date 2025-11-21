import streamlit as st
import asyncio
import pandas as pd
import page_parser as parser
from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from database import DatabaseHandler
import plotly.express as px
from report_generator import create_pdf

def color_rating(val):
    if not isinstance(val, str): return ''
    if 'Высокое доверие' in val:
        return 'background-color: #d4edda; color: #155724'  # Green
    elif 'Пропаганда' in val or 'Низкое доверие' in val:
        return 'background-color: #f8d7da; color: #721c24'  # Red
    elif 'Платформа' in val:
        return 'background-color: #fff3cd; color: #856404'  # Yellow
    return ''

st.set_page_config(page_title="Анализатор Новостей", page_icon="🛡️", layout="wide")
st.title("🛡️ AI-Анализатор Новостей и Пропаганды")

db = DatabaseHandler()

async def run_analysis(query, num_results):
    st.session_state.is_running = True
    st.session_state.report_data = None

    status_placeholder = st.empty()
    status_placeholder.info(f"🔎 Ищу {num_results} результатов для: **{query}**...")

    try:
        client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
        results_data = client.search(query, num_results, show_logs=False)
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
    st.header("🔍 Параметры")
    search_query = st.text_input("Поисковый запрос", key="search_query")
    num_results = st.slider("Количество результатов", 1, 10, 5)
    if st.button("🚀 Начать Анализ", disabled=st.session_state.is_running, type="primary"):
        if search_query:
            try:
                asyncio.run(run_analysis(search_query, num_results))
            except RuntimeError as e:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_analysis(search_query, num_results))
                loop.close()

    st.markdown("---")
    st.subheader("📊 Статистика Базы")
    stats = db.get_stats()
    col1, col2 = st.columns(2)
    col1.metric("Всего", stats['total'])
    col2.metric("Доверенные", stats['trusted'])
    st.metric("Подозрительные / Пропаганда", stats['fake'], delta_color="inverse")

if st.session_state.report_data:
    st.divider()
    st.subheader("📍 Результаты текущего поиска")

    df_report = pd.DataFrame(st.session_state.report_data)
    st.dataframe(
        df_report.style.map(color_rating, subset=['rating']),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large")
        }
    )

    st.markdown("#### ⚔️ Сводный анализ (Cross-Check)")

    with st.expander("ℹ️ Что это?", expanded=False):
        st.info("AI сравнит тексты только что найденных статей, найдет противоречия в фактах и манипуляции.")

    if st.button("✨ Сгенерировать сводный отчет"):
        current_data = st.session_state.get('report_data')

        if not current_data:
             st.error("Ошибка данных.")
        else:
            has_text = any(item.get('text_content') for item in current_data)
            if not has_text:
                st.error("⚠️ Нет текстов для анализа. Возможно, сайты заблокировали парсер.")
            else:
                cross_check_result = ""
                with st.spinner("🤖 AI читает статьи и ищет истину..."):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        cross_check_result = loop.run_until_complete(
                            parser.get_cross_check_analysis(current_data)
                        )
                        loop.close()

                        st.success("Готово!")
                        with st.container(border=True):
                            st.markdown(cross_check_result)

                            # pdf_data = create_pdf(
                            #     query=search_query,
                            #     articles=current_data,
                            #     cross_check_text=cross_check_result
                            # )

                            # st.download_button(
                            #     label="📄 Скачать PDF отчет",
                            #     data=pdf_data,
                            #     file_name="analysis_report.pdf",
                            #     mime="application/pdf",
                            #     type="primary"
                            # )
                    except Exception as e:
                        st.error(f"Ошибка кросс-анализа: {e}")
                if cross_check_result:
                    try:
                        with st.spinner("📄 Верстаю PDF отчет..."):
                            pdf_data = create_pdf(
                                query=search_query,
                                articles=current_data,
                                cross_check_text=cross_check_result
                            )

                        st.download_button(
                            label="📄 Скачать PDF отчет",
                            data=pdf_data,
                            file_name="analysis_report.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                    except IndexError:
                        st.error("❌ Ошибка структуры данных при создании PDF (IndexError).")
                        # st.warning("Совет: Скорее всего, проблема в report_generator.py при разбивке текста.")
                    except Exception as e:
                        st.error(f"❌ Ошибка создания PDF: {e}")
st.divider()
st.subheader("📚 История и Тренды (База данных)")

df_history = db.get_all_articles_df()

if not df_history.empty:
    df_history['clean_rating'] = df_history['rating'].astype(str).apply(
        lambda x: x.split('|')[0].replace('Рейтинг:', '').split('(')[0].strip()
    )

    df_history['published_date'] = df_history['published_date'].astype(str)
    df_history['published_date_dt'] = pd.to_datetime(df_history['published_date'], errors='coerce', utc=True)
    df_history['date_parsed'] = df_history['published_date_dt'].dt.date

    tab1, tab2 = st.tabs(["📈 Визуализация", "📋 Таблица истории"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            rating_counts = df_history['clean_rating'].value_counts().reset_index()
            rating_counts.columns = ['Источник', 'Кол-во']
            fig_pie = px.pie(
                rating_counts, values='Кол-во', names='Источник',
                title='Доверие к источникам', hole=0.4,
                color='Источник',
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
                date_counts.columns = ['Дата', 'Статей']
                date_counts = date_counts.sort_values('Дата')
                fig_bar = px.bar(
                    date_counts, x='Дата', y='Статей',
                    title='Хронология публикаций',
                    color_discrete_sequence=['#3498db']
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Мало данных с датами для графика.")

    with tab2:
        st.dataframe(
            df_history.style.map(color_rating, subset=['rating']),
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("URL", display_text="🔗"),
                "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large"),
                "retrieved_at": st.column_config.DatetimeColumn("Проверено", format="DD.MM.YYYY HH:mm")
            }
        )
else:
    st.info("История поиска пока пуста.")
