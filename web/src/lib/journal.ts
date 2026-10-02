export type JournalTrade = {
  id: number;
  ticker: string;
  signal_id: number | null;
  strategy_status: string | null;
  entry_date: string;
  entry_price: number;
  quantity: number;
  stop_planned: number | null;
  target_planned: number | null;
  entry_fees: number;
  reason: string | null;
  emotion: string | null;
  exit_date: string | null;
  exit_price: number | null;
  exit_fees: number;
  exit_notes: string | null;
  status: "open" | "closed";
  pnl: number | null;
  return_pct: number | null;
  r_multiple: number | null;
  planned_risk: number | null;
  holding_days: number | null;
};

export type JournalSummary = {
  open_count: number;
  closed_count: number;
  win_rate: number | null;
  total_pnl: number;
  avg_r: number | null;
  with_stop_pct: number | null;
  non_approved_count: number;
};

export type Journal = { trades: JournalTrade[]; summary: JournalSummary };

export const EMOTIONS: Record<string, string> = {
  calmo: "Calmo",
  confiante: "Confiante",
  ansioso: "Ansioso",
  com_medo: "Com medo",
  euforico: "Eufórico",
  impaciente: "Impaciente",
};

const brl = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  signDisplay: "exceptZero",
});
export const fmtBRL = (v: number | null | undefined) => (v == null ? "—" : brl.format(v));

/** Converte "1.234,56" ou "1234.56" em número; vazio → null; inválido → NaN. */
export function parseBR(raw: FormDataEntryValue | null): number | null {
  const text = String(raw ?? "").trim();
  if (!text) return null;
  const normalized = text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text;
  const value = Number(normalized);
  return Number.isFinite(value) ? value : NaN;
}
