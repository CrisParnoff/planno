# Planno

**Planno organiza a rotina de estudos de quem está na preparação para o
vestibular.** O app nasceu de um motivo pessoal: ajudar a minha namorada a
organizar a semana de estudos para medicina, distribuindo as tarefas nos
horários livres da agenda dela e mostrando, com clareza, onde ela mais erra
para saber o que revisar. Foi construído também pensando na possibilidade de os
colegas dela usarem — por isso é multiusuário, com acesso controlado por uma
lista de emails autorizados.

Na prática, o Planno responde a três perguntas do dia a dia de quem estuda para
o vestibular:

- **"O que eu estudo esta semana e quando?"** — cadastre as tarefas e o Planno
  as encaixa automaticamente nos seus horários de estudo.
- **"Onde eu mais erro?"** — o caderno de erros digital mostra, por matéria,
  qual assunto pesa mais (ex.: em Física, o que mais cai é Mecânica).
- **"Estou evoluindo?"** — simulados e a evolução de erros por semana mostram o
  progresso ao longo do tempo.

---

## Funcionalidades

- **Organizar semana:** visão da semana no estilo Google Agenda. Você reserva
  horários de estudo, cadastra tarefas (matéria + duração) e o botão
  **Organizar** aloca as tarefas nos blocos de estudo — priorizando as de maior
  duração e nunca ocupando horário de aula.
- **Relatório de erros (caderno de erros):** cada erro é registrado por questão
  (prova, data, matéria, assunto e tipo de erro). No topo aparecem os insights:
  matéria que mais precisa de atenção, assunto campeão de erros por matéria,
  distribuição por tipo de erro e evolução por semana. Há também uma seção
  "Refazer" para as questões pendentes.
- **Simulados:** registro de nome, questões e acertos, com percentual calculado
  automaticamente e histórico.
- **Tela principal:** atalhos, data/hora e a semana em modo acompanhamento.
- **Rollover de sábado:** toda semana, as pendências não concluídas são
  consolidadas na semana seguinte e marcadas como atrasadas.

---

## Stack

| Camada | Tecnologias |
| --- | --- |
| **Frontend** | React 18 + TypeScript, Vite, React Router, CSS próprio (tokens OKLCH; fontes Fraunces + Inter) |
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic, Uvicorn |
| **Banco de dados** | PostgreSQL (Supabase) com Row Level Security |
| **Autenticação** | Supabase Auth (login com Google) + verificação de JWT no backend |
| **Integração** | Google Calendar API (somente leitura) |
| **Infra / deploy** | Frontend na **Vercel**, backend na **Render** (Docker), banco/auth na **Supabase**, cron na **GitHub Actions** |

Resumo: **React/TS (Vite) na Vercel + FastAPI (Python) na Render + PostgreSQL na
Supabase**, com login Google, leitura da Google Agenda e um cron no GitHub
Actions para o rollover semanal.

---

## Como a Google Agenda deve estar organizada

O Planno **lê** a Google Agenda (nunca escreve nela) e decide o papel de cada
evento pelo **título**. Para o organizador funcionar bem, os eventos precisam
seguir esta convenção:

- **Aulas → título em MAIÚSCULAS** (ex.: `QUÍMICA`, `BIOLOGIA`).
  São blocos fixos: o Planno **nunca** aloca tarefas em cima de uma aula.
- **Horários de estudo → título em minúsculas** (ex.: `quimica`, `biologia`).
  São os espaços onde o Planno encaixa as tarefas. O título indica a matéria do
  bloco: uma tarefa de Química é alocada num bloco `quimica`.
- **Simulados → título contendo "simulado"** (ex.: `Simulado ENEM`).
  Aparecem destacados na visão da semana.
- **Outros compromissos → título misto** (ex.: `Academia`, `Consulta médica`).
  São tratados como ocupados: o Planno não aloca tarefas nesses horários, mas
  também não os trata como bloco de estudo.

Regras de alocação, em resumo:

