from search_client import SearchClient
from config import API_KEY, SEARCH_ENGINE_ID
from loguru import logger
import argparse
from logger_config import setup_logger
import page_parser as parser
import asyncio
import subprocess
from database import DatabaseHandler
from rich.console import Console
from rich.markdown import Markdown
from report_generator import create_pdf


def main():
    console = Console()
    setup_logger()
    db = DatabaseHandler()
    arg_parser = argparse.ArgumentParser(description="Анализ и поиск статей по запросу.")
    arg_parser.add_argument(
        '-q', '--query',
        type=str,
        required=False,
        help="Поисковый запрос (в кавычках, если из нескольких слов)"
    )
    arg_parser.add_argument(
        '-n', '--num',
        type=int,
        default=5,
        help="Количество результатов для поиска (по умолчанию: 5)"
    )
    arg_parser.add_argument(
        '-l', '--logs',
        action='store_true',
        help="Включить режим логов (вместо красивых рамок)"
    )
    arg_parser.add_argument(
        '-w', '--web',
        action='store_true',
        help="Открыть веб-интерфейс после выполнения поиска"
    )
    arg_parser.add_argument(
        '-cc', '--cross-check',
        action='store_true',
        help="Выполнить сводный AI-анализ (Cross-Check) по найденным статьям"
    )
    arg_parser.add_argument(
        '-r', '--report',
        action='store_true',
        help="Сохранить результат в PDF"
    )
    args = arg_parser.parse_args()
    query = args.query
    num_results = args.num
    show_logs = args.logs
    if args.web:
        if show_logs: logger.info("Запуск веб-интерфейса Streamlit...")
        subprocess.run(["streamlit", "run", "web_app.py"])
        return

    if show_logs:
        logger.info(f"Запуск с запросом: '{query}' (результатов: {num_results})")
    else:
        print(f"🔎 Поиск: {query}...")

    try:
        client = SearchClient(API_KEY, SEARCH_ENGINE_ID)
    except ValueError:
        logger.critical("Запуск невозможен: нет ключей API.")
        return
    results_data = client.search(query, num_results, show_logs)
    if results_data:
        final_data = asyncio.run(parser.run_parser(results_data, query, show_logs))
        report_text = None
        if args.cross_check:
            if not show_logs:
                console.print("\n[bold yellow]⚔️ Запуск сводного анализа (Cross-Check)...[/bold yellow]")
                console.print("[dim]AI читает тексты и ищет противоречия...[/dim]")
            else:
                logger.info("Запуск сводного анализа...")

            try:
                report_text = asyncio.run(parser.get_cross_check_analysis(final_data))
                console.print("\n")
                console.rule("[bold green]📊 СВОДНЫЙ ОТЧЕТ AI[/bold green]")
                console.print(Markdown(report_text))
                console.rule("[bold green]КОНЕЦ ОТЧЕТА[/bold green]")
                console.print("\n")
            except Exception as e:
                logger.error(f"Ошибка кросс-анализа: {e}")

        if args.report:
            console.print("[yellow]⏳ Генерация PDF...[/yellow]")
            try:
                # Если report_text равен None, PDF просто создастся без секции кросс-анализа
                pdf_bytes = create_pdf(query, final_data, report_text)

                filename = f"report_{query.replace(' ', '_')}.pdf"
                with open(filename, "wb") as f:
                    f.write(pdf_bytes)

                console.print(f"[bold green]✅ PDF отчет сохранен: {filename}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]❌ Ошибка создания PDF: {e}[/bold red]")
                if "ttf" in str(e).lower():
                    console.print("[dim]Подсказка: Проверьте, лежит ли файл DejaVuSans.ttf рядом с main.py[/dim]")

    if show_logs:
        logger.info("Приложение завершило работу.")


if __name__ == "__main__":
    main()
