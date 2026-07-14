"""Autenticação e autorização.

Fluxo:
1. O frontend faz login com Google via Supabase Auth e recebe um JWT.
2. Cada request para a nossa API manda esse JWT em `Authorization: Bearer <token>`.
3. Aqui validamos a ASSINATURA do token (não confiamos em nada do cliente):
   - Primeiro tentamos o segredo HS256 (SUPABASE_JWT_SECRET), se configurado.
   - Senão, buscamos as chaves públicas no JWKS da Supabase (ES256/RS256).
4. Extraímos o `sub` (user_id) e o `email` de dentro do token verificado.
5. Checamos a WHITELIST: só emails aprovados (tabela allowed_emails) passam.

O user_id NUNCA vem do corpo/params do request — sempre do token verificado.
Isso é o que garante o isolamento entre inquilinos (multi-tenant).
"""
import time
from typing import Any, Optional

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db

_JWKS_CACHE: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL = 3600  # 1h


class CurrentUser:
    """Representa o usuário autenticado e autorizado."""

    def __init__(self, user_id: str, email: str):
        self.id = user_id
        self.email = email


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_jwks() -> dict:
    now = time.time()
    if _JWKS_CACHE["keys"] and now - _JWKS_CACHE["fetched_at"] < _JWKS_TTL:
        return _JWKS_CACHE["keys"]
    if not settings.SUPABASE_URL:
        raise _unauthorized("Servidor sem SUPABASE_URL configurada.")
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _unauthorized("Não foi possível obter as chaves de verificação.") from exc
    keys = resp.json()
    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["fetched_at"] = now
    return keys


def _decode_token(token: str) -> dict:
    options = {"verify_aud": True}
    audience = settings.SUPABASE_JWT_AUDIENCE

    # Escolhemos o método de verificação pelo 'alg' do próprio token:
    #   HS256  -> segredo simétrico (JWT Secret legado)
    #   ES256/RS256 -> chaves públicas via JWKS (projetos com chaves novas)
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _unauthorized("Cabeçalho do token inválido.") from exc

    alg = header.get("alg", "")

    if alg == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            raise _unauthorized("Servidor sem SUPABASE_JWT_SECRET para tokens HS256.")
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=audience,
                options=options,
            )
        except JWTError as exc:
            raise _unauthorized("Token inválido.") from exc

    # Caminho assimétrico (ES256/RS256) via JWKS.
    jwks = _get_jwks()
    kid = header.get("kid")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        # Chave rotacionada? Invalida cache e tenta uma vez mais.
        _JWKS_CACHE["keys"] = None
        jwks = _get_jwks()
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        raise _unauthorized("Chave de verificação não encontrada.")

    try:
        return jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "ES256")],
            audience=audience,
            options=options,
        )
    except JWTError as exc:
        raise _unauthorized("Token inválido.") from exc


# Cache da whitelist: evita uma consulta ao Postgres em CADA request.
# TTL curto para que revogar um acesso tenha efeito rápido.
_WHITELIST_TTL = 300  # 5 min
_whitelist_cache: dict[str, tuple[bool, float]] = {}


def _is_whitelisted(db: Session, email: str) -> bool:
    """Só emails presentes e ativos na tabela allowed_emails podem usar o app."""
    key = email.lower()
    hit = _whitelist_cache.get(key)
    if hit is not None and hit[1] > time.time():
        return hit[0]

    row = db.execute(
        text(
            "SELECT 1 FROM public.allowed_emails "
            "WHERE lower(email) = lower(:email) AND is_active = true LIMIT 1"
        ),
        {"email": email},
    ).first()
    allowed = row is not None
    # Só cacheia o "positivo": negados continuam consultando (acesso recém-liberado
    # passa a valer na hora, sem esperar TTL).
    if allowed:
        _whitelist_cache[key] = (allowed, time.time() + _WHITELIST_TTL)
    return allowed


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("Cabeçalho Authorization ausente ou malformado.")

    token = authorization.split(" ", 1)[1].strip()
    claims = _decode_token(token)

    user_id = claims.get("sub")
    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email")
    if not user_id or not email:
        raise _unauthorized("Token sem identificação de usuário.")

    if not _is_whitelisted(db, email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu email não está autorizado a usar este app. "
            "Fale com o administrador.",
        )

    return CurrentUser(user_id=str(user_id), email=str(email))
