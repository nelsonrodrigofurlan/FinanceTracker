-- FinanceTracker — diário de trades REAIS (registrados pelo usuário; o app não envia ordens).
-- Mesma política de segurança: schema ft, RLS sem políticas, sem acesso via PostgREST.

create table ft.journal_trades (
    id              bigint generated always as identity primary key,
    user_id         uuid not null,
    ticker          text not null check (ticker ~ '^[A-Z][A-Z0-9]{3}[0-9]{1,2}F?$'),
    signal_id       bigint references ft.signals (id) on delete set null,
    entry_date      date not null,
    entry_price     numeric(14, 4) not null check (entry_price > 0),
    quantity        integer not null check (quantity > 0),
    stop_planned    numeric(14, 4) check (stop_planned > 0),
    target_planned  numeric(14, 4) check (target_planned > 0),
    entry_fees      numeric(12, 2) not null default 0 check (entry_fees >= 0),
    reason          text check (char_length(reason) <= 2000),
    emotion         text check (emotion in
                        ('calmo', 'confiante', 'ansioso', 'com_medo', 'euforico', 'impaciente')),
    exit_date       date,
    exit_price      numeric(14, 4) check (exit_price > 0),
    exit_fees       numeric(12, 2) not null default 0 check (exit_fees >= 0),
    exit_notes      text check (char_length(exit_notes) <= 2000),
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    check (stop_planned is null or stop_planned < entry_price),
    check (target_planned is null or target_planned > entry_price),
    check ((exit_date is null) = (exit_price is null)),
    check (exit_date is null or exit_date >= entry_date)
);
create index journal_trades_user_idx on ft.journal_trades (user_id, entry_date desc);

alter table ft.journal_trades enable row level security;
revoke all on ft.journal_trades from public, anon, authenticated;
