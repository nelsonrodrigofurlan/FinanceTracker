-- FinanceTracker — CDI diário (Banco Central, SGS série 12), referência de renda fixa.
-- Mesma política de segurança: schema ft, RLS sem políticas, sem acesso via PostgREST.

create table ft.cdi_daily (
    date          date primary key,
    rate_pct_day  numeric(12, 8) not null check (rate_pct_day >= 0),  -- % ao dia útil
    source        text not null default 'bcb_sgs_12',
    updated_at    timestamptz not null default now()
);

alter table ft.cdi_daily enable row level security;
revoke all on ft.cdi_daily from public, anon, authenticated;
