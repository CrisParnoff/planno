-- =====================================================================
--  Med Study Planner — schema do banco (Supabase / Postgres)
--  Rode este arquivo no SQL Editor da Supabase.
--
--  Modelo de segurança:
--   * O BACKEND (FastAPI) é o tier confiável e SEMPRE filtra por user_id.
--   * RLS abaixo é a SEGUNDA camada de defesa: mesmo que alguém use a
--     anon key pública / PostgREST, só enxerga as próprias linhas.
--   * O backend conecta com um papel que respeita RLS OU aplica os
--     filtros no código (ver app/security.py). As duas camadas juntas.
-- =====================================================================

-- Extensão para gerar UUIDs
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- WHITELIST: só emails aqui (is_active = true) conseguem usar o app.
-- Gerenciada por você (admin). Não tem RLS de usuário: é lida pelo
-- backend com papel de serviço e nunca exposta ao frontend.
-- ---------------------------------------------------------------------
create table if not exists public.allowed_emails (
    id          uuid primary key default gen_random_uuid(),
    email       varchar(320) not null unique,
    is_active   boolean not null default true,
    note        varchar(200),
    created_at  timestamptz not null default now()
);

alter table public.allowed_emails enable row level security;
-- Sem policies permissivas => ninguém acessa via anon/authenticated key.
-- Só o service_role (backend) enxerga. É exatamente o que queremos.

