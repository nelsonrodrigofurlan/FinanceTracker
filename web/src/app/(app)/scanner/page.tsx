import { FlaskConical, Radar } from "lucide-react";
import Link from "next/link";

import { EmptyState, PageBody, PageHeader } from "@/components/page";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { fmtR } from "@/lib/lab";
import { fmtDate, fmtPrice } from "@/lib/market";
import { ORDER_LABEL, type Signal, type Strategy } from "@/lib/signals";

export default async function ScannerPage() {
  const [strategies, signals] = await Promise.all([
    apiGet<Strategy[]>("/strategies").catch(() => null),
    apiGet<Signal[]>("/signals/latest").catch(() => null),
  ]);
  const operable = strategies?.filter((s) => s.status !== "rejected") ?? [];
  const rejected = (strategies?.length ?? 0) - operable.length;

  return (
    <PageBody>
      <PageHeader
        title="Scanner"
        description="Sinais do último pregão, apenas de estratégias aprovadas ou em observação no laboratório."
      />

      {signals && signals.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Sinais de {fmtDate(signals[0].signal_date)}</CardTitle>
            <CardDescription>
              Estratégias em observação operam só no modo simulado. Quantidade calculada pelos seus
              Ajustes. Ferramenta de análise; não é recomendação de investimento.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground border-b text-xs">
                <tr>
                  <th className="py-2 text-left font-medium">Ativo</th>
                  <th className="py-2 text-left font-medium">Estratégia</th>
                  <th className="py-2 text-left font-medium">Ordem</th>
                  <th className="py-2 text-right font-medium">Entrada</th>
                  <th className="py-2 text-right font-medium">Stop</th>
                  <th className="py-2 text-right font-medium">Alvo</th>
                  <th className="py-2 text-right font-medium">Qtde</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {signals.map((s) => (
                  <tr key={s.id}>
                    <td className="py-2 font-medium">
                      <Link href={`/ativos/${s.ticker}`} className="hover:text-primary">
                        {s.ticker}
                      </Link>
                    </td>
                    <td className="py-2">
                      <div className="flex flex-col gap-1">
                        <span>
                          {s.setup_code} · {s.setup_name}
                        </span>
                        <StatusBadge status={s.status} />
                      </div>
                    </td>
                    <td className="text-muted-foreground py-2 text-xs">
                      {ORDER_LABEL[s.order_kind]}
                    </td>
                    <td className="num py-2 text-right">
                      {s.entry_is_estimate && "≈ "}
                      {fmtPrice(s.entry_estimate)}
                    </td>
                    <td className="num text-down py-2 text-right">{fmtPrice(s.stop_estimate)}</td>
                    <td className="num text-up py-2 text-right">{fmtPrice(s.target_estimate)}</td>
                    <td className="num py-2 text-right">
                      {s.quantity ?? (
                        <Link href="/ajustes" className="text-muted-foreground text-xs underline">
                          definir ajustes
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          icon={Radar}
          title="Nenhum sinal no último pregão"
          description={
            operable.length === 0
              ? "Nenhuma estratégia está aprovada ou em observação. O scanner só gera sinais do que passou no laboratório, e hoje nada passou."
              : "As estratégias operáveis não encontraram setup no último pregão."
          }
        />
      )}

      <Card>
        <CardHeader>
          <CardTitle>Estratégias</CardTitle>
          <CardDescription>
            {operable.length} operáveis · {rejected} reprovadas. Status definido por regra a partir
            do laboratório (fora da amostra, walk-forward e comparação com o CDI).
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {strategies && strategies.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="text-muted-foreground border-b text-xs">
                <tr>
                  <th className="py-2 text-left font-medium">Estratégia</th>
                  <th className="py-2 text-left font-medium">Variante</th>
                  <th className="py-2 text-left font-medium">Status</th>
                  <th className="py-2 text-right font-medium">Walk-forward</th>
                  <th className="py-2 text-right font-medium">Carteira (fora)</th>
                  <th className="py-2 text-right font-medium">CDI</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {strategies.map((s) => (
                  <tr key={s.id}>
                    <td className="py-1.5">
                      {s.setup_code} · {s.setup_name}
                    </td>
                    <td className="text-muted-foreground py-1.5 text-xs">{s.variant}</td>
                    <td className="py-1.5">
                      <StatusBadge status={s.status} />
                    </td>
                    <td className="num py-1.5 text-right">
                      {fmtR(s.evidence.walkforward_expectancy_r)}
                    </td>
                    <td className="num py-1.5 text-right">
                      {s.evidence.portfolio_cagr_pct != null
                        ? `${s.evidence.portfolio_cagr_pct}%`
                        : "—"}
                    </td>
                    <td className="num text-muted-foreground py-1.5 text-right">
                      {s.evidence.cdi_cagr_pct != null ? `${s.evidence.cdi_cagr_pct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState
              icon={FlaskConical}
              title="Nenhuma estratégia classificada"
              description="Rode o laboratório e a classificação: uv run python -m ft.signals.strategies"
            />
          )}
        </CardContent>
      </Card>
    </PageBody>
  );
}
