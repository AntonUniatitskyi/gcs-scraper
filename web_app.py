import streamlit as st
import asyncio
import pandas as pd
import page_parser as parser
from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from database import DatabaseHandler
import plotly.express as px
from report_generator import create_pdf
import digest_generator  # Убедитесь, что этот файл создан рядом
from trends_client import TrendsClient

st.set_page_config(
    page_title="AI News Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def color_rating(val):
    if not isinstance(val, str): return ''
    if 'Высокое доверие' in val:
        return 'background-color: #d4edda; color: #155724'  # Green
    elif 'Пропаганда' in val or 'Низкое доверие' in val:
        return 'background-color: #f8d7da; color: #721c24'  # Red
    elif 'Платформа' in val:
        return 'background-color: #fff3cd; color: #856404'  # Yellow
    return ''

db = DatabaseHandler()

async def run_search_process(query, num_results):
    st.session_state.is_running = True
    st.session_state.report_data = None

    if 'last_cross_check' in st.session_state:
        del st.session_state['last_cross_check']
    if 'last_digest' in st.session_state:
        del st.session_state['last_digest']

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
    status_placeholder.info(f"🔗 Найдено {links_count} ссылок. Читаю и анализирую контент...")

    final_report_data = await parser.run_parser(results_data, query, show_logs=False)

    st.session_state.report_data = final_report_data
    status_placeholder.success(f"✅ Анализ {links_count} статей завершен!")
    st.session_state.is_running = False

async def run_daily_monitor():
    st.session_state.is_running = True
    st.session_state.report_data = [] # Очищаем старое

    # Очистка AI результатов
    if 'last_cross_check' in st.session_state: del st.session_state['last_cross_check']
    if 'last_digest' in st.session_state: del st.session_state['last_digest']

    status_box = st.empty()
    progress_bar = st.progress(0)

    try:
        status_box.info("📰 Читаю заголовки Google News...")
        # Получаем топ-3 темы (можно изменить limit в trends_client.py или передать аргумент)
        trends = TrendsClient().get_top_trends(limit=3)

        if not trends:
            status_box.error("Не удалось получить тренды.")
            st.session_state.is_running = False
            return

        all_articles = []
        search_client = SearchClient(API_KEY, SEARCH_ENGINE_ID)

        for i, topic in enumerate(trends):
            status_box.info(f"🕵️ Анализирую тему ({i+1}/{len(trends)}): **{topic}**")

            # Ищем по 2 статьи на каждую тему
            results = search_client.search(topic, num_results=2, show_logs=False)

            if results and results.get('items'):
                parsed = await parser.run_parser(results, topic, show_logs=False)
                # Добавляем пометку о теме, чтобы потом было понятно
                for item in parsed:
                    item['query_topic'] = topic
                all_articles.extend(parsed)

            # Обновляем прогресс
            progress_bar.progress((i + 1) / len(trends))

        st.session_state.report_data = all_articles
        status_box.success(f"✅ Готово! Собрано статей: {len(all_articles)}")

    except Exception as e:
        status_box.error(f"Ошибка мониторинга: {e}")

    st.session_state.is_running = False

# === ИНИЦИАЛИЗАЦИЯ SESSION STATE ===
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'report_data' not in st.session_state:
    st.session_state.report_data = None

# ==========================================
#                  SIDEBAR
# ==========================================
with st.sidebar:
    st.title("🛡️ AI-Scanner")
    st.markdown("---")

    st.header("🔍 Параметры")
    search_query = st.text_input("Поисковый запрос", key="search_query", placeholder="Например: Выборы в США")
    num_results = st.slider("Количество источников", 1, 10, 5)

    st.markdown("###")

    if st.button("🚀 Начать Анализ", disabled=st.session_state.is_running, type="primary", use_container_width=True):
        if search_query:
            try:
                # Запуск асинхронной функции в Streamlit
                asyncio.run(run_search_process(search_query, num_results))
            except RuntimeError:
                # Fallback для сложных event loops
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_search_process(search_query, num_results))
                loop.close()
        else:
            st.warning("Введите запрос.")

    st.markdown("---")
    st.header("🔥 Авто-Мониторинг")
    st.caption("Автоматический сбор главных новостей за 24 часа.")

    if st.button("🌍 Картина дня (UA)", disabled=st.session_state.is_running, use_container_width=True):
        try:
            asyncio.run(run_daily_monitor())
            st.rerun()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_daily_monitor())
            loop.close()
            st.rerun()
    st.subheader("📊 Статистика Базы")
    stats = db.get_stats()
    col1, col2 = st.columns(2)
    col1.metric("Всего", stats['total'])
    col2.metric("Доверенные", stats['trusted'])
    st.metric("⚠️ Фейки / Пропаганда", stats['fake'], delta_color="inverse")


st.title("📡 Центр Анализа Информации")
st.markdown("OSINT-инструмент для выявления манипуляций в СМИ.")