-- ---------------------------------------------------------------------
-- RELATÓRIOS DE ERROS
-- ---------------------------------------------------------------------
create table if not exists public.error_reports (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users(id) on delete cascade,
    name            varchar(200) not null,
    source_filename varchar(255),
    total_errors    integer not null default 0,
    items           jsonb not null default '[]'::jsonb,
    insights        jsonb not null default '[]'::jsonb,
    created_at      timestamptz not null default now()
);
create index if not exists idx_error_reports_user on public.error_reports(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- CADERNO DE ERROS (cada linha = um erro de uma questão)
-- Substitui a lógica antiga de upload agregado (error_reports).
-- ---------------------------------------------------------------------
create table if not exists public.error_entries (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    exam        varchar(120),                    -- Prova (opcional)
    error_date  date,                            -- Data em que fez a questão
    question    integer,                         -- Nº da questão (opcional)
    area        varchar(40),                     -- Grande área (opcional)
    subject     varchar(80)  not null,           -- Matéria (ex.: Física)
    topic       varchar(120) not null,           -- Assunto (ex.: Mecânica)
    error_type  varchar(20)  not null,           -- 'conteudo' | 'atencao' | 'interpretacao'
    redone      boolean      not null default false,
    redo_on     date,                            -- Refazer: data planejada (opcional)
    created_at  timestamptz  not null default now(),
    constraint error_type_valid
        check (error_type in ('conteudo', 'atencao', 'interpretacao'))
);
create index if not exists idx_error_entries_user_date on public.error_entries(user_id, error_date desc);
create index if not exists idx_error_entries_user_subject on public.error_entries(user_id, subject);
create index if not exists idx_error_entries_user_redo on public.error_entries(user_id, redone);

-- ---------------------------------------------------------------------
-- SIMULADOS
-- ---------------------------------------------------------------------
create table if not exists public.simulados (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references auth.users(id) on delete cascade,
    name           varchar(200) not null,
    num_questions  integer not null check (num_questions > 0),
    num_correct    integer not null check (num_correct >= 0),
    percent        numeric(5,2) not null,
    taken_on       date,
    created_at     timestamptz not null default now(),
    constraint correct_lte_questions check (num_correct <= num_questions)
);
create index if not exists idx_simulados_user on public.simulados(user_id, created_at desc);

-- ---------------------------------------------------------------------
-- LABELS (etiquetas / matérias)
-- ---------------------------------------------------------------------
create table if not exists public.labels (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    name        varchar(80) not null,
    color       varchar(20) not null default '#2d5f4f',
    created_at  timestamptz not null default now(),
    unique (user_id, name)
);
create index if not exists idx_labels_user on public.labels(user_id);

-- ---------------------------------------------------------------------
-- TAREFAS
-- ---------------------------------------------------------------------
create table if not exists public.tasks (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users(id) on delete cascade,
    label_id         uuid references public.labels(id) on delete set null,
    description      text not null,
    duration_min     integer not null check (duration_min > 0),
    week_start       date not null,
    scheduled_start  timestamptz,
    scheduled_end    timestamptz,
    status           varchar(20) not null default 'pending',
    is_late          boolean not null default false,
    rolled_from_week date,
    created_at       timestamptz not null default now()
);
create index if not exists idx_tasks_user_week on public.tasks(user_id, week_start);

-- ---------------------------------------------------------------------
-- CONEXÃO COM GOOGLE CALENDAR (refresh token criptografado)
-- ---------------------------------------------------------------------
create table if not exists public.calendar_connections (
    id                       uuid primary key default gen_random_uuid(),
    user_id                  uuid not null unique references auth.users(id) on delete cascade,
    refresh_token_encrypted  text not null,
    connected_at             timestamptz not null default now()
);

-- =====================================================================
--  RLS: ativa em todas as tabelas de dados do usuário.
--  Policy única por tabela: a linha só é visível/manipulável se
--  auth.uid() == user_id. auth.uid() vem do JWT verificado pela Supabase.
-- =====================================================================
do $$
declare
    t text;
begin
    foreach t in array array[
        'error_reports', 'error_entries', 'simulados', 'labels', 'tasks', 'calendar_connections'
    ]
    loop
        execute format('alter table public.%I enable row level security;', t);

        execute format('drop policy if exists %I on public.%I;', t || '_select', t);
        execute format(
            'create policy %I on public.%I for select using (auth.uid() = user_id);',
            t || '_select', t);

        execute format('drop policy if exists %I on public.%I;', t || '_insert', t);
        execute format(
            'create policy %I on public.%I for insert with check (auth.uid() = user_id);',
            t || '_insert', t);

        execute format('drop policy if exists %I on public.%I;', t || '_update', t);
        execute format(
            'create policy %I on public.%I for update using (auth.uid() = user_id) with check (auth.uid() = user_id);',
            t || '_update', t);

        execute format('drop policy if exists %I on public.%I;', t || '_delete', t);
        execute format(
            'create policy %I on public.%I for delete using (auth.uid() = user_id);',
            t || '_delete', t);
    end loop;
end $$;

-- =====================================================================
--  ADMIN: como adicionar alguém à whitelist (rode manualmente):
--
--    insert into public.allowed_emails (email, note)
--    values ('namorada@gmail.com', 'usuária principal');
--
--  Para desativar sem apagar:
--    update public.allowed_emails set is_active = false where email = '...';
-- =====================================================================

-- ---------------------------------------------------------------------
-- BLOCOS DE ESTUDO criados no app (para quem não tem horários na agenda)
-- ---------------------------------------------------------------------
create table if not exists public.study_blocks (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    weekday     integer not null check (weekday between 0 and 6),
    start_min   integer not null check (start_min between 0 and 1439),
    end_min     integer not null check (end_min between 1 and 1440),
    subject     varchar(80) not null,
    created_at  timestamptz not null default now()
);
create index if not exists idx_study_blocks_user on public.study_blocks(user_id);

alter table public.study_blocks enable row level security;
drop policy if exists study_blocks_select on public.study_blocks;
create policy study_blocks_select on public.study_blocks for select using (auth.uid() = user_id);
drop policy if exists study_blocks_insert on public.study_blocks;
create policy study_blocks_insert on public.study_blocks for insert with check (auth.uid() = user_id);
drop policy if exists study_blocks_update on public.study_blocks;
create policy study_blocks_update on public.study_blocks for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists study_blocks_delete on public.study_blocks;
create policy study_blocks_delete on public.study_blocks for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------
-- OVERRIDE do tipo de um evento (estudo/aula/outro), definido no popup.
-- ---------------------------------------------------------------------
create table if not exists public.event_overrides (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    event_id    varchar(512) not null,
    kind        varchar(20)  not null,
    created_at  timestamptz  not null default now(),
    unique (user_id, event_id),
    constraint event_override_kind_valid check (kind in ('estudo', 'aula', 'outro'))
);
create index if not exists idx_event_overrides_user on public.event_overrides(user_id);

alter table public.event_overrides enable row level security;
drop policy if exists event_overrides_select on public.event_overrides;
create policy event_overrides_select on public.event_overrides for select using (auth.uid() = user_id);
drop policy if exists event_overrides_insert on public.event_overrides;
create policy event_overrides_insert on public.event_overrides for insert with check (auth.uid() = user_id);
drop policy if exists event_overrides_update on public.event_overrides;
create policy event_overrides_update on public.event_overrides for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists event_overrides_delete on public.event_overrides;
create policy event_overrides_delete on public.event_overrides for delete using (auth.uid() = user_id);
