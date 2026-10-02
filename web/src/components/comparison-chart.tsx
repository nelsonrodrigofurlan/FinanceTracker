"use client";

import { ColorType, createChart, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

export type ComparisonSeries = {
  key: string;
  label: string;
  points: { time: string; value: number }[];
};

// Setup em azul (assinatura), CDI em dourado, BOVA11 em cinza.
const COLORS = {
  dark: { text: "#8b93a7", grid: "rgba(255,255,255,0.045)", base: "#5b6378", series: ["#6c9cff", "#e9b949", "#8b93a7"] },
  light: { text: "#5b6475", grid: "rgba(0,0,0,0.05)", base: "#9aa3b5", series: ["#2f6bed", "#b7861c", "#5b6475"] },
} as const;

const brl = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });

export function ComparisonChart({
  series,
  baseline,
}: {
  series: ComparisonSeries[];
  baseline: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    if (!ref.current) return;
    const c = COLORS[resolvedTheme === "light" ? "light" : "dark"];
    const chart = createChart(ref.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: c.text,
        fontSize: 11,
        attributionLogo: false, // atribuição por link na página (THIRD_PARTY_NOTICES.md)
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: { locale: "pt-BR", priceFormatter: (v: number) => `R$ ${brl.format(v)}` },
    });

    series.forEach((s, i) => {
      const line = chart.addSeries(LineSeries, {
        color: c.series[i % c.series.length],
        lineWidth: i === 0 ? 2 : 1,
        priceLineVisible: false,
        title: s.label,
      });
      line.setData(s.points.map((p) => ({ time: p.time as Time, value: p.value })));
      if (i === 0) {
        line.createPriceLine({
          price: baseline,
          color: c.base,
          lineStyle: LineStyle.Dashed,
          lineWidth: 1,
          axisLabelVisible: false,
        });
      }
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, baseline, resolvedTheme]);

  return <div ref={ref} className="h-80 w-full" />;
}
