// Tipos e formatação do laboratório de backtest.

export type SampleMetrics = {
  trades: number;
  win_rate?: number;
  avg_win_r?: number;
  avg_loss_r?: number;
  payoff?: number | null;
  expectancy_r?: number;
  profit_factor?: number | null;
  total_r?: number;
  max_drawdown_r?: number;
  max_consecutive_losses?: number;
  avg_bars?: number;
  avg_return_pct?: number;
};

export type RunSummary = {
  id: number;
  setup_code: string;
  setup_name: string;
  variant: string;
  approved: boolean;
  created_at: string;
  split_date: string;
  in_sample: SampleMetrics;
  out_of_sample: SampleMetrics;
};

export type RunDetail = RunSummary & {
  params: Record<string, unknown>;
  costs: Record<string, number>;
  period_start: string;
  period_end: string;
  universe: { count: number; note?: string; series_cut_at?: Record<string, string> };
  approval: {
    approved: boolean;
    criteria: Record<string, number>;
    checks: Record<string, boolean>;
  };
  metrics_all: SampleMetrics;
  equity: { time: string; value: number }[];
  by_ticker: {
    ticker: string;
    trades: number;
    expectancy_r: number;
    total_r: number;
    win_rate: number;
  }[];
  recent_trades: {
    ticker: string;
    entry_date: string;
    entry_price: number;
    exit_date: string;
    exit_price: number;
    r_multiple: number;
    return_pct: number;
    bars: number;
    exit_reason: string;
    sample: "in" | "out";
  }[];
};

const r2 = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});
const n1 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const n2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtR = (v: number | null | undefined) => (v == null ? "—" : `${r2.format(v)}R`);
export const fmtNum1 = (v: number | null | undefined) => (v == null ? "—" : n1.format(v));
export const fmtNum2 = (v: number | null | undefined) => (v == null ? "—" : n2.format(v));

export const CHECK_LABEL: Record<string, string> = {
  oos_trades: "Trades suficientes fora da amostra",
  oos_expectancy: "Expectativa positiva fora da amostra (após custos)",
  oos_profit_factor: "Fator de lucro mínimo fora da amostra",
  no_severe_degradation: "Sem degradação grave entre dentro e fora da amostra",
};

export const EXIT_LABEL: Record<string, string> = {
  stop: "Stop",
  alvo: "Alvo",
  stop_tempo: "Stop no tempo",
  saida_max2: "Fechou acima da máx. 2",
  saida_mma5: "Fechou acima da MMA5",
  saida_minima_n: "Perdeu a mínima de N",
  fim_dos_dados: "Em aberto (fim dos dados)",
};

export type WalkForwardRow = {
  year: number;
  chosen_variant: string;
  lookback_expectancy_r: number;
  trades: number;
  total_r: number;
  expectancy_r: number | null;
  would_trade: boolean;
};

export type WalkForward = {
  setup_code: string;
  setup_name: string;
  params: { lookback: number; min_trades: number };
  years: WalkForwardRow[];
  trades: number;
  total_r?: number;
  expectancy_r: number | null;
  years_traded?: number;
  years_positive?: number;
};

export type YearlyRow = { year: number; trades: number; total_r: number; expectancy_r: number | null };

export type PortfolioResult = {
  params: { initial_capital: number; risk_pct: number; max_positions: number; max_position_pct: number };
  trades_taken: number;
  trades_skipped_no_slot?: number;
  trades_skipped_size?: number;
  final_equity?: number;
  total_return_pct?: number;
  cagr_pct?: number;
  max_drawdown_pct?: number;
  years?: number;
  curve: { time: string; value: number }[];
};
