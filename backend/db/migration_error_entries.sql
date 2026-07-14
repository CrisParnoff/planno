-- =====================================================================
--  MIGRAÇÃO: Caderno de erros (aba "Relatório de erros" reformulada)
--
--  Cole e rode este arquivo no SQL Editor da Supabase.
--
--  O que faz:
--   1. Cria a tabela public.error_entries — cada linha é UM erro de UMA
--      questão (modelo do "CADERNO DE ERROS"): prova, data, questão,
--      matéria, assunto, tipo de erro e controle de "refazer".
--   2. Ativa RLS (mesmo padrão das outras tabelas: só o dono enxerga).
--
--  Observação: a tabela antiga public.error_reports (upload de Excel
--  agregado) não é mais usada pelo app. Ela NÃO é apagada aqui para não
--  arriscar seus dados. Se quiser removê-la, rode manualmente:
--       drop table if exists public.error_reports;
-- =====================================================================

create extension if not exists "pgcrypto";

create table if not exists public.error_entries (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    exam        varchar(120),                    -- Prova (opcional, ex.: "UPF 26/2")
    error_date  date,                            -- Data em que fez a questão
    question    integer,                         -- Nº da questão (opcional)
    area        varchar(40),                     -- Grande área (Naturezas/Humanas/Matemática/Linguagens) — opcional
    subject     varchar(80)  not null,           -- Matéria (ex.: Física)
    topic       varchar(120) not null,           -- Assunto (ex.: Mecânica)
    error_type  varchar(20)  not null,           -- 'conteudo' | 'atencao' | 'interpretacao'
    redone      boolean      not null default false,  -- Situação: já refez a questão?
    redo_on     date,                            -- Refazer: data planejada (opcional)
    created_at  timestamptz  not null default now(),
    constraint error_type_valid
        check (error_type in ('conteudo', 'atencao', 'interpretacao'))
);

create index if not exists idx_error_entries_user_date
    on public.error_entries(user_id, error_date desc);
create index if not exists idx_error_entries_user_subject
    on public.error_entries(user_id, subject);
create index if not exists idx_error_entries_user_redo
    on public.error_entries(user_id, redone);

-- ---------------------------------------------------------------------
-- RLS: só o dono (auth.uid() = user_id) vê/edita as próprias linhas.
-- ---------------------------------------------------------------------
alter table public.error_entries enable row level security;

drop policy if exists error_entries_select on public.error_entries;
create policy error_entries_select on public.error_entries
    for select using (auth.uid() = user_id);

drop policy if exists error_entries_insert on public.error_entries;
create policy error_entries_insert on public.error_entries
    for insert with check (auth.uid() = user_id);

drop policy if exists error_entries_update on public.error_entries;
create policy error_entries_update on public.error_entries
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists error_entries_delete on public.error_entries;
create policy error_entries_delete on public.error_entries
    for delete using (auth.uid() = user_id);
