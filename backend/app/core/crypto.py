"""Criptografia simétrica para segredos guardados em repouso.

Usada para o refresh token do Google Calendar: nunca guardamos o token em
texto puro no banco. Se o banco vazar, os tokens continuam inúteis sem a
TOKEN_ENCRYPTION_KEY (que fica só nas variáveis de ambiente do servidor).
"""
from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY não configurada. "
            "Gere uma com: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Não foi possível descriptografar o segredo.") from exc
