"""Autenticação e autorização das requisições.

Fluxo por request:

1. O frontend faz login com Google (Supabase Auth) e recebe um JWT.
2. Cada request envia o JWT em ``Authorization: Bearer <token>``.
3. A assinatura do token é verificada — via segredo HS256
   (``SUPABASE_JWT_SECRET``) ou, na ausência dele, pelas chaves públicas do
   JWKS da Supabase (ES256/RS256).
4. ``sub`` (user_id) e ``email`` são extraídos do token verificado.
5. A whitelist (tabela ``allowed_emails``) é checada.

O ``user_id`` nunca vem do corpo ou dos params — sempre do token verificado —,
o que garante o isolamento entre usuários (multi-tenant).
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
_JWKS_TTL = 3600  # segundos (1h)


class CurrentUser:
    """Usuário autenticado e autorizado.

    Attributes:
        id: UUID do usuário (claim ``sub`` do token).
        email: Email do usuário.
    """

    def __init__(self, user_id: str, email: str):
        self.id = user_id
        self.email = email


def _unauthorized(detail: str) -> HTTPException:
    """Cria uma :class:`HTTPException` 401 padronizada."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _get_jwks() -> dict:
    """Retorna o JWKS da Supabase, com cache de 1h.

    Raises:
        HTTPException: 401 se a URL não estiver configurada ou o JWKS não puder
            ser obtido.
    """
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
    """Verifica a assinatura de um JWT e devolve suas claims.

    O algoritmo é escolhido pelo header do token: HS256 usa o segredo
    simétrico; ES256/RS256 usam as chaves públicas do JWKS.

    Args:
        token: JWT recebido no header ``Authorization``.

    Returns:
        As claims do token verificado.

    Raises:
        HTTPException: 401 se o token for inválido ou a chave não for encontrada.
    """
    options = {"verify_aud": True}
    audience = settings.SUPABASE_JWT_AUDIENCE

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

    jwks = _get_jwks()
    kid = header.get("kid")
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key is None:
        # Chave possivelmente rotacionada: invalida o cache e tenta de novo.
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


# Cache da whitelist para evitar uma consulta ao Postgres em cada request.
# Só o resultado positivo é cacheado, para que a liberação de um acesso passe a
# valer na hora (o negativo continua sendo consultado).
_WHITELIST_TTL = 300  # segundos (5 min)
_whitelist_cache: dict[str, tuple[bool, float]] = {}


def _is_whitelisted(db: Session, email: str) -> bool:
    """Indica se o email está ativo na tabela ``allowed_emails``.

    Args:
        db: Sessão do banco.
        email: Email extraído do token.

    Returns:
        ``True`` se o email estiver autorizado.
    """
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
    if allowed:
        _whitelist_cache[key] = (allowed, time.time() + _WHITELIST_TTL)
    return allowed


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Dependência do FastAPI que autentica e autoriza o usuário.

    Args:
        authorization: Header ``Authorization: Bearer <token>``.
        db: Sessão do banco.

    Returns:
        O :class:`CurrentUser` verificado.

    Raises:
        HTTPException: 401 se o token for inválido; 403 se o email não estiver
            na whitelist.
    """
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
