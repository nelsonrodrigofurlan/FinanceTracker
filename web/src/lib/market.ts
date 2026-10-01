// Tipos e formatação de dados de mercado (compartilhados entre servidor e cliente).

export type AssetSummary = {
  ticker: string;
  name: string | null;
  type: "stock" | "etf";
  is_benchmark: boolean;
  last_date: string | null;
  last_close: number | null;
  change_pct: number | null;
  avg_fin_volume_21: number | null;
};

export type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Point = { time: string; value: number };

export type CandlesResponse = {
  ticker: string;
  name: string | null;
  range: ChartRange;
  candles: Candle[];
  indicators: Record<"sma200" | "ema21" | "ema9" | "rsi2" | "rsi14", Point[]>;
};

export const CHART_RANGES = ["6m", "1y", "3y", "5y", "max"] as const;
export type ChartRange = (typeof CHART_RANGES)[number];
export const RANGE_LABEL: Record<ChartRange, string> = {
  "6m": "6M",
  "1y": "1A",
  "3y": "3A",
  "5y": "5A",
  max: "Máx",
};

export const TICKER_RE = /^[A-Z][A-Z0-9]{3}\d{1,2}$/;

const price = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = new Intl.NumberFormat("pt-BR", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "exceptZero",
});
const millions = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export const fmtPrice = (v: number | null | undefined) => (v == null ? "—" : price.format(v));
export const fmtPct = (v: number | null | undefined) => (v == null ? "—" : `${pct.format(v)}%`);
export const fmtMillions = (v: number | null | undefined) =>
  v == null ? "—" : `${millions.format(v / 1e6)} mi`;
export const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString("pt-BR", { timeZone: "UTC" }) : "—";
