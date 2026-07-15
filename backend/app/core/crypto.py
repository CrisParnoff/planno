"""Criptografia simétrica (Fernet) para segredos em repouso.

Usada no refresh token do Google Calendar, que nunca é gravado em texto puro.
Sem a ``TOKEN_ENCRYPTION_KEY`` (mantida apenas nas variáveis de ambiente do
servidor), um vazamento do banco não expõe os tokens.
"""
from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


def _fernet() -> Fernet:
    """Cria o cifrador Fernet a partir da chave configurada.

    Raises:
        RuntimeError: Se ``TOKEN_ENCRYPTION_KEY`` não estiver configurada.
    """
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY não configurada. "
            "Gere uma com: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """Cifra um texto e retorna o token em base64."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Decifra um token Fernet.

    Args:
        token: Texto cifrado por :func:`encrypt`.

    Returns:
        O texto original.

    Raises:
        ValueError: Se o token for inválido ou tiver sido adulterado.
    """
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Não foi possível descriptografar o segredo.") from exc
