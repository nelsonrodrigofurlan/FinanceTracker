-- FinanceTracker — dados de mercado (F2)
--
-- Segurança: tudo fica no schema `ft`, que NÃO é exposto pela API REST do Supabase
-- (PostgREST expõe só `public` por padrão). Além disso, revogamos qualquer privilégio
-- dos papéis `anon` e `authenticated`. Acesso apenas via conexão direta (API/pipeline).

create schema if not exists ft;
revoke all on schema ft from public, anon, authenticated;

-- Ativos acompanhados (ações do universo + referências de mercado)
create table ft.assets (
    id            bigint generated always as identity primary key,
    ticker        text not null unique,                 -- código B3, ex.: PETR4
    yahoo_symbol  text not null unique,                 -- ex.: PETR4.SA
    name          text,
    type          text not null check (type in ('stock', 'etf')),
    is_benchmark  boolean not null default false,       -- BOVA11, SMAL11
    active        boolean not null default true,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

-- Candles diários.
-- close: fechamento ajustado só por desdobramentos (padrão Yahoo) — usado em sinais.
-- adj_close: ajustado também por proventos — usado no backtest.
-- fin_volume: aproximação close * volume (Yahoo não informa volume financeiro).
create table ft.candles_daily (
    asset_id    bigint not null references ft.assets (id) on delete cascade,
    date        date not null,
    open        numeric(14, 4) not null check (open > 0),
    high        numeric(14, 4) not null check (high > 0),
    low         numeric(14, 4) not null check (low > 0),
    close       numeric(14, 4) not null check (close > 0),
    adj_close   numeric(18, 8) not null check (adj_close > 0),
    volume      bigint not null check (volume >= 0),
    fin_volume  numeric(20, 2) not null check (fin_volume >= 0),
    source      text not null,
    updated_at  timestamptz not null default now(),
    primary key (asset_id, date),
    check (high >= low),
    check (high >= greatest(open, close)),
    check (low <= least(open, close))
);
create index candles_daily_date_idx on ft.candles_daily (date);

-- Proventos e desdobramentos (para auditoria do ajuste de preços)
create table ft.corporate_events (
    asset_id  bigint not null references ft.assets (id) on delete cascade,
    date      date not null,
    type      text not null check (type in ('dividend', 'split')),
    value     numeric(18, 8) not null,
    source    text not null,
    primary key (asset_id, date, type)
);

-- Fotografia mensal do universo (reduz viés de sobrevivência em backtests futuros)
create table ft.universe_snapshots (
    id          bigint generated always as identity primary key,
    ref_date    date not null unique,
    criteria    jsonb not null,
    candidates  text[] not null,                        -- tickers do IBrX-100 na data
    selected    text[] not null,                        -- aprovados no filtro de liquidez
    created_at  timestamptz not null default now()
);

-- Execuções do pipeline (observabilidade)
create table ft.pipeline_runs (
    id           bigint generated always as identity primary key,
    job          text not null,
    started_at   timestamptz not null default now(),
    finished_at  timestamptz,
    status       text not null check (status in ('running', 'success', 'failed')),
    stats        jsonb not null default '{}'::jsonb,
    error        text
);
create index pipeline_runs_started_idx on ft.pipeline_runs (started_at desc);

-- Defesa em profundidade: RLS ligado e sem políticas = nenhum acesso via PostgREST
alter table ft.assets enable row level security;
alter table ft.candles_daily enable row level security;
alter table ft.corporate_events enable row level security;
alter table ft.universe_snapshots enable row level security;
alter table ft.pipeline_runs enable row level security;

revoke all on all tables in schema ft from public, anon, authenticated;
revoke all on all sequences in schema ft from public, anon, authenticated;
alter default privileges in schema ft revoke all on tables from public, anon, authenticated;
alter default privileges in schema ft revoke all on sequences from public, anon, authenticated;
alter default privileges in schema ft revoke all on functions from public, anon, authenticated;
