-- FinanceTracker — laboratório de backtest (F4)
-- Mesma política de segurança do 0001: schema ft, RLS sem políticas, sem acesso via PostgREST.

create table ft.backtest_runs (
    id            bigint generated always as identity primary key,
    setup_code    text not null,                       -- S1..S5
    variant       text not null,                       -- nome legível da combinação de parâmetros
    params        jsonb not null,
    costs         jsonb not null,
    period_start  date not null,
    period_end    date not null,
    split_date    date not null,                       -- início do período fora da amostra
    universe      jsonb not null,                      -- tickers usados + observações (viés)
    metrics       jsonb not null,                      -- {all, in_sample, out_of_sample}
    approved      boolean not null,
    approval      jsonb not null,                      -- critérios e resultado de cada checagem
    engine_version text not null,
    created_at    timestamptz not null default now()
);
create index backtest_runs_setup_idx on ft.backtest_runs (setup_code, created_at desc);

create table ft.backtest_trades (
    run_id        bigint not null references ft.backtest_runs (id) on delete cascade,
    ticker        text not null,
    entry_date    date not null,
    entry_price   numeric(14, 4) not null,
    exit_date     date not null,
    exit_price    numeric(14, 4) not null,
    initial_stop  numeric(14, 4) not null,
    target        numeric(14, 4),
    r_multiple    numeric(10, 4) not null,
    return_pct    numeric(10, 4) not null,
    bars          integer not null,
    exit_reason   text not null,
    sample        text not null check (sample in ('in', 'out'))
);
create index backtest_trades_run_idx on ft.backtest_trades (run_id, exit_date);

alter table ft.backtest_runs enable row level security;
alter table ft.backtest_trades enable row level security;
revoke all on ft.backtest_runs, ft.backtest_trades from public, anon, authenticated;
