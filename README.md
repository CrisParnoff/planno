# Planno

Aplicação web multi-tenant para organizar a semana de estudos de quem está se
preparando para o vestibular de medicina. Puxa a Google Agenda, distribui
tarefas automaticamente nos horários livres de estudo, gera relatórios de erros
a partir de planilhas e acompanha simulados.

> **Stack:** React + TypeScript (Vite) · FastAPI (Python) · PostgreSQL (Supabase) ·
> Supabase Auth (Google OAuth) · Google Calendar API · GitHub Actions (cron) · Docker.

<!-- Dica de portfólio: cole aqui um GIF de ~10s clicando em "Organizar" e as
     tarefas se distribuindo na agenda. É o que converte o recrutador. -->
<!-- ![demo](docs/demo.gif) -->

---

## Funcionalidades

- **Organizar semana (núcleo):** login com Google, leitura da agenda, visão
  semanal tipo Google Agenda, cadastro de tarefas (etiqueta + duração) e um
  botão **Organizar** que aloca as tarefas nos blocos de estudo — priorizando as
  de maior duração e **nunca** ocupando horário de aula.
- **Relatório de erros:** upload de planilha `.xlsx/.csv`, ranking decrescente
  por matéria, insights de foco, histórico e **comparação** entre dois relatórios.
- **Simulados:** registro de nome/questões/acertos com % automática e histórico.
- **Tela principal:** atalhos, data/hora, e a semana em modo acompanhamento (só checks).
- **Rollover de sábado:** todo sábado 00h01 (via GitHub Actions), pendências não
  concluídas são consolidadas; o que sobra vira "atrasado" na semana seguinte.

---

## Arquitetura e decisões

```
┌────────────┐    JWT (Bearer)     ┌──────────────┐   SQL     ┌─────────────┐
│  Frontend  │ ──────────────────► │   Backend    │ ────────► │  Postgres   │
│ React + TS │                     │   FastAPI    │           │  (Supabase) │
│ (Vercel)   │ ◄────── JSON ────── │ (Render)     │ ◄──────── │  + RLS      │
└─────┬──────┘                     └──────┬───────┘           └─────────────┘
      │ login Google (Supabase Auth)      │ Google Calendar API (readonly)
      ▼                                   ▼
  Supabase Auth                     Google Calendar
```

- **`week_start` sempre na segunda-feira.** Toda a modelagem de semana parte disso.
- **O status "atrasado" é DERIVADO na leitura** (função da data atual), não gravado.
  Assim o app nunca mente sobre o estado, mesmo que o cron falhe. O cron de sábado
  apenas **materializa** o movimento das tarefas (conveniência de UX).
- **Alocação = heurística gulosa** (first-fit decreasing), não um otimizador. Ordena
  por duração decrescente e encaixa no bloco compatível com menor sobra. Testada em
  `backend/tests/test_scheduling.py`.
- **Google Calendar é somente leitura** (`calendar.readonly`). Fonte de verdade das
  tarefas é o Postgres; da agenda de aulas, o Google. Sem sincronização bidirecional.

---

## Segurança

Multi-tenant com isolamento em **duas camadas**:

1. **Backend como tier confiável.** O frontend usa a Supabase apenas para login.
   **Todo** dado de aplicação passa pela API FastAPI, que:
   - valida a **assinatura** do JWT (JWKS assimétrico ou segredo HS256) — nada vindo
     do cliente é confiável;
   - extrai o `user_id` **de dentro do token** (nunca do corpo/query);
   - filtra **todas** as queries por esse `user_id`.
2. **RLS no banco (defense-in-depth).** Todas as tabelas têm Row Level Security com
   policy `auth.uid() = user_id`. Mesmo que a anon key pública seja usada via
   PostgREST, ninguém enxerga dados de outro usuário.

Outras medidas:

- **Whitelist de emails** (`allowed_emails`): só emails que você cadastrar conseguem
  usar o app; qualquer outro login é bloqueado com `403`.
