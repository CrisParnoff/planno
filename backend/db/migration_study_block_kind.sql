-- =====================================================================
--  MIGRAÇÃO: tipo do bloco criado no app (estudo/aula/outro).
--
--  Cole e rode no SQL Editor da Supabase.
--
--  Permite criar, dentro do app, blocos de aula ou outros compromissos
--  (além de estudo). Só "estudo" recebe alocação de tarefas.
-- =====================================================================

alter table public.study_blocks
    add column if not exists kind varchar(20) not null default 'estudo';

alter table public.study_blocks
    drop constraint if exists study_block_kind_valid;

alter table public.study_blocks
    add constraint study_block_kind_valid check (kind in ('estudo', 'aula', 'outro'));
