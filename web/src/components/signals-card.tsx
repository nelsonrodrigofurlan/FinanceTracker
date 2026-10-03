import { Radar } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/page";
import { StatusBadge } from "@/components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { fmtDate, fmtPrice } from "@/lib/market";
import { ORDER_LABEL, type Signal } from "@/lib/signals";

export async function SignalsCard({ className }: { className?: string }) {
  const signals = await apiGet<Signal[]>("/signals/latest").catch(() => null);

  if (!signals || signals.length === 0) {
    return (
      <EmptyState
        className={className}
        icon={Radar}
        title="Sem sinais no último pregão"
        description="O scanner só gera sinais de estratégias aprovadas ou em observação no laboratório. Hoje, nenhuma passou nos critérios."
      />
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Sinais de {fmtDate(signals[0].signal_date)}</CardTitle>
        <CardDescription>
          {signals.length} sinal(is).{" "}
          <Link href="/scanner" className="underline">
            Ver detalhes no Scanner
          </Link>
        </CardDescription>
      </CardHeader>
      <CardContent className="divide-y text-sm">
        {signals.slice(0, 6).map((s) => (
          <div key={s.id} className="flex items-center justify-between gap-3 py-2">
            <span className="font-medium">{s.ticker}</span>
            <span className="text-muted-foreground text-xs">
              {s.setup_code} · {ORDER_LABEL[s.order_kind]}
            </span>
            <span className="num">{fmtPrice(s.entry_estimate)}</span>
            <StatusBadge status={s.status} />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