- **Refresh token do Google criptografado** em repouso (Fernet). Se o banco vazar,
  os tokens são inúteis sem a `TOKEN_ENCRYPTION_KEY` (que fica só no servidor).
- **CORS restrito** às origens do frontend (nada de `*`).
- **Rate limiting** (120 req/min por IP) e **cabeçalhos de segurança** em toda resposta.
- **Endpoint de cron protegido** por segredo comparado em tempo constante (`hmac`).
- **Docs desativados em produção**; erros internos nunca vazam stack trace.

---

## Como rodar localmente (Docker Compose)

### Pré-requisitos
- Docker + Docker Compose
- Uma conta Supabase (grátis) e um projeto no Google Cloud (grátis)

### 1. Supabase
1. Crie um projeto em https://supabase.com.
2. No **SQL Editor**, cole e rode todo o `backend/db/schema.sql` (cria tabelas + RLS).
3. Em **Authentication → Providers → Google**, ative o provider (usaremos as
   credenciais do passo 2 do Google abaixo). Em **Scopes**, adicione:
   `https://www.googleapis.com/auth/calendar.readonly`.
4. Adicione você/namorada à whitelist (SQL Editor):
   ```sql
   insert into public.allowed_emails (email, note)
   values ('email-da-sua-namorada@gmail.com', 'usuária principal');
   ```
5. Anote em **Project Settings → API**: `Project URL`, `anon public key`, e o
   `JWT Secret` (aba API). Em **Database**, pegue a connection string (URI).

### 2. Google Cloud (Calendar API)
1. Em https://console.cloud.google.com crie um projeto.
2. **APIs & Services → Library:** ative a **Google Calendar API**.
3. **Credentials → Create Credentials → OAuth client ID → Web application.**
   - **Authorized redirect URIs:** adicione o callback da Supabase:
     `https://SEU-PROJETO.supabase.co/auth/v1/callback`
4. Copie o **Client ID** e **Client secret** (usados no backend e na Supabase).
5. Em **OAuth consent screen**, publique em **Production** com o escopo
   `calendar.readonly` (evita o refresh token expirar em 7 dias do modo Testing).

### 3. Variáveis de ambiente
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```
Preencha os dois `.env`. Gere as chaves que faltam:
```bash
# TOKEN_ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# CRON_SECRET
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 4. Subir
```bash
docker compose up --build
```
- Frontend: http://localhost:5173
- API + docs (dev): http://localhost:8000/docs

---

## Rodar sem Docker (opcional)

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Testes
```bash
cd backend
pytest            # motor de alocação (inclui o caso 60+15+15 no bloco de 90min)
```

---

## Cron de sábado (deploy)
O workflow `.github/workflows/saturday-rollover.yml` roda sábado 00h01 (BRT) e
chama `POST /internal/cron/rollover`. Em **Settings → Secrets → Actions** do seu
repositório, defina:
- `BACKEND_URL` — URL pública do backend (ex.: `https://seu-app.onrender.com`)
- `CRON_SECRET` — o mesmo valor do `.env` do backend

Também dá para disparar manualmente pela aba **Actions → Run workflow**.

---

## Estrutura
```
med-study-planner/
├── backend/
│   ├── app/
│   │   ├── core/        # excel, scheduling, google_calendar, planner_service, crypto
│   │   ├── routers/     # errors, simulados, labels, calendar, planner, cron
│   │   ├── security.py  # verificação de JWT + whitelist
│   │   ├── models.py    # SQLAlchemy
│   │   └── main.py      # app + CORS + rate limit + headers
│   ├── db/schema.sql    # tabelas + RLS + whitelist
│   └── tests/
├── frontend/
│   └── src/
│       ├── lib/         # supabase, api, auth, types, week
│       ├── components/  # Layout, WeekCalendar
│       └── pages/       # Home, Planner, Errors, Simulados, Login
├── .github/workflows/saturday-rollover.yml
└── docker-compose.yml
```
