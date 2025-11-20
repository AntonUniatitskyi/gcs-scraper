import datetime
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session, Mapped, mapped_column
from sqlalchemy.exc import IntegrityError
from loguru import logger
import pandas as pd

Base = declarative_base()

class ArticleModel(Base):
    __tablename__ = 'articles'

    url: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    published_date: Mapped[str | None] = mapped_column(String, nullable=True)
    rating: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    search_query: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_at: Mapped[str | None] = mapped_column(String, nullable=True)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatabaseHandler:
    _instance = None

    def __new__(cls, db_path="sqlite:///data.db"):
        if cls._instance is None:
            cls._instance = super(DatabaseHandler, cls).__new__(cls)
            cls._instance._initialize(db_path)
        return cls._instance

    def _initialize(self, db_path):
        self.engine = create_engine(db_path, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        logger.info("DatabaseHandler инициализирован (Singleton).")

    def get_session(self):
        return self.Session()

    def save_article(self, data: dict, query: str):
        session = self.get_session()
        try:
            article = session.query(ArticleModel).filter_by(url=data['url']).first()
            if not article:
                article = ArticleModel(url=data['url'])
                session.add(article)

            article.title = data.get('title')
            article.published_date = data.get('published_date')
            article.rating = data.get('rating')
            article.status = data.get('status')
            article.search_query = query
            article.retrieved_at = datetime.datetime.now().isoformat()
            article.ai_analysis = data.get('ai_analysis')

            session.commit()
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка ORM при сохранении: {e}")
            return False
        finally:
            session.close()


    def get_all_articles_df(self):
        try:
            query = "SELECT * FROM articles ORDER BY retrieved_at DESC"
            return pd.read_sql(query, self.engine)
        except Exception as e:
            logger.error(f"Ошибка чтения DataFrame: {e}")
            return pd.DataFrame()

    def get_stats(self):
        session = self.get_session()
        try:
            total = session.query(ArticleModel).count()
            trusted = session.query(ArticleModel).filter(ArticleModel.rating.ilike('%Высокое доверие%')).count()
            fake = session.query(ArticleModel).filter(
                (ArticleModel.rating.ilike('%Пропаганда%')) |
                (ArticleModel.rating.ilike('%Низкое доверие%'))
            ).count()

            return {"total": total, "trusted": trusted, "fake": fake}
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {"total": 0, "trusted": 0, "fake": 0}
        finally:
            session.close()
