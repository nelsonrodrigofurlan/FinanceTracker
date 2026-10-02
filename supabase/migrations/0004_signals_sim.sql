-- FinanceTracker — estratégias, sinais diários, carteira simulada e ajustes (F5)
-- Mesma política de segurança: schema ft, RLS sem políticas, sem acesso via PostgREST.

-- Estratégia = variante de setup com status decidido por regra a partir do laboratório.
create table ft.strategies (
    id              bigint generated always as identity primary key,
    setup_code      text not null,
    variant         text not null,
    params          jsonb not null,
    status          text not null check (status in ('approved', 'observation', 'rejected')),
    source_run_id   bigint references ft.backtest_runs (id) on delete set null,
    evidence        jsonb not null,          -- números que justificam o status
    sim_start_date  date,                    -- início da operação simulada ao vivo
    decided_at      timestamptz not null default now(),
    unique (setup_code, variant)
);

-- Sinais do scanner (um por estratégia × ativo × pregão de referência).
create table ft.signals (
    id              bigint generated always as identity primary key,
    strategy_id     bigint not null references ft.strategies (id) on delete cascade,
    ticker          text not null,
    signal_date     date not null,           -- pregão cujo fechamento gerou o sinal
    order_kind      text not null check (order_kind in ('close', 'open', 'stop')),
    entry_level     numeric(14, 4),          -- nível da ordem stop; null para abertura/fechamento
    ref_price       numeric(14, 4) not null, -- fechamento do pregão do sinal
    stop            numeric(14, 4),          -- stop absoluto (se já conhecido)
    stop_distance   numeric(14, 4),          -- stop relativo ao preço executado
    risk_distance   numeric(14, 4),          -- unidade R quando não há stop de preço
    target_r        numeric(6, 2),
    expires_after   integer,                 -- validade da ordem em pregões
    created_at      timestamptz not null default now(),
    unique (strategy_id, ticker, signal_date)
);
create index signals_date_idx on ft.signals (signal_date desc);

-- Carteira simulada: recalculada pelo motor a partir de sim_start_date (paridade com backtest).
create table ft.sim_trades (
    strategy_id     bigint not null references ft.strategies (id) on delete cascade,
    ticker          text not null,
    entry_date      date not null,
    entry_price     numeric(14, 4) not null,
    initial_stop    numeric(14, 4) not null,
    target          numeric(14, 4),
    exit_date       date,                    -- null = posição aberta
    exit_price      numeric(14, 4),          -- aberta: último fechamento (marcação)
    exit_reason     text,
    r_multiple      numeric(10, 4) not null, -- aberta: R não realizado
    bars            integer not null,
    status          text not null check (status in ('open', 'closed')),
    updated_at      timestamptz not null default now(),
    primary key (strategy_id, ticker, entry_date)
);

-- Parâmetros do usuário (modo simulado). Sem valores padrão de risco: decisão do usuário.
create table ft.user_settings (
    user_id           uuid primary key,
    sim_capital       numeric(16, 2) check (sim_capital > 0),
    risk_pct          numeric(5, 2) check (risk_pct > 0 and risk_pct <= 5),
    max_positions     integer check (max_positions between 1 and 30),
    max_position_pct  numeric(5, 2) check (max_position_pct > 0 and max_position_pct <= 100),
    updated_at        timestamptz not null default now()
);

alter table ft.strategies enable row level security;
alter table ft.signals enable row level security;
alter table ft.sim_trades enable row level security;
alter table ft.user_settings enable row level security;
revoke all on ft.strategies, ft.signals, ft.sim_trades, ft.user_settings
    from public, anon, authenticated;
