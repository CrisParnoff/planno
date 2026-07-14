# Deploy do Planno — passo a passo

Arquitetura em produção:

```
Vercel (frontend)  →  Render (API FastAPI)  →  Supabase (Postgres)
                          ↑
                 GitHub Actions (cron de sábado)
```

**Ordem recomendada** (por causa da dependência entre URLs):
Banco → Backend (Render) → Frontend (Vercel) → Amarrar CORS/Auth → Cron → Teste.

Você precisará ter a URL do backend para configurar o frontend, e a URL do
frontend para liberar o CORS do backend. Por isso: sobe o backend primeiro,
depois o frontend, e no fim volta no backend para ajustar o `FRONTEND_ORIGINS`.

---

## Passo 0 — Confirmar o banco (30 segundos)

O banco já está com as tabelas e o email autorizado. Só falta garantir que a
tabela nova do **caderno de erros** existe (ela foi adicionada depois).

No **SQL Editor** da Supabase, rode:

```sql
select to_regclass('public.error_entries');
```

- Se retornar `error_entries` → tudo certo, pule para o Passo 1.
- Se retornar `null` (vazio) → rode o arquivo `backend/db/migration_error_entries.sql` (cole o conteúdo no SQL Editor e execute).

Confira também que o login com Google está ativo:
**Authentication → Providers → Google** deve estar **Enabled**, com o Client ID
e Secret do Google e o scope `https://www.googleapis.com/auth/calendar.readonly`.

---

## Passo 1 — Os segredos já existem (é só copiar do `.env`)

Você **já preencheu todos os valores** durante o desenvolvimento. Eles estão em:

- `backend/.env` → todas as variáveis do backend (Supabase, banco, Google, chaves geradas)
- `frontend/.env` → `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

Para produção você **reutiliza os mesmos valores**. Só muda o seguinte:

1. `ENV` → passa de `development` para **`production`**.
2. `FRONTEND_ORIGINS` (backend) → passa a apontar para a URL da Vercel (Passo 4).
3. `VITE_API_URL` (frontend) → passa a apontar para a URL do Render (Passo 3).

Ou seja: as **únicas coisas que ainda não existem** são as duas URLs de deploy
(Render e Vercel) — elas só nascem quando você sobe cada serviço.

> **Não copie o `.env` para o repositório.** Ele é (e deve continuar) ignorado
> pelo Git. No Render e na Vercel os valores vão em "Environment Variables", não
> em arquivo. Abra os dois `.env` locais e copie de lá na hora de colar.

**Detalhes que já estão certos no seu `.env`:**
- O `DATABASE_URL` usa o **Session pooler** e a senha está URL-encoded
  (`%40` = `@`). Cole exatamente como está.
- Seu projeto usa o **JWT Secret legado (HS256)**, então `SUPABASE_JWT_SECRET`
  é **obrigatório** (não deixe vazio).
- `TOKEN_ENCRYPTION_KEY` e `CRON_SECRET` já foram gerados — reutilize os mesmos.
  O `CRON_SECRET` vai em DOIS lugares (Render e GitHub) e precisa ser idêntico.

---

## Passo 2 — Backend no Render

1. Crie conta em https://render.com e conecte sua conta do GitHub.
2. **New → Web Service** e selecione o repositório do projeto.
3. Configure:
   - **Root Directory:** `backend`
   - **Runtime/Language:** Docker (o Render detecta o `backend/Dockerfile`)
   - **Instance Type:** Free
   - **Health Check Path:** `/health`
4. Em **Environment → Environment Variables**, adicione (uma por uma):

   | Chave | Valor |
   |---|---|
   | `ENV` | `production` |
   | `SUPABASE_URL` | (do Passo 1) |
   | `SUPABASE_JWT_SECRET` | (do Passo 1, ou vazio) |
   | `DATABASE_URL` | (do Passo 1) |
   | `GOOGLE_CLIENT_ID` | (do Passo 1) |
   | `GOOGLE_CLIENT_SECRET` | (do Passo 1) |
   | `TOKEN_ENCRYPTION_KEY` | (gerado no Passo 1) |
   | `CRON_SECRET` | (gerado no Passo 1) |
   | `FRONTEND_ORIGINS` | `http://localhost:5173` *(provisório — ajustamos no Passo 4)* |
   | `APP_TIMEZONE` | `America/Sao_Paulo` |

5. Clique em **Create Web Service**. O primeiro build leva alguns minutos.
6. Quando ficar **Live**, teste no navegador: `https://SEU-BACKEND.onrender.com/health`
   → deve responder `{"status":"ok","env":"production"}`.
7. **Anote a URL do backend** (ex.: `https://planno-api.onrender.com`). Você vai
   usar no Passo 3.

> Observação: no plano Free, o serviço hiberna após ~15 min sem uso. A primeira
> chamada depois disso demora ~50s para "acordar" (inclusive a do cron). É normal.

---

## Passo 3 — Frontend na Vercel

