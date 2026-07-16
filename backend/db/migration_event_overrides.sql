-- =====================================================================
--  MIGRAÇÃO: Override do tipo de um evento da agenda.
--
--  Cole e rode no SQL Editor da Supabase.
--
--  Permite o usuário corrigir manualmente, no popup do evento, se um horário
--  é de estudo, aula ou outro compromisso (sobrepõe a leitura automática do
--  título). Só "estudo" recebe alocação de tarefas.
-- =====================================================================

create extension if not exists "pgcrypto";

create table if not exists public.event_overrides (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    event_id    varchar(512) not null,          -- id do evento (Google) ou "sb-<uuid>" (app)
    kind        varchar(20)  not null,           -- 'estudo' | 'aula' | 'outro'
    created_at  timestamptz  not null default now(),
    unique (user_id, event_id),
    constraint event_override_kind_valid check (kind in ('estudo', 'aula', 'outro'))
);

create index if not exists idx_event_overrides_user on public.event_overrides(user_id);

alter table public.event_overrides enable row level security;

drop policy if exists event_overrides_select on public.event_overrides;
create policy event_overrides_select on public.event_overrides
    for select using (auth.uid() = user_id);

drop policy if exists event_overrides_insert on public.event_overrides;
create policy event_overrides_insert on public.event_overrides
    for insert with check (auth.uid() = user_id);

drop policy if exists event_overrides_update on public.event_overrides;
create policy event_overrides_update on public.event_overrides
    for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists event_overrides_delete on public.event_overrides;
create policy event_overrides_delete on public.event_overrides
    for delete using (auth.uid() = user_id);
