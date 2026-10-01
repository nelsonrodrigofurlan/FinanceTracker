"use client";

import { ArrowDown, ArrowUp, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { fmtMillions, fmtPct, fmtPrice, type AssetSummary } from "@/lib/market";

type SortKey = "ticker" | "change_pct" | "avg_fin_volume_21";

export function AssetsTable({ assets }: { assets: AssetSummary[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({
    key: "avg_fin_volume_21",
    desc: true,
  });

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    const filtered = assets.filter(
      (a) => !q || a.ticker.includes(q) || (a.name ?? "").toUpperCase().includes(q),
    );
    const dir = sort.desc ? -1 : 1;
    return [...filtered].sort((a, b) => {
      const va = a[sort.key];
      const vb = b[sort.key];
      if (va == null) return 1;
      if (vb == null) return -1;
      return va < vb ? -dir : va > vb ? dir : 0;
    });
  }, [assets, query, sort]);

  const header = (key: SortKey, label: string, align: "left" | "right" = "right") => (
    <th className={cn("px-3 py-2 font-medium", align === "right" ? "text-right" : "text-left")}>
      <button
        type="button"
        className="hover:text-foreground inline-flex items-center gap-1"
        onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : true }))}
      >
        {label}
        {sort.key === key &&
          (sort.desc ? <ArrowDown className="size-3" /> : <ArrowUp className="size-3" />)}
      </button>
    </th>
  );

  return (
    <div className="flex flex-col gap-3">
      <div className="relative max-w-xs">
        <Search className="text-muted-foreground absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filtrar por ticker ou empresa"
          className="pl-8"
          aria-label="Filtrar ativos"
        />
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead className="text-muted-foreground bg-muted/40 border-b text-xs">
            <tr>
              {header("ticker", "Ativo", "left")}
              <th className="px-3 py-2 text-left font-medium">Empresa</th>
              <th className="px-3 py-2 text-right font-medium">Último</th>
              {header("change_pct", "Var. dia")}
              {header("avg_fin_volume_21", "Vol. fin. médio 21d (R$)")}
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((a) => (
              <tr key={a.ticker} className="hover:bg-muted/40 transition-colors">
                <td className="px-3 py-2 font-medium">
                  <Link href={`/ativos/${a.ticker}`} className="hover:text-primary">
                    {a.ticker}
                  </Link>
                  {a.is_benchmark && (
                    <span className="text-muted-foreground bg-muted ml-2 rounded px-1.5 py-0.5 text-[10px]">
                      referência
                    </span>
                  )}
                </td>
                <td className="text-muted-foreground px-3 py-2">{a.name ?? "—"}</td>
                <td className="num px-3 py-2 text-right">{fmtPrice(a.last_close)}</td>
                <td
                  className={cn(
                    "num px-3 py-2 text-right",
                    a.change_pct != null && a.change_pct > 0 && "text-up",
                    a.change_pct != null && a.change_pct < 0 && "text-down",
                  )}
                >
                  {fmtPct(a.change_pct)}
                </td>
                <td className="num text-muted-foreground px-3 py-2 text-right">
                  {fmtMillions(a.avg_fin_volume_21)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="text-muted-foreground px-3 py-8 text-center">
                  Nenhum ativo encontrado para “{query}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-muted-foreground text-xs">
        {rows.length} de {assets.length} ativos · universo líquido do IBrX-100 + referências.
      </p>
    </div>
  );
}
