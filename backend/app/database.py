"""Camada de acesso ao banco (SQLAlchemy).

O backend é o único tier confiável: conecta no Postgres da Supabase e sempre
filtra por ``user_id``. As policies de RLS (ver ``db/schema.sql``) são uma
segunda camada de defesa contra acesso via anon key / PostgREST.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Classe base declarativa dos modelos ORM."""


# pool_pre_ping revalida conexões ociosas (o free tier do banco hiberna).
engine = create_engine(
    settings.DATABASE_URL or "postgresql+psycopg2://localhost/placeholder",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão do banco por request e a fecha ao final.

    Yields:
        A sessão do SQLAlchemy, usada como dependência do FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
