import { FlaskConical } from "lucide-react";
import Link from "next/link";

import { EvidenceBadge } from "@/components/evidence-badge";
import { EmptyState, PageBody, PageHeader } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { WalkForwardTable } from "@/components/walkforward-table";
import { apiGet } from "@/lib/api";
import { fmtNum1, fmtNum2, fmtR, type RunSummary, type WalkForward } from "@/lib/lab";
import { fmtDate } from "@/lib/market";
import { cn } from "@/lib/utils";

export default async function LaboratorioPage() {
  const [runs, walkforward] = await Promise.all([
    apiGet<RunSummary[]>("/lab/runs").catch(() => null),
    apiGet<WalkForward[]>("/lab/walkforward").catch(() => null),
  ]);

  const approved = runs?.filter((r) => r.approved).length ?? 0;

  return (
    <PageBody>
      <PageHeader
        title="Laboratório"
        description="Cada setup testado em anos de histórico, com custos e validação fora da amostra. Só os aprovados viram sinais."
      />

      {!runs || runs.length === 0 ? (
        <EmptyState
          icon={FlaskConical}
          title={runs ? "Nenhum teste executado" : "Não foi possível carregar o laboratório"}
          description={
            runs
              ? "Rode o laboratório na API: uv run python -m ft.backtest.run"
              : "Verifique se a API está no ar."
          }
        />
      ) : (
        <>
          <div className="text-muted-foreground flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <span>
              <span className="text-foreground font-medium">{runs.length}</span> variantes testadas
            </span>
            <span>
              <span className={cn("font-medium", approved ? "text-up" : "text-foreground")}>
                {approved}
              </span>{" "}
              aprovadas
            </span>
            <span>Fora da amostra a partir de {fmtDate(runs[0].split_date)}</span>
          </div>

          {walkforward && walkforward.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Validação walk-forward</CardTitle>
                <CardDescription>
                  A cada ano, escolhe a melhor variante dos 5 anos anteriores e mede o resultado no
                  ano seguinte — como seria operar de verdade, sem conhecer o futuro.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <WalkForwardTable data={walkforward} />
              </CardContent>
            </Card>
          )}

          <h2 className="text-sm font-medium">Todas as variantes (divisão 70/30)</h2>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 border-b text-xs">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Setup</th>
                  <th className="px-3 py-2 text-left font-medium">Variante</th>
                  <th className="px-3 py-2 text-left font-medium">Evidência (fora da amostra)</th>
                  <th className="px-3 py-2 text-right font-medium">Acerto</th>
                  <th className="px-3 py-2 text-right font-medium">Fator de lucro</th>
                  <th className="px-3 py-2 text-right font-medium">Expect. dentro</th>
                  <th className="px-3 py-2 text-right font-medium">Pior sequência</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/40 transition-colors">
                    <td className="px-3 py-2">
                      <Link href={`/laboratorio/${r.id}`} className="hover:text-primary font-medium">
                        {r.setup_code} · {r.setup_name}
                      </Link>
                    </td>
                    <td className="text-muted-foreground px-3 py-2 text-xs">{r.variant}</td>
                    <td className="px-3 py-2">
                      <EvidenceBadge
                        approved={r.approved}
                        expectancy={r.out_of_sample.expectancy_r}
                        trades={r.out_of_sample.trades}
                      />
                    </td>
                    <td className="num px-3 py-2 text-right">
                      {fmtNum1(r.out_of_sample.win_rate)}%
                    </td>
                    <td className="num px-3 py-2 text-right">
                      {fmtNum2(r.out_of_sample.profit_factor)}
                    </td>
                    <td className="num text-muted-foreground px-3 py-2 text-right">
                      {fmtR(r.in_sample.expectancy_r)}
                    </td>
                    <td className="num text-muted-foreground px-3 py-2 text-right">
                      {r.out_of_sample.max_consecutive_losses ?? "—"} perdas
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-muted-foreground max-w-3xl text-xs leading-relaxed">
            R = múltiplo do risco inicial de cada trade (distância entre entrada e stop). Custos
            incluídos: taxas B3 de 0,0274% e slippage de 0,1% por lado; corretagem zero. Atenção:
            o universo é o de hoje aplicado ao passado (viés de sobrevivência), o que tende a deixar
            os resultados mais otimistas. Resultado passado não garante resultado futuro.
          </p>
        </>
      )}
    </PageBody>
  );
}
