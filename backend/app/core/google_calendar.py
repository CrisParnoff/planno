"""Cliente mínimo da Google Calendar API (somente leitura).

Usa o refresh token do usuário (guardado criptografado) para obter um access
token e listar os eventos da semana. Classifica cada evento:
  * TÍTULO EM MAIÚSCULAS  -> 'aula'    (bloco fixo, não pode ser sobrescrito)
  * título em minúsculas   -> 'estudo'  (bloco onde o algoritmo aloca tarefas)
  * contém 'simulado'      -> 'simulado'
  * misto/indefinido       -> 'outro'
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime

import httpx

from ..config import settings

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Cache de access tokens do Google. O access token vale ~1h; guardamos por
# um pouco menos para nunca usar um já vencido. Isso evita um round-trip de
# refresh (200-400ms) a CADA leitura da agenda — o principal gargalo do app.
_ACCESS_TOKEN_TTL = 3000  # ~50 min
_token_cache: dict[str, tuple[str, float]] = {}  # sha256(refresh) -> (access, expira_em)


class GoogleCalendarError(RuntimeError):
    pass


def get_access_token(refresh_token: str) -> str:
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
    """Retorna (kind, subject). subject é o título normalizado quando relevante."""
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
    """Lista eventos entre time_min e time_max (datetimes com timezone)."""
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
            continue  # ignora eventos de dia inteiro
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
