"""Configuração central da aplicação, carregada de variáveis de ambiente.

Nunca colocamos segredos no código. Tudo vem do .env (local) ou das
variáveis de ambiente do provedor (produção).
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Ambiente
    ENV: str = "development"

    # --- Supabase ---
    # URL do projeto, ex: https://xxxx.supabase.co
    SUPABASE_URL: str = ""
    # Segredo legado HS256 (Project Settings > API > JWT Secret).
    # Se vazio, a verificação usa o JWKS assimétrico (ES256/RS256).
    SUPABASE_JWT_SECRET: str = ""
    # Audience padrão dos tokens de usuário logado da Supabase.
    SUPABASE_JWT_AUDIENCE: str = "authenticated"

    # --- Banco (Postgres da Supabase) ---
    # Use a connection string do "Session pooler" ou "Direct connection".
    DATABASE_URL: str = ""

    # --- Google OAuth (para a Calendar API) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # --- Criptografia dos refresh tokens do Google (Fernet key base64 de 32 bytes) ---
    TOKEN_ENCRYPTION_KEY: str = ""

    # --- Segredo compartilhado para o cron do GitHub Actions chamar o endpoint interno ---
    CRON_SECRET: str = ""

    # --- CORS: origens do frontend permitidas (separadas por vírgula) ---
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Fuso horário usado para o cálculo do "sábado 00h01" e alocação.
    APP_TIMEZONE: str = "America/Sao_Paulo"

    # Limites de upload
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
