"""Cliente somente-leitura da Google Calendar API.

Usa o refresh token do usuário (guardado criptografado) para obter um access
token e listar os eventos da semana de **todos os calendários visíveis** do
usuário (não só o principal), classificando cada evento pelo título:

* título em MAIÚSCULAS -> ``aula`` (bloco fixo, nunca sobrescrito);
* título em minúsculas -> ``estudo`` (bloco onde as tarefas são alocadas);
* contém "simulado" -> ``simulado``;
* misto/indefinido -> ``outro``.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime
from urllib.parse import quote

import httpx

from ..config import settings
from .scheduling import COMMON_SUBJECT_KEYS, normalize_subject

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"

# Cache de access tokens (sha256(refresh) -> (access, expira_em)). O token do
# Google vale ~1h; guardamos por menos para nunca usar um vencido, evitando um
# refresh (200-400 ms) a cada leitura da agenda.
_ACCESS_TOKEN_TTL = 3000  # segundos (~50 min)
_token_cache: dict[str, tuple[str, float]] = {}


class GoogleCalendarError(RuntimeError):
    """Falha ao renovar o acesso ou ler eventos do Google Calendar."""


def get_access_token(refresh_token: str) -> str:
    """Obtém um access token do Google, usando cache quando possível.

    Args:
        refresh_token: Refresh token OAuth já descriptografado.

    Returns:
        Um access token válido.

    Raises:
        GoogleCalendarError: Se a renovação do token falhar.
    """
    key = hashlib.sha256(refresh_token.encode()).hexdigest()
    hit = _token_cache.get(key)
    if hit is not None and hit[1] > time.time():
        return hit[0]

    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        resp = httpx.post(GOOGLE_TOKEN_URL, data=data, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GoogleCalendarError(
            "Falha ao renovar o acesso ao Google. Reconecte sua agenda."
        ) from exc
    token = resp.json()["access_token"]
    _token_cache[key] = (token, time.time() + _ACCESS_TOKEN_TTL)
    return token


def _looks_like_study(norm: str, subject_keys: frozenset[str]) -> bool:
    """Indica se um título minúsculo é de estudo.

    É estudo quando cita "estudo" ou contém, como palavra, o nome de alguma
    matéria (etiquetas do usuário + matérias comuns).
    """
    if "estudo" in norm:
        return True
    words = set(norm.split())
    keys = subject_keys | COMMON_SUBJECT_KEYS
    return any(sk in words for sk in keys)


def classify_event(
    title: str, subject_keys: frozenset[str] = frozenset()
) -> tuple[str, str | None]:
    """Classifica um evento pelo título.

    Regras (ignorando acentos):

    * contém "pendencias" -> ``pendencias`` (bloco de pendências do sábado);
    * título em minúsculas **com nome de matéria ou "estudo"** -> ``estudo``
      (inclui "simulado ...", que só recebe tarefas de simulado);
    * título em minúsculas sem matéria -> ``outro`` (não recebe tarefas);
    * título em MAIÚSCULAS com "simulado" -> ``simulado`` (sessão fixa);
    * título em MAIÚSCULAS -> ``aula`` (bloco fixo);
    * misto com "simulado" -> ``simulado``;
    * misto/indefinido -> ``outro``.

    Args:
        title: Título do evento na agenda.
        subject_keys: Matérias do usuário, já normalizadas.

    Returns:
        A tupla ``(kind, subject)``; ``subject`` é o título original quando
        relevante (senão ``None``).
    """
    t = (title or "").strip()
    if not t:
        return "outro", None
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return "outro", None

    norm = normalize_subject(t)
    if "pendencias" in norm:
        return "pendencias", t

    is_upper = all(c.isupper() for c in letters)
    is_lower = all(c.islower() for c in letters)

    if is_lower:
        if _looks_like_study(norm, subject_keys):
            return "estudo", t
        return "outro", t
    if is_upper:
        if "simulado" in norm:
            return "simulado", None
        return "aula", t
    if "simulado" in norm:
        return "simulado", None
    return "outro", t


def _list_calendar_ids(access_token: str) -> list[str]:
    """Lista os IDs dos calendários visíveis do usuário.

    Returns:
        IDs dos calendários com ``selected != false``; ``["primary"]`` como
        fallback se a listagem falhar ou vier vazia.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(CALENDAR_LIST_URL, headers=headers, timeout=15)
        resp.raise_for_status()
    except httpx.HTTPError:
        return ["primary"]
    ids = [
        item["id"]
        for item in resp.json().get("items", [])
        if item.get("id") and item.get("selected", True)
    ]
    return ids or ["primary"]


def _events_for_calendar(
    access_token: str,
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
    subject_keys: frozenset[str] = frozenset(),
) -> list[dict]:
    """Lista os eventos de um único calendário no intervalo informado.

    Raises:
        GoogleCalendarError: Se a leitura do calendário falhar.
    """
    url = CALENDAR_EVENTS_URL.format(calendar_id=quote(calendar_id, safe=""))
    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "250",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GoogleCalendarError("Falha ao ler eventos do Google Calendar.") from exc

    events = []
    for item in resp.json().get("items", []):
        start = item.get("start", {}).get("dateTime")
        end = item.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        title = item.get("summary", "")
        kind, subject = classify_event(title, subject_keys)
        events.append(
            {
                "id": item.get("id"),
                "title": title,
                "start": start,
                "end": end,
                "kind": kind,
                "subject": subject,
            }
        )
    return events


def list_week_events(
    refresh_token: str,
    time_min: datetime,
    time_max: datetime,
    subject_keys: frozenset[str] = frozenset(),
) -> list[dict]:
    """Lista os eventos de todos os calendários do usuário no intervalo.

    Args:
        refresh_token: Refresh token OAuth do usuário.
        time_min: Início do intervalo (datetime com timezone).
        time_max: Fim do intervalo (datetime com timezone).
        subject_keys: Matérias do usuário, para reconhecer blocos de estudo.

    Returns:
        Eventos de todos os calendários visíveis, cada um com ``id``, ``title``,
        ``start``, ``end``, ``kind`` e ``subject``. Eventos de dia inteiro são
        ignorados.

    Raises:
        GoogleCalendarError: Se a leitura de algum calendário falhar.
    """
    access_token = get_access_token(refresh_token)
    events: list[dict] = []
    for calendar_id in _list_calendar_ids(access_token):
        try:
            events.extend(
                _events_for_calendar(access_token, calendar_id, time_min, time_max, subject_keys)
            )
        except GoogleCalendarError:
            # Ignora um calendário problemático e mantém os demais.
            continue
    return events