1. Só entram tarefas nos **blocos de estudo** (títulos em minúsculas).
2. A matéria da tarefa precisa bater com a matéria do bloco (comparação sem
   acentos e sem diferença de maiúsculas). Tarefas sem matéria podem usar
   blocos genéricos.
3. Tarefas mais longas são alocadas primeiro (heurística *first-fit
   decreasing*), aproveitando melhor cada bloco.

> **Sem horários na Google Agenda?** Não tem problema. Dá para criar **blocos de
> estudo recorrentes dentro do próprio app** (na aba "Organizar semana"), e o
> organizador passa a usar esses blocos. Assim o Planno funciona mesmo para
> quem não mantém a agenda no Google.

---

## Acesso (whitelist)

O uso é restrito aos emails cadastrados na tabela `allowed_emails`. Quem loga
com um email não autorizado vê uma tela informando que não tem permissão e não
acessa nenhuma funcionalidade. Para liberar um novo usuário, basta inserir o
email nessa tabela.

---

## Arquitetura

```
┌────────────┐    JWT (Bearer)     ┌──────────────┐   SQL     ┌─────────────┐
│  Frontend  │ ──────────────────► │   Backend    │ ────────► │  Postgres   │
│ React + TS │                     │   FastAPI    │           │  (Supabase) │
│  (Vercel)  │ ◄────── JSON ────── │   (Render)   │ ◄──────── │   + RLS     │
└─────┬──────┘                     └──────┬───────┘           └─────────────┘
      │ login Google (Supabase Auth)      │ Google Calendar API (readonly)
      ▼                                   ▼
  Supabase Auth                     Google Calendar
```

Decisões de projeto:

- **O backend é o único tier confiável.** O frontend usa a Supabase apenas para
  o login; todo dado de aplicação passa pela API FastAPI, que valida a
  assinatura do JWT, extrai o `user_id` de dentro do token e filtra todas as
  consultas por ele. As policies de RLS no banco são uma segunda camada.
- **O estado "atrasado" é derivado na leitura** (em função da data), então o app
  nunca fica inconsistente mesmo que o cron falhe.
- **A alocação é uma heurística gulosa** (first-fit decreasing), testada em
  `backend/tests/test_scheduling.py`.
- **A Google Agenda é somente leitura.** A fonte de verdade das tarefas é o
  Postgres; das aulas, o Google. Não há sincronização de volta.

---

## Rodando localmente

Pré-requisitos: Docker + Docker Compose, uma conta Supabase e um projeto no
Google Cloud.

1. **Supabase:** crie o projeto, rode `backend/db/schema.sql` e
   `backend/db/migration_error_entries.sql` no SQL Editor, ative o provider
   Google (scope `calendar.readonly`) e cadastre seu email em `allowed_emails`.
2. **Variáveis de ambiente:** copie `backend/.env.example` e
   `frontend/.env.example` para `.env` e preencha.
3. **Suba tudo:**
   ```bash
   docker compose up --build
   ```
   - Frontend: http://localhost:5173
   - API (docs em dev): http://localhost:8000/docs

O passo a passo completo de deploy (Vercel + Render + GitHub Actions) está em
`DEPLOY.md`.

---

## Estrutura

```
planno/
├── backend/
│   ├── app/
│   │   ├── core/        # scheduling, planner_service, google_calendar, crypto, error_insights
│   │   ├── routers/     # auth, errors, simulados, labels, calendar, planner, cron
│   │   ├── security.py  # verificação de JWT + whitelist
│   │   ├── models.py    # modelos SQLAlchemy
│   │   └── main.py      # app + CORS + rate limit + headers
│   ├── db/              # schema.sql e migrações
│   └── tests/
├── frontend/
│   └── src/
│       ├── lib/         # supabase, api, auth, types, week
│       ├── components/  # Layout, WeekCalendar, Modal, dialogs, Logo
│       └── pages/       # Home, Planner, Errors, Simulados, Login, NoAccess
├── .github/workflows/   # cron do rollover de sábado
└── docker-compose.yml
```

---

## Testes

```bash
cd backend
pytest
```