1. Crie conta em https://vercel.com e conecte o GitHub.
2. **Add New → Project** e importe o mesmo repositório.
3. Configure:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite (deve ser detectado sozinho)
   - **Build Command:** `npm run build` (padrão)
   - **Output Directory:** `dist` (padrão)

   > Ignore o `frontend/Dockerfile` — ele é só do ambiente de desenvolvimento
   > (Vite dev server). A Vercel usa o build de produção nativo.

4. Em **Environment Variables** (deixe marcado *Production*):

   | Chave | Valor |
   |---|---|
   | `VITE_SUPABASE_URL` | mesmo valor de `SUPABASE_URL` |
   | `VITE_SUPABASE_ANON_KEY` | a anon key do Passo 1 |
   | `VITE_API_URL` | a URL do backend no Render (Passo 2), **sem barra no final** |

5. **Deploy.** Ao final, a Vercel te dá um domínio (ex.: `https://planno.vercel.app`).
   **Anote-o** para o Passo 4.

> Importante: as variáveis `VITE_*` são embutidas **no momento do build**. Se
> você mudar o `VITE_API_URL` depois, precisa fazer **Redeploy**.
>
> O build roda `tsc -b` (checagem de tipos do projeto inteiro). Se o deploy
> falhar com erro de tipo, me manda a saída que eu corrijo.

---

## Passo 4 — Amarrar CORS e Auth (fecha o circuito)

Agora que você tem o domínio da Vercel:

1. **Render → seu serviço → Environment:** edite `FRONTEND_ORIGINS` para o domínio
   exato da Vercel (ex.: `https://planno.vercel.app`), **sem barra no final**.
   Salve — o Render redeploya sozinho. *(Se tiver domínio próprio depois, adicione
   os dois separados por vírgula.)*
2. **Supabase → Authentication → URL Configuration:**
   - **Site URL:** o domínio da Vercel
   - **Redirect URLs:** adicione o domínio da Vercel (e mantenha
     `http://localhost:5173` para desenvolvimento)
3. **Google Cloud → OAuth consent screen:** confirme que está publicado em
   **Production** (no modo Testing o refresh token do Google expira em 7 dias).
   Em **Credentials**, o *Authorized redirect URI* deve conter o callback da
   Supabase: `https://SEU-PROJETO.supabase.co/auth/v1/callback`.

---

## Passo 5 — Cron de sábado (GitHub Actions)

O workflow já está pronto em `.github/workflows/saturday-rollover.yml` (roda
sábado 00h01 BRT e chama `POST /internal/cron/rollover`). Só falta dar os segredos:

1. No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
2. Crie os dois:
   - `BACKEND_URL` → a URL do Render (Passo 2), sem barra no final.
   - `CRON_SECRET` → **exatamente** o mesmo valor que está no Render.
3. Teste agora, sem esperar sábado: aba **Actions → "Rollover de sábado" →
   Run workflow**. O job deve terminar verde com **HTTP 200** e um JSON tipo
   `{"users_processed": N, "errors": 0}`.

---

## Passo 6 — Teste de ponta a ponta

Abra o domínio da Vercel e:

1. Faça login com o Google da sua namorada → deve autorizar a Google Agenda.
2. Em **Organizar semana**: arraste na agenda para criar um bloco de estudo,
   cadastre uma tarefa e clique em **Organizar** — deve encaixar a tarefa.
3. Marque a tarefa como feita (tem que responder na hora).
4. Em **Relatório de erros**: cadastre um erro e veja os insights no topo.
5. Em **Simulados**: registre um simulado.

---

## Se algo der errado

| Sintoma | Causa provável | Solução |
|---|---|---|
| Login volta com **403** | email fora da whitelist | conferir `allowed_emails` no banco |
| Tudo dá erro de **CORS** no console | `FRONTEND_ORIGINS` diferente do domínio da Vercel | igualar exatamente, sem barra final, e redeploy do Render |
| Backend não sobe no Render | porta | o `Dockerfile` já respeita `$PORT`; confira os logs do Render |
| **Relatório de erros** dá erro 500 | tabela `error_entries` não existe | rodar `migration_error_entries.sql` (Passo 0) |
| Agenda não aparece | Google OAuth em modo Testing / não reconectada | publicar consent em Production e reconectar a agenda |
| Cron falha | `BACKEND_URL`/`CRON_SECRET` errados | conferir os dois secrets do GitHub |

---

## Resumo dos segredos (onde cada um vai)

| Segredo | Backend (Render) | Frontend (Vercel) | GitHub Actions |
|---|:--:|:--:|:--:|
| `SUPABASE_URL` / `VITE_SUPABASE_URL` | ✅ | ✅ | |
| `VITE_SUPABASE_ANON_KEY` | | ✅ | |
| `SUPABASE_JWT_SECRET` | ✅ | | |
| `DATABASE_URL` | ✅ | | |
| `GOOGLE_CLIENT_ID` / `SECRET` | ✅ | | |
| `TOKEN_ENCRYPTION_KEY` | ✅ | | |
| `CRON_SECRET` | ✅ | | ✅ |
| `VITE_API_URL` (URL do Render) | | ✅ | |
| `BACKEND_URL` (URL do Render) | | | ✅ |
| `FRONTEND_ORIGINS` (URL da Vercel) | ✅ | | |