if st.session_state.report_data:
    st.divider()
    st.subheader("📍 Результаты сканирования")

    df_report = pd.DataFrame(st.session_state.report_data)

    st.dataframe(
        df_report.style.map(color_rating, subset=['rating']),
        use_container_width=True,
        column_config={
            "url": st.column_config.LinkColumn("URL", display_text="Открыть ссылку"),
            "title": st.column_config.TextColumn("Заголовок", width="medium"),
            "ai_analysis": st.column_config.TextColumn("AI Анализ", width="large"),
            "rating": st.column_config.TextColumn("Рейтинг", width="small"),
        },
        hide_index=True
    )

    st.markdown("###")

    with st.container(border=True):
        st.subheader("🧠 AI-Лаборатория")
        st.caption("Выберите режим глубокого анализа собранных данных")

        tab_check, tab_digest = st.tabs(["⚔️ Кросс-анализ (Поиск правды)", "📰 Умный Дайджест (Суть)"])

        with tab_check:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.info("🤖 AI сравнит тексты всех статей, найдет противоречия в цифрах, датах и выявит манипуляции.")
            with c2:
                st.write("") # Отступ
                btn_cross = st.button("⚔️ Сравнить источники", type="primary", use_container_width=True)

            if btn_cross:
                current_data = st.session_state.get('report_data')
                has_text = any(item.get('text_content') for item in current_data)

                if not has_text:
                    st.error("⚠️ Нет текстов для анализа. Сайты могли заблокировать парсер.")
                else:
                    with st.status("🕵️ AI читает статьи и ищет несостыковки...", expanded=True) as status:
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            res = loop.run_until_complete(parser.get_cross_check_analysis(current_data))
                            loop.close()

                            st.session_state['last_cross_check'] = res
                            status.update(label="✅ Анализ готов!", state="complete", expanded=False)
                        except Exception as e:
                            status.update(label="❌ Ошибка", state="error")
                            st.error(f"Ошибка: {e}")

            if 'last_cross_check' in st.session_state:
                st.markdown(st.session_state['last_cross_check'])
                st.markdown("---")
                col_pdf, _ = st.columns([1, 3])
                with col_pdf:
                    try:
                        pdf_bytes = create_pdf(
                            query=search_query,
                            articles=st.session_state.get('report_data'),
                            cross_check_text=st.session_state['last_cross_check']
                        )
                        st.download_button(
                            label="📄 Скачать PDF отчет",
                            data=pdf_bytes,
                            file_name="investigation_report.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.warning(f"Не удалось создать PDF: {e}")

        with tab_digest:
            c1, c2 = st.columns([3, 1])

            with c1:
                cynicism = st.slider(
                    "🎚️ Уровень цинизма (Фильтр шума)",
                    0, 100, 50,
                    format="%d%%"
                )
                if cynicism < 30:
                    st.caption("🎭 *Режим: Сторителлинг (Контекст, история, мнения)*")
                elif cynicism < 70:
                    st.caption("⚖️ *Режим: Информбюро (Баланс фактов и контекста)*")
                else:
                    st.caption("💀 *Режим: Сухой остаток (Только факты, без эмоций)*")

            with c2:
                st.write("")
                st.write("")
                btn_digest = st.button("⚡ Создать сводку", type="primary", use_container_width=True)

            if btn_digest:
                current_data = st.session_state.get('report_data')
                if not current_data:
                    st.error("Нет данных.")
                else:
                    with st.spinner(f"🔪 Вырезаю лишнее (Цинизм: {cynicism}%)..."):
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            digest_res = loop.run_until_complete(
                                digest_generator.generate_cynical_digest(current_data, cynicism)
                            )
                            loop.close()
                            st.session_state['last_digest'] = digest_res
                        except Exception as e:
                            st.error(f"Ошибка: {e}")

            if 'last_digest' in st.session_state:
                st.success("Дайджест сформирован!")
                with st.container(border=True):
                    st.markdown(st.session_state['last_digest'])

st.divider()
st.subheader("📚 Архив расследований")

df_history = db.get_all_articles_df()

if not df_history.empty:
    df_history['clean_rating'] = df_history['rating'].astype(str).apply(
        lambda x: x.split('|')[0].replace('Рейтинг:', '').split('(')[0].strip()
    )
    df_history['published_date'] = pd.to_datetime(df_history['published_date'], errors='coerce', utc=True)
    df_history['date_parsed'] = df_history['published_date'].dt.date

    tab_chart, tab_data = st.tabs(["📈 Визуализация", "📋 Таблица данных"])

    with tab_chart:
        col1, col2 = st.columns(2)
        with col1:
            rating_counts = df_history['clean_rating'].value_counts().reset_index()
            rating_counts.columns = ['Источник', 'Кол-во']
            fig_pie = px.pie(
                rating_counts, values='Кол-во', names='Источник',
                title='Репутация источников в базе', hole=0.4,
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
                    title='Динамика публикаций',
                    color_discrete_sequence=['#3498db']
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Недостаточно данных с датами для графика.")

    with tab_data:
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
