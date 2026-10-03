"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
} from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { fmtDate, fmtPct, fmtPrice, type CandlesResponse } from "@/lib/market";

// Paleta do gráfico em hex (o canvas não deve depender de oklch), alinhada aos tokens do tema.
const PALETTE = {
  dark: {
    text: "#8b93a7",
    grid: "rgba(255,255,255,0.045)",
    border: "rgba(255,255,255,0.08)",
    crosshair: "#5b6378",
    up: "#3cc2a4",
    down: "#f0705f",
    sma200: "#e9b949",
    ema21: "#6c9cff",
    ema9: "#c792ea",
    rsi: "#6c9cff",
    rsi2: "#c792ea",
  },
  light: {
    text: "#5b6475",
    grid: "rgba(0,0,0,0.05)",
    border: "rgba(0,0,0,0.1)",
    crosshair: "#9aa3b5",
    up: "#0e9f86",
    down: "#d9483b",
    sma200: "#b7861c",
    ema21: "#2f6bed",
    ema9: "#9b4dca",
    rsi: "#2f6bed",
    rsi2: "#9b4dca",
  },
} as const;

type Overlay = "sma200" | "ema21" | "ema9" | "volume" | "rsi14" | "rsi2";

const OVERLAYS: { key: Overlay; label: string }[] = [
  { key: "sma200", label: "MMA 200" },
  { key: "ema21", label: "MME 21" },
  { key: "ema9", label: "MME 9" },
  { key: "volume", label: "Volume" },
  { key: "rsi14", label: "IFR 14" },
  { key: "rsi2", label: "IFR 2" },
];

type Legend = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  change: number | null;
};

export function PriceChart({ data }: { data: CandlesResponse }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Partial<Record<Overlay, ISeriesApi<"Line" | "Histogram">>>>({});
  const { resolvedTheme } = useTheme();
  const [visible, setVisible] = useState<Record<Overlay, boolean>>({
    sma200: true,
    ema21: true,
    ema9: false,
    volume: true,
    rsi14: true,
    rsi2: false,
  });
  const [hover, setHover] = useState<Legend | null>(null);

  const lastLegend = useMemo<Legend | null>(() => {
    const n = data.candles.length;
    if (!n) return null;
    const last = data.candles[n - 1];
    const prev = n > 1 ? data.candles[n - 2].close : null;
    return { ...last, change: prev ? (last.close / prev - 1) * 100 : null };
  }, [data.candles]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const c = PALETTE[resolvedTheme === "light" ? "light" : "dark"];

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.text,
        fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
        fontSize: 11,
        panes: { separatorColor: c.border, separatorHoverColor: c.border },
        // Atribuição exigida pela licença é feita por link na página (ver THIRD_PARTY_NOTICES.md).
        attributionLogo: false,
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: c.crosshair, labelBackgroundColor: c.crosshair },
        horzLine: { color: c.crosshair, labelBackgroundColor: c.crosshair },
      },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, rightOffset: 4 },
      localization: { locale: "pt-BR", priceFormatter: (p: number) => fmtPrice(p) },
    });
    chartRef.current = chart;

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: c.up,
      downColor: c.down,
      borderUpColor: c.up,
      borderDownColor: c.down,
      wickUpColor: c.up,
      wickDownColor: c.down,
    });
    candles.setData(data.candles.map((k) => ({ ...k, time: k.time as Time })));

    const line = (key: Overlay, color: string, pane = 0, width: 1 | 2 = 1) => {
      const series = chart.addSeries(
        LineSeries,
        {
          color,
          lineWidth: width,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        },
        pane,
      );
      const points = data.indicators[key as keyof CandlesResponse["indicators"]];
      series.setData(points.map((p) => ({ time: p.time as Time, value: p.value })));
      seriesRef.current[key] = series;
      return series;
    };

    line("sma200", c.sma200, 0, 2);
    line("ema21", c.ema21);
    line("ema9", c.ema9);

    const volume = chart.addSeries(HistogramSeries, {
      priceScaleId: "volume",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volume.setData(
      data.candles.map((k) => ({
        time: k.time as Time,
        value: k.volume,
        color: k.close >= k.open ? `${c.up}55` : `${c.down}55`,
      })),
    );
    seriesRef.current.volume = volume;

    const rsi14 = line("rsi14", c.rsi, 1);
    line("rsi2", c.rsi2, 1);
    for (const level of [30, 70]) {
      rsi14.createPriceLine({
        price: level,
        color: c.crosshair,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: false,
      });
    }
    chart.panes()[1]?.setStretchFactor(0.28);
    chart.timeScale().fitContent();

    const onMove = (param: MouseEventParams<Time>) => {
      const bar = param.seriesData.get(candles) as Legend | undefined;
      if (!param.time || !bar) {
        setHover(null);
        return;
      }
      const idx = data.candles.findIndex((k) => k.time === param.time);
      const prev = idx > 0 ? data.candles[idx - 1].close : null;
      setHover({
        time: String(param.time),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        change: prev ? (bar.close / prev - 1) * 100 : null,
      });
    };
    chart.subscribeCrosshairMove(onMove);

    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = {};
    };
  }, [data, resolvedTheme]);

  useEffect(() => {
    for (const { key } of OVERLAYS) {
      seriesRef.current[key]?.applyOptions({ visible: visible[key] });
    }
  }, [visible, data, resolvedTheme]);

  const legend = hover ?? lastLegend;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="num text-muted-foreground flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {legend && (
            <>
              <span>{fmtDate(legend.time)}</span>
              <span>
                A <span className="text-foreground">{fmtPrice(legend.open)}</span>
              </span>
              <span>
                Máx <span className="text-foreground">{fmtPrice(legend.high)}</span>
              </span>
              <span>
                Mín <span className="text-foreground">{fmtPrice(legend.low)}</span>
              </span>
              <span>
                F <span className="text-foreground">{fmtPrice(legend.close)}</span>
              </span>
              <span
                className={cn(
                  legend.change != null && legend.change > 0 && "text-up",
                  legend.change != null && legend.change < 0 && "text-down",
                )}
              >
                {fmtPct(legend.change)}
              </span>
            </>
          )}
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Indicadores">
          {OVERLAYS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              aria-pressed={visible[key]}
              onClick={() => setVisible((v) => ({ ...v, [key]: !v[key] }))}
              className={cn(
                "rounded-md border px-2 py-0.5 text-xs transition-colors",
                visible[key]
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="h-[560px] w-full" />
    </div>
  );
}
