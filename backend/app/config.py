"""Configuração da aplicação carregada de variáveis de ambiente.

Segredos nunca ficam no código: vêm do ``.env`` (local) ou das variáveis de
ambiente do provedor (produção).
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação.

    Attributes:
        ENV: Ambiente atual ("development" ou "production").
        SUPABASE_URL: URL do projeto Supabase.
        SUPABASE_JWT_SECRET: Segredo HS256 legado. Vazio usa o JWKS assimétrico.
        SUPABASE_JWT_AUDIENCE: Audience esperada nos tokens de usuário.
        DATABASE_URL: Connection string do Postgres (Session pooler).
        GOOGLE_CLIENT_ID: Client ID do OAuth do Google.
        GOOGLE_CLIENT_SECRET: Client secret do OAuth do Google.
        TOKEN_ENCRYPTION_KEY: Chave Fernet para cifrar os refresh tokens.
        CRON_SECRET: Segredo compartilhado com o cron do GitHub Actions.
        FRONTEND_ORIGINS: Origens liberadas no CORS, separadas por vírgula.
        APP_TIMEZONE: Fuso usado no rollover de sábado e na alocação.
        MAX_UPLOAD_BYTES: Tamanho máximo de upload aceito.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENV: str = "development"

    SUPABASE_URL: str = ""
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    DATABASE_URL: str = ""

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    TOKEN_ENCRYPTION_KEY: str = ""

    CRON_SECRET: str = ""

    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    APP_TIMEZONE: str = "America/Sao_Paulo"

    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024

    @property
    def cors_origins(self) -> List[str]:
        """Origens de CORS normalizadas (sem espaços nem barra final).

        A normalização faz a origem casar com a que o navegador envia
        (ex.: "https://app.vercel.app", sem barra ao final).
        """
        origins = []
        for o in self.FRONTEND_ORIGINS.split(","):
            o = o.strip().rstrip("/")
            if o:
                origins.append(o)
        return origins

    @property
    def is_production(self) -> bool:
        """Indica se a aplicação está em ambiente de produção."""
        return self.ENV.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única de :class:`Settings` (memoizada)."""
    return Settings()


settings = get_settings()
