import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageBody } from "@/components/page";
import { PriceChart } from "@/components/price-chart";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, apiGet } from "@/lib/api";
import {
  CHART_RANGES,
  RANGE_LABEL,
  TICKER_RE,
  fmtDate,
  fmtPct,
  fmtPrice,
  type CandlesResponse,
  type ChartRange,
} from "@/lib/market";
import { cn } from "@/lib/utils";

export default async function AtivoPage({ params, searchParams }: PageProps<"/ativos/[ticker]">) {
  const ticker = (await params).ticker.toUpperCase();
  if (!TICKER_RE.test(ticker)) notFound();

  const rawRange = (await searchParams).range;
  const range: ChartRange = CHART_RANGES.includes(rawRange as ChartRange)
    ? (rawRange as ChartRange)
    : "1y";

  let data: CandlesResponse;
  try {
    data = await apiGet<CandlesResponse>(`/market/candles/${ticker}?range=${range}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) notFound();
    throw error;
  }

  const n = data.candles.length;
  const last = n ? data.candles[n - 1] : null;
  const prev = n > 1 ? data.candles[n - 2] : null;
  const change = last && prev ? (last.close / prev.close - 1) * 100 : null;

  return (
    <PageBody>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <Link
            href="/ativos"
            className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-xs"
          >
            <ArrowLeft className="size-3" /> Ativos
          </Link>
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{data.ticker}</h1>
            <span className="text-muted-foreground text-sm">{data.name}</span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="num text-xl font-semibold">{fmtPrice(last?.close)}</span>
            <span
              className={cn(
                "num text-sm",
                change != null && change > 0 && "text-up",
                change != null && change < 0 && "text-down",
              )}
            >
              {fmtPct(change)}
            </span>
            <span className="text-muted-foreground text-xs">fechamento de {fmtDate(last?.time)}</span>
          </div>
        </div>
        <nav className="bg-muted flex rounded-md p-0.5" aria-label="Período do gráfico">
          {CHART_RANGES.map((r) => (
            <Link
              key={r}
              href={`/ativos/${data.ticker}?range=${r}`}
              aria-current={r === range ? "page" : undefined}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                r === range
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {RANGE_LABEL[r]}
            </Link>
          ))}
        </nav>
      </div>

      <Card>
        <CardContent>
          <PriceChart data={data} />
        </CardContent>
      </Card>

      <p className="text-muted-foreground text-xs">
        Preços ajustados por desdobramentos (fonte: Yahoo Finance). Gráficos por{" "}
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
