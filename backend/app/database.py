"""Camada de acesso ao banco (SQLAlchemy).

O backend é o único tier confiável: conecta no Postgres da Supabase e é
responsável por SEMPRE filtrar por user_id. As policies de RLS no banco
(ver db/schema.sql) são uma segunda camada de defesa, caso alguém tente
acessar via anon key / PostgREST.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


# pool_pre_ping evita conexões mortas no free tier que dorme.
engine = create_engine(
    settings.DATABASE_URL or "postgresql+psycopg2://localhost/placeholder",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
