"""Ponto de entrada da API (FastAPI).

Aplica, em toda a aplicação: CORS restrito às origens do frontend, rate
limiting (slowapi), compressão Gzip, cabeçalhos de segurança e ocultação da
documentação em produção.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .config import settings
from .routers import auth, calendar, cron, errors, labels, planner, simulados

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

app = FastAPI(
    title="Med Study Planner API",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Comprime respostas JSON acima de ~500 bytes.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Adiciona cabeçalhos de segurança a toda resposta."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Converte erros não tratados em 500 sem vazar detalhes internos."""
    return JSONResponse(status_code=500, content={"detail": "Erro interno."})


@app.get("/health", tags=["infra"])
def health():
    """Healthcheck usado pelo provedor de deploy."""
    return {"status": "ok", "env": settings.ENV}


app.include_router(auth.router)
app.include_router(errors.router)
app.include_router(simulados.router)
app.include_router(labels.router)
app.include_router(calendar.router)
app.include_router(planner.router)
app.include_router(cron.router)
