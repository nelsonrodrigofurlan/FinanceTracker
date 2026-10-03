export type StrategyStatus = "approved" | "observation" | "rejected";

export type Strategy = {
  id: number;
  setup_code: string;
  setup_name: string;
  variant: string;
  status: StrategyStatus;
  sim_start_date: string | null;
  evidence: {
    oos?: { expectancy_r?: number; trades?: number };
    walkforward_expectancy_r?: number | null;
    portfolio_cagr_pct?: number | null;
    cdi_cagr_pct?: number | null;
  };
};

export type Signal = {
  id: number;
  ticker: string;
  signal_date: string;
  setup_code: string;
  setup_name: string;
  variant: string;
  status: StrategyStatus;
  order_kind: "open" | "close" | "stop";
  entry_estimate: number | null;
  entry_is_estimate: boolean;
  stop_estimate: number | null;
  target_estimate: number | null;
  risk_per_share: number | null;
  quantity: number | null;
  evidence: Strategy["evidence"];
};

export type SimTrade = {
  setup_code: string;
  variant: string;
  ticker: string;
  entry_date: string;
  entry_price: number;
  initial_stop: number;
  target: number | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  r_multiple: number;
  bars: number;
  status: "open" | "closed";
};

export type SimBook = {
  open: SimTrade[];
  closed: SimTrade[];
  closed_count: number;
  total_r: number;
  win_rate: number | null;
};

export const STATUS_LABEL: Record<StrategyStatus, string> = {
  approved: "Aprovada",
  observation: "Em observação",
  rejected: "Reprovada",
};

export const ORDER_LABEL: Record<Signal["order_kind"], string> = {
  open: "Compra na abertura",
  close: "Compra no fechamento",
  stop: "Stop de compra",
};
