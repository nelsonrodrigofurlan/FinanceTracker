import { AlertTriangle, NotebookPen } from "lucide-react";

import { EmptyState, Metric, PageBody, PageHeader } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { EMOTIONS, fmtBRL, type Journal, type JournalTrade } from "@/lib/journal";
import { EXIT_LABEL, fmtNum1, fmtR } from "@/lib/lab";
import { fmtDate, fmtPct, fmtPrice } from "@/lib/market";
import type { SimBook, SimTrade } from "@/lib/signals";
import { cn } from "@/lib/utils";

import { CloseTradeForm, DeleteTradeButton, NewTradeForm } from "./journal-forms";

const tone = (v: number | null | undefined) =>
  v == null ? undefined : v > 0 ? "text-up" : v < 0 ? "text-down" : undefined;

/* ----------------------------- Trades reais ----------------------------- */

function RealTradeRow({ t }: { t: JournalTrade }) {
  const open = t.status === "open";
  return (
    <tr className="align-top">
      <td className="py-2 font-medium">
        {t.ticker}
        {t.strategy_status && t.strategy_status !== "approved" && (
          <span
            className="text-warning ml-1"
            title="Ligado a uma estratégia não aprovada no laboratório"
          >
            <AlertTriangle className="inline size-3.5" aria-label="estratégia não aprovada" />
          </span>
        )}
      </td>
      <td className="num text-muted-foreground py-2">
        {fmtDate(t.entry_date)} · {fmtPrice(t.entry_price)} × {t.quantity}
        <div className="text-xs">
          stop {fmtPrice(t.stop_planned)}
          {t.target_planned != null && ` · alvo ${fmtPrice(t.target_planned)}`}
        </div>
      </td>
      <td className="text-muted-foreground py-2 text-xs">
        {t.emotion ? EMOTIONS[t.emotion] : "—"}
        {t.reason && <div className="max-w-56 truncate" title={t.reason}>{t.reason}</div>}
      </td>
      <td className="py-2">
        {open ? (
          <CloseTradeForm id={t.id} entryDate={t.entry_date} />
        ) : (
          <span className="num text-muted-foreground">
            {fmtDate(t.exit_date)} · {fmtPrice(t.exit_price)}
            <span className="block text-xs">{t.holding_days} dias</span>
          </span>
        )}
      </td>
      <td className={cn("num py-2 text-right", tone(t.pnl))}>
        {open ? "—" : fmtBRL(t.pnl)}
        {!open && <span className="block text-xs">{fmtPct(t.return_pct)}</span>}
      </td>
      <td className={cn("num py-2 text-right font-medium", tone(t.r_multiple))}>
        {open ? "—" : fmtR(t.r_multiple)}
      </td>
      <td className="py-2 text-right">
        <DeleteTradeButton id={t.id} ticker={t.ticker} />
      </td>
    </tr>
  );
}

function RealTrades({ journal }: { journal: Journal | null }) {
  if (!journal) {
    return (
      <EmptyState
        icon={NotebookPen}
        title="Não foi possível carregar o diário"
        description="Verifique se a API está no ar."
      />
    );
  }
  const s = journal.summary;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trades reais</CardTitle>
        <CardDescription>
          O que você operou na corretora. O app não envia ordens; só registra e calcula. Imposto
          de renda não é calculado.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Metric label="Abertos / encerrados" value={`${s.open_count} / ${s.closed_count}`} />
          <Metric
            label="Resultado (líquido de custos)"
            value={s.closed_count ? fmtBRL(s.total_pnl) : null}
            tone={s.total_pnl > 0 ? "up" : s.total_pnl < 0 ? "down" : "neutral"}
          />
          <Metric label="Média em R" value={s.avg_r != null ? fmtR(s.avg_r) : null} />
          <Metric label="Acerto" value={s.win_rate != null ? `${fmtNum1(s.win_rate)}%` : null} />
          <Metric
            label="Com stop definido"
            value={s.with_stop_pct != null ? `${fmtNum1(s.with_stop_pct)}%` : null}
            hint="disciplina"
          />
        </section>
        {s.non_approved_count > 0 && (
          <p className="text-warning flex items-center gap-2 text-sm">
            <AlertTriangle className="size-4" />
            {s.non_approved_count} trade(s) ligado(s) a estratégia não aprovada no laboratório.
          </p>
        )}
        <NewTradeForm />
        {journal.trades.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground border-b text-xs">
                <tr>
                  <th className="py-2 text-left font-medium">Ativo</th>
                  <th className="py-2 text-left font-medium">Entrada</th>
                  <th className="py-2 text-left font-medium">Emoção / motivo</th>
                  <th className="py-2 text-left font-medium">Saída</th>
                  <th className="py-2 text-right font-medium">Resultado</th>
                  <th className="py-2 text-right font-medium">R</th>
                  <th className="py-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {journal.trades.map((t) => (
                  <RealTradeRow key={t.id} t={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/* ------------------------------- Simulado ------------------------------- */

function exitText(t: SimTrade) {
  const reason = t.exit_reason ? (EXIT_LABEL[t.exit_reason] ?? t.exit_reason) : "";
  return `${fmtDate(t.exit_date)} · ${fmtPrice(t.exit_price)} · ${reason}`;
}

function SimTable({ trades, open }: { trades: SimTrade[]; open: boolean }) {
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
            <td className={cn("num py-1.5 text-right font-medium", tone(t.r_multiple))}>
              {fmtR(t.r_multiple)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Simulated({ book }: { book: SimBook | null }) {
  const empty = !book || (book.open.length === 0 && book.closed_count === 0);
  if (empty || !book) {
    return (
      <EmptyState
        icon={NotebookPen}
        title="Nenhuma operação simulada ainda"
        description="A carteira simulada começa quando uma estratégia fica aprovada ou em observação no laboratório. Não há histórico retroativo: o que vale é o desempenho ao vivo."
      />
    );
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Operação simulada</CardTitle>
        <CardDescription>
          Mesmo motor do laboratório, a partir da data em que a estratégia passou a ser operável.
          {` ${book.closed_count} encerradas · ${fmtR(book.total_r)} · acerto `}
          {book.win_rate != null ? `${fmtNum1(book.win_rate)}%` : "—"}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6 overflow-x-auto">
        {book.open.length > 0 && <SimTable trades={book.open} open />}
        {book.closed.length > 0 && <SimTable trades={book.closed} open={false} />}
      </CardContent>
    </Card>
  );
}

export default async function DiarioPage() {
  const [journal, book] = await Promise.all([
    apiGet<Journal>("/journal").catch(() => null),
    apiGet<SimBook>("/sim/book").catch(() => null),
  ]);

  return (
    <PageBody>
      <PageHeader
        title="Diário"
        description="Seus trades reais e a operação simulada lado a lado: compare o que você fez com o que o plano previa."
      />
      <RealTrades journal={journal} />
      <h2 className="text-sm font-medium">Simulado</h2>
      <Simulated book={book} />
    </PageBody>
  );
}
