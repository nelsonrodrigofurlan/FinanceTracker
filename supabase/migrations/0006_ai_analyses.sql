-- FinanceTracker — explicações de sinais geradas por IA (F5)
-- Mesma política de segurança: schema ft, RLS sem políticas, sem acesso via PostgREST.

create table ft.ai_analyses (
    id           bigint generated always as identity primary key,
    signal_id    bigint not null references ft.signals (id) on delete cascade,
    model        text not null,            -- modelo que respondeu de fato (não o apelido)
    prompt_hash  text not null,            -- sha256 do contexto enviado (auditoria)
    content      text not null,
    usage        jsonb not null,           -- tokens e custo (USD) informados pelo OpenRouter
    created_at   timestamptz not null default now()
);
create index ai_analyses_signal_idx on ft.ai_analyses (signal_id, created_at desc);

alter table ft.ai_analyses enable row level security;
revoke all on ft.ai_analyses from public, anon, authenticated;
