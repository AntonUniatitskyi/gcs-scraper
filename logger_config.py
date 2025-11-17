import sys
from loguru import logger
import os

def setup_logger():
    os.makedirs("logs", exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        colorize=True,
        format="<blue>[{time:HH:mm:ss}]</blue> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="DEBUG"
    )

    logger.add(
        "logs/app.log",
        rotation="1 MB",
        retention="10 days",
        compression="zip",
        level="INFO",
        encoding="utf-8"
    )

    logger.level("INFO", color="<blue>")
    logger.level("WARNING", color="<yellow>")
    logger.level("ERROR", color="<red>")
    logger.level("SUCCESS", color="<green>")
    logger.level("DEBUG", color="<white>")

    logger.info("Логгер успешно настроен.")
