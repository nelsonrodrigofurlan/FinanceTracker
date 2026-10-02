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
  type PortfolioResult,
  type RunDetail,
  type SampleMetrics,
  type YearlyRow,
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

const RISK_OPTIONS = [0.5, 1, 2];
const POSITION_OPTIONS = [5, 10];

function pick(raw: string | string[] | undefined, options: number[], fallback: number): number {
  const value = Number(Array.isArray(raw) ? raw[0] : raw);
  return options.includes(value) ? value : fallback;
}

export default async function RunPage({ params, searchParams }: PageProps<"/laboratorio/[id]">) {
  const id = Number((await params).id);
  if (!Number.isInteger(id) || id < 1) notFound();
  const query = await searchParams;
  const risk = pick(query.risco, RISK_OPTIONS, 1);
  const positions = pick(query.posicoes, POSITION_OPTIONS, 5);

  let run: RunDetail;
  let yearly: YearlyRow[];
  let portfolio: PortfolioResult;
  try {
    [run, yearly, portfolio] = await Promise.all([
      apiGet<RunDetail>(`/lab/runs/${id}`),
      apiGet<YearlyRow[]>(`/lab/runs/${id}/yearly`),
      apiGet<PortfolioResult>(
        `/lab/runs/${id}/portfolio?risk_pct=${risk}&max_positions=${positions}`,
      ),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }
  const maxAbsYear = Math.max(...yearly.map((y) => Math.abs(y.expectancy_r ?? 0)), 0.01);

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
          <CardTitle>Simulação de carteira</CardTitle>
          <CardDescription>
            Como uma conta com capital limitado teria operado estes sinais: R$ 100 mil fictícios,
            teto de 20% por posição, sinais excedentes descartados. Parâmetros de simulação, não
            recomendação de risco.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <ParamLinks
              label="Risco por trade"
              options={RISK_OPTIONS}
              current={risk}
              href={(v) => `/laboratorio/${run.id}?risco=${v}&posicoes=${positions}`}
              suffix="%"
            />
            <ParamLinks
              label="Posições simultâneas"
              options={POSITION_OPTIONS}
              current={positions}
              href={(v) => `/laboratorio/${run.id}?risco=${risk}&posicoes=${v}`}
            />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Retorno ao ano"
              value={`${fmtNum1(portfolio.cagr_pct)}%`}
              tone={portfolio.cagr_pct}
            />
            <Stat
              label="Pior queda do patrimônio"
              value={`−${fmtNum1(portfolio.max_drawdown_pct)}%`}
              tone={-1}
            />
            <Stat
              label="Retorno total"
              value={`${fmtNum1(portfolio.total_return_pct)}%`}
              tone={portfolio.total_return_pct}
            />
            <Stat
              label="Trades feitos / sem vaga"
              value={`${portfolio.trades_taken} / ${portfolio.trades_skipped_no_slot ?? 0}`}
            />
          </div>
          <EquityChart
            points={portfolio.curve}
            format="brl"
            baseline={portfolio.params.initial_capital}
          />
          <p className="text-muted-foreground text-xs">
            Compare com a renda fixa: um setup que rende pouco acima do CDI com quedas grandes não
            compensa o risco. Patrimônio realizado (posições abertas não são marcadas a mercado);
            caixa parado não rende juros na simulação; sinais do mesmo dia entram em ordem
            alfabética.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estabilidade ano a ano</CardTitle>
          <CardDescription>Expectativa por trade em cada ano (pela data de entrada).</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-1">
          {yearly.map((y) => {
            const e = y.expectancy_r ?? 0;
            return (
              <div key={y.year} className="grid grid-cols-[3rem_1fr_7rem] items-center gap-2 text-xs">
                <span className="num text-muted-foreground">{y.year}</span>
                <div className="relative h-3">
                  <div className="bg-border absolute top-0 left-1/2 h-full w-px" />
                  <div
                    className={cn(
                      "absolute top-0.5 h-2 rounded-sm",
                      e >= 0 ? "bg-up left-1/2" : "bg-down right-1/2",
                    )}
                    style={{ width: `${(Math.abs(e) / maxAbsYear) * 50}%` }}
                  />
                </div>
                <span className={cn("num text-right", toneR(e))}>
                  {fmtR(y.expectancy_r)} <span className="text-muted-foreground">({y.trades})</span>
                </span>
              </div>
            );
          })}
        </CardContent>
      </Card>

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

function Stat({ label, value, tone }: { label: string; value: string; tone?: number | null }) {
  return (
    <div className="bg-muted/40 rounded-md p-3">
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className={cn("num text-lg font-semibold", tone != null && toneR(tone))}>{value}</div>
    </div>
  );
}

function ParamLinks({
  label,
  options,
  current,
  href,
  suffix = "",
}: {
  label: string;
  options: number[];
  current: number;
  href: (value: number) => string;
  suffix?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-muted-foreground">{label}</span>
      <div className="bg-muted flex rounded-md p-0.5">
        {options.map((v) => (
          <Link
            key={v}
            href={href(v)}
            scroll={false}
            aria-current={v === current ? "true" : undefined}
            className={cn(
              "num rounded px-2 py-0.5",
              v === current
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {String(v).replace(".", ",")}
            {suffix}
          </Link>
        ))}
      </div>
    </div>
  );
}
