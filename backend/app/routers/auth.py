"""Checagem de acesso do usuário logado.

O frontend chama GET /api/me logo após o login. Como `get_current_user`
já valida o JWT e a whitelist, este endpoint só responde 200 para quem
está autorizado; para quem não está, devolve 403 (email fora da whitelist).
Assim o frontend sabe se mostra o app ou a tela de "sem permissão".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"email": user.email, "authorized": True}
