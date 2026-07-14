-- Rode no SQL Editor da Supabase para adicionar a tabela de blocos de estudo.
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
