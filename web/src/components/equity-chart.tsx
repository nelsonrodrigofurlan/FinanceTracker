"use client";

import { ColorType, createChart, LineSeries, LineStyle, type Time } from "lightweight-charts";
import { useTheme } from "next-themes";
import { useEffect, useRef } from "react";

const COLORS = {
  dark: { text: "#8b93a7", grid: "rgba(255,255,255,0.045)", in: "#5b6378", out: "#6c9cff", zero: "#5b6378" },
  light: { text: "#5b6475", grid: "rgba(0,0,0,0.05)", in: "#9aa3b5", out: "#2f6bed", zero: "#9aa3b5" },
} as const;

/** Curva de resultado acumulado em R. Cinza = dentro da amostra; azul = fora da amostra. */
export function EquityChart({
  points,
  splitDate,
}: {
  points: { time: string; value: number }[];
  splitDate: string;
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
      localization: { locale: "pt-BR", priceFormatter: (v: number) => `${v.toFixed(0)}R` },
    });

    const inSample = points.filter((p) => p.time < splitDate);
    // O trecho fora da amostra começa no último ponto de dentro, para a linha não ter buraco.
    const outSample = points.filter((p) => p.time >= splitDate);
    const bridge = inSample.length ? [inSample[inSample.length - 1]] : [];

    const sIn = chart.addSeries(LineSeries, { color: c.in, lineWidth: 2, priceLineVisible: false });
    sIn.setData(inSample.map((p) => ({ time: p.time as Time, value: p.value })));
    const sOut = chart.addSeries(LineSeries, { color: c.out, lineWidth: 2, priceLineVisible: false });
    sOut.setData([...bridge, ...outSample].map((p) => ({ time: p.time as Time, value: p.value })));
    sOut.createPriceLine({
      price: 0,
      color: c.zero,
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      axisLabelVisible: false,
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points, splitDate, resolvedTheme]);

  return <div ref={ref} className="h-72 w-full" />;
}
