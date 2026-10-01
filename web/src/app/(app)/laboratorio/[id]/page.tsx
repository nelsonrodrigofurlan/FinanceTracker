import { ArrowLeft, Check, X } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { EquityChart } from "@/components/equity-chart";
import { EvidenceBadge } from "@/components/evidence-badge";
import { PageBody } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiGet } from "@/lib/api";
import {
  CHECK_LABEL,
  EXIT_LABEL,
  fmtNum1,
  fmtNum2,
  fmtR,
  type RunDetail,
  type SampleMetrics,
} from "@/lib/lab";
import { fmtDate, fmtPct, fmtPrice } from "@/lib/market";
import { cn } from "@/lib/utils";

const METRIC_ROWS: { key: keyof SampleMetrics; label: string; fmt: (v: number) => string }[] = [
  { key: "trades", label: "Trades", fmt: (v) => String(v) },
  { key: "win_rate", label: "Acerto", fmt: (v) => `${fmtNum1(v)}%` },
  { key: "expectancy_r", label: "Expectativa por trade", fmt: fmtR },
  { key: "payoff", label: "Payoff (ganho médio ÷ perda média)", fmt: fmtNum2 },
  { key: "profit_factor", label: "Fator de lucro", fmt: fmtNum2 },
  { key: "total_r", label: "Resultado acumulado", fmt: fmtR },
  { key: "max_drawdown_r", label: "Rebaixamento máximo", fmt: (v) => `${fmtNum1(v)}R` },
  { key: "max_consecutive_losses", label: "Pior sequência de perdas", fmt: (v) => String(v) },
  { key: "avg_bars", label: "Duração média (pregões)", fmt: fmtNum1 },
];

function toneR(v: number) {
  return v > 0 ? "text-up" : v < 0 ? "text-down" : undefined;
}

export default async function RunPage({ params }: PageProps<"/laboratorio/[id]">) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id < 1) notFound();

  let run: RunDetail;
  try {
    run = await apiGet<RunDetail>(`/lab/runs/${id}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const best = run.by_ticker.slice(0, 5);
  const worst = run.by_ticker.slice(-5).reverse();

  return (
    <PageBody>
      <div className="flex flex-col gap-2">
        <Link
          href="/laboratorio"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs"
        >
          <ArrowLeft className="size-3" /> Laboratório
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">
            {run.setup_code} · {run.setup_name}
          </h1>
          <EvidenceBadge
            approved={run.approved}
            expectancy={run.out_of_sample.expectancy_r}
            trades={run.out_of_sample.trades}
          />
        </div>
        <p className="text-muted-foreground text-sm">
          Variante: {run.variant} · {run.universe.count} ativos · {fmtDate(run.period_start)} a{" "}
          {fmtDate(run.period_end)} · fora da amostra desde {fmtDate(run.split_date)}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Resultado acumulado em R</CardTitle>
            <CardDescription>
              Soma dos trades por data de saída. Cinza: dentro da amostra · azul: fora da amostra.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EquityChart points={run.equity} splitDate={run.split_date} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Critérios de aprovação</CardTitle>
            <CardDescription>Todos precisam passar.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-sm">
            {Object.entries(run.approval.checks).map(([key, ok]) => (
              <div key={key} className="flex items-start gap-2">
                {ok ? (
                  <Check className="text-up mt-0.5 size-4 shrink-0" aria-label="passou" />
                ) : (
                  <X className="text-down mt-0.5 size-4 shrink-0" aria-label="falhou" />
                )}
                <span className={cn(!ok && "text-muted-foreground")}>{CHECK_LABEL[key] ?? key}</span>
              </div>
            ))}
            <p className="text-muted-foreground border-t pt-3 text-xs">
              Mínimos: {run.approval.criteria.min_oos_trades} trades, fator de lucro{" "}
              {fmtNum2(run.approval.criteria.min_oos_profit_factor)}, expectativa fora ≥{" "}
              {Math.round(run.approval.criteria.max_degradation * 100)}% da de dentro.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Métricas</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground border-b text-xs">
              <tr>
                <th className="py-2 text-left font-medium">Métrica</th>
                <th className="py-2 text-right font-medium">Dentro da amostra</th>
                <th className="py-2 text-right font-medium">Fora da amostra</th>
                <th className="py-2 text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {METRIC_ROWS.map(({ key, label, fmt }) => (
                <tr key={key}>
                  <td className="text-muted-foreground py-2">{label}</td>
                  {[run.in_sample, run.out_of_sample, run.metrics_all].map((m, i) => {
                    const v = m[key] as number | null | undefined;
                    return (
                      <td key={i} className={cn("num py-2 text-right", i === 1 && "font-medium")}>
                        {v == null ? "—" : fmt(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {[
          { title: "Melhores ativos", rows: best },
          { title: "Piores ativos", rows: worst },
        ].map(({ title, rows }) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
              <CardDescription>Resultado acumulado no período inteiro.</CardDescription>
            </CardHeader>
            <CardContent className="divide-y text-sm">
              {rows.map((t) => (
                <div key={t.ticker} className="flex items-center justify-between py-1.5">
                  <Link href={`/ativos/${t.ticker}`} className="hover:text-primary font-medium">
                    {t.ticker}
                  </Link>
                  <span className="num text-muted-foreground text-xs">
                    {t.trades} trades · acerto {fmtNum1(t.win_rate)}%
                  </span>
                  <span className={cn("num w-20 text-right", toneR(t.total_r))}>{fmtR(t.total_r)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Últimos trades</CardTitle>
          <CardDescription>Os 50 mais recentes por data de saída (preços ajustados).</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground border-b text-xs">
              <tr>
                <th className="py-2 text-left font-medium">Ativo</th>
                <th className="py-2 text-left font-medium">Entrada</th>
                <th className="py-2 text-left font-medium">Saída</th>
                <th className="py-2 text-left font-medium">Motivo</th>
                <th className="py-2 text-right font-medium">Pregões</th>
                <th className="py-2 text-right font-medium">Retorno</th>
                <th className="py-2 text-right font-medium">Resultado</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {run.recent_trades.map((t, i) => (
                <tr key={`${t.ticker}-${t.entry_date}-${i}`}>
                  <td className="py-1.5 font-medium">{t.ticker}</td>
                  <td className="num text-muted-foreground py-1.5">
                    {fmtDate(t.entry_date)} · {fmtPrice(t.entry_price)}
                  </td>
                  <td className="num text-muted-foreground py-1.5">
                    {fmtDate(t.exit_date)} · {fmtPrice(t.exit_price)}
                  </td>
                  <td className="text-muted-foreground py-1.5 text-xs">
                    {EXIT_LABEL[t.exit_reason] ?? t.exit_reason}
                  </td>
                  <td className="num py-1.5 text-right">{t.bars}</td>
                  <td className={cn("num py-1.5 text-right", toneR(t.return_pct))}>
                    {fmtPct(t.return_pct)}
                  </td>
                  <td className={cn("num py-1.5 text-right font-medium", toneR(t.r_multiple))}>
                    {fmtR(t.r_multiple)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs">
        {run.universe.note} Gráficos por{" "}
        <a
          href="https://www.tradingview.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-foreground underline underline-offset-2"
        >
          TradingView Lightweight Charts™
        </a>
        .
      </p>
    </PageBody>
  );
}
