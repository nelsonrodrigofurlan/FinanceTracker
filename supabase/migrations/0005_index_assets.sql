-- FinanceTracker — permite índices como ativo de referência (ex.: IBOV, fonte Yahoo ^BVSP).
-- Usado no filtro de regime de mercado dos setups.

alter table ft.assets drop constraint assets_type_check;
alter table ft.assets add constraint assets_type_check check (type in ('stock', 'etf', 'index'));
