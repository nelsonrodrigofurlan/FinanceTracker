import { NotebookPen } from "lucide-react";

import { EmptyState, Metric, PageBody, PageHeader } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { EXIT_LABEL, fmtNum1, fmtR } from "@/lib/lab";
import { fmtDate, fmtPrice } from "@/lib/market";
import type { SimBook, SimTrade } from "@/lib/signals";
import { cn } from "@/lib/utils";

function exitText(t: SimTrade) {
  const reason = t.exit_reason ? (EXIT_LABEL[t.exit_reason] ?? t.exit_reason) : "";
  return `${fmtDate(t.exit_date)} · ${fmtPrice(t.exit_price)} · ${reason}`;
}

function TradeTable({ trades, open }: { trades: SimTrade[]; open: boolean }) {
  return (
    <table className="w-full text-sm">
      <thead className="text-muted-foreground border-b text-xs">
        <tr>
          <th className="py-2 text-left font-medium">Ativo</th>
          <th className="py-2 text-left font-medium">Estratégia</th>
          <th className="py-2 text-left font-medium">Entrada</th>
          <th className="py-2 text-right font-medium">Stop</th>
          <th className="py-2 text-left font-medium">{open ? "Último preço" : "Saída"}</th>
          <th className="py-2 text-right font-medium">{open ? "R (aberto)" : "Resultado"}</th>
        </tr>
      </thead>
      <tbody className="divide-y">
        {trades.map((t) => (
          <tr key={`${t.setup_code}-${t.ticker}-${t.entry_date}`}>
            <td className="py-1.5 font-medium">{t.ticker}</td>
            <td className="text-muted-foreground py-1.5 text-xs">
              {t.setup_code} · {t.variant}
            </td>
            <td className="num text-muted-foreground py-1.5">
              {fmtDate(t.entry_date)} · {fmtPrice(t.entry_price)}
            </td>
            <td className="num py-1.5 text-right">{fmtPrice(t.initial_stop)}</td>
            <td className="num text-muted-foreground py-1.5">
              {open ? fmtPrice(t.exit_price) : exitText(t)}
            </td>
            <td
              className={cn(
                "num py-1.5 text-right font-medium",
                t.r_multiple > 0 && "text-up",
                t.r_multiple < 0 && "text-down",
              )}
            >
              {fmtR(t.r_multiple)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default async function DiarioPage() {
  const book = await apiGet<SimBook>("/sim/book").catch(() => null);
  const empty = !book || (book.open.length === 0 && book.closed_count === 0);

  return (
    <PageBody>
      <PageHeader
        title="Diário"
        description="Operação simulada ao vivo: o mesmo motor do laboratório, aplicado a partir da data em que a estratégia passou a ser operável."
      />
      {empty || !book ? (
        <EmptyState
          icon={NotebookPen}
          title="Nenhuma operação simulada ainda"
          description="A carteira simulada começa quando uma estratégia fica aprovada ou em observação. Não há histórico retroativo: o que vale é o desempenho ao vivo."
        />
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric label="Posições abertas" value={String(book.open.length)} />
            <Metric label="Operações encerradas" value={String(book.closed_count)} />
            <Metric
              label="Resultado acumulado"
              value={fmtR(book.total_r)}
              tone={book.total_r > 0 ? "up" : book.total_r < 0 ? "down" : "neutral"}
            />
            <Metric
              label="Acerto"
              value={book.win_rate != null ? `${fmtNum1(book.win_rate)}%` : null}
            />
          </section>
          {book.open.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Posições abertas (simuladas)</CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                <TradeTable trades={book.open} open />
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>Operações encerradas (simuladas)</CardTitle>
              <CardDescription>As 100 mais recentes.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <TradeTable trades={book.closed} open={false} />
            </CardContent>
          </Card>
        </>
      )}
    </PageBody>
  );
}
