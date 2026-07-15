"""Cliente somente-leitura da Google Calendar API.

Usa o refresh token do usuário (guardado criptografado) para obter um access
token e listar os eventos da semana, classificando cada evento pelo título:

* título em MAIÚSCULAS -> ``aula`` (bloco fixo, nunca sobrescrito);
* título em minúsculas -> ``estudo`` (bloco onde as tarefas são alocadas);
* contém "simulado" -> ``simulado``;
* misto/indefinido -> ``outro``.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime

import httpx

from ..config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

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


def classify_event(title: str) -> tuple[str, str | None]:
    """Classifica um evento pelo título.

    Args:
        title: Título do evento na agenda.

    Returns:
        A tupla ``(kind, subject)``, onde ``kind`` é um de
        ``aula``/``estudo``/``simulado``/``outro`` e ``subject`` é o título
        original quando relevante (senão ``None``).
    """
    t = (title or "").strip()
    if not t:
        return "outro", None
    low = t.lower()
    if "simulado" in low:
        return "simulado", None

    letters = [c for c in t if c.isalpha()]
    if not letters:
        return "outro", None

    is_upper = all(c.isupper() for c in letters)
    is_lower = all(c.islower() for c in letters)

    if is_upper:
        return "aula", t
    if is_lower:
        return "estudo", t
    return "outro", t


def list_week_events(refresh_token: str, time_min: datetime, time_max: datetime) -> list[dict]:
    """Lista os eventos da agenda no intervalo informado.

    Args:
        refresh_token: Refresh token OAuth do usuário.
        time_min: Início do intervalo (datetime com timezone).
        time_max: Fim do intervalo (datetime com timezone).

    Returns:
        Lista de eventos com ``id``, ``title``, ``start``, ``end``, ``kind`` e
        ``subject``. Eventos de dia inteiro são ignorados.

    Raises:
        GoogleCalendarError: Se a leitura da agenda falhar.
    """
    access_token = get_access_token(refresh_token)
    params = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": "250",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = httpx.get(CALENDAR_EVENTS_URL, params=params, headers=headers, timeout=20)
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
        kind, subject = classify_event(title)
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
