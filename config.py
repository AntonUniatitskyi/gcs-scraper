from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")


TRUSTED_DOMAINS = {
    'bbc.com', 'reuters.com', 'pravda.com.ua', 'nv.ua',
    'liga.net', 'suspilne.media', 'radiosvoboda.org', 'bank.gov.ua', 'minfin.com.ua'
}

FAKE_DOMAINS = {
    'ria.ru', 'tass.ru', 'rt.com', 'bankofkazan.ru', 'sberbank.ru', 'nationalbank.kz', 'primbank.ru', 'cbr.ru'
    # (дополнишь сам)
}

PLATFORM_DOMAINS = {
    'facebook.com', 'twitter.com', 't.me', 'youtube.com',
    'blogspot.com', 'livejournal.com', 'teletype.in'
}

CLICKBAIT_TRIGGERS = {
    # Триггер-слова
    'шок',
    'сенсация',
    'скандал',
    'узнай',
    'вы не поверите',
    'раскрыты',
    'секрет',
    'только у нас',
    'подробности',
}
