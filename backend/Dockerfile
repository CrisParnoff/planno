FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de sistema mínimas (psycopg2 já vem binário)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Roda como usuário não-root (boa prática de segurança)
RUN useradd -m appuser
USER appuser

# Respeita a porta injetada pelo provedor (Render usa $PORT); cai para 8000
# localmente (docker-compose). `exec` garante que o uvicorn receba os sinais.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
