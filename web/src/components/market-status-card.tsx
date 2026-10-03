import { Database } from "lucide-react";

import { EmptyState } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

type MarketStatus = {
  active_assets: number;
  benchmarks: number;
  last_candle_date: string | null;
  universe_ref_date: string | null;
  universe_selected: number | null;
  universe_candidates: number | null;
  last_run: {
    status: "running" | "success" | "failed";
    started_at: string;
    finished_at: string | null;
    assets_updated: number | null;
    errors: number | null;
  } | null;
};

const dateFmt = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });
const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: "America/Sao_Paulo",
});

const RUN_LABEL = { running: "Em execução", success: "Concluída", failed: "Falhou" } as const;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="num text-right font-medium">{children}</span>
    </div>
  );
}

export async function MarketStatusCard() {
  let status: MarketStatus;
  try {
    status = await apiGet<MarketStatus>("/market/status");
  } catch {
    return (
      <EmptyState
        icon={Database}
        title="Dados de mercado"
        description="Não foi possível consultar o status da coleta. Verifique se a API está no ar."
      />
    );
  }

  const run = status.last_run;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="text-muted-foreground size-4" aria-hidden="true" />
          Dados de mercado
        </CardTitle>
        <CardDescription>Coleta diária pós-fechamento (Yahoo Finance).</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        <Row label="Último pregão carregado">
          {status.last_candle_date ? dateFmt.format(new Date(status.last_candle_date)) : "—"}
        </Row>
        <Row label="Universo líquido">
          {status.universe_selected !== null
            ? `${status.universe_selected} de ${status.universe_candidates} do IBrX-100`
            : "—"}
        </Row>
        <Row label="Referências">{status.benchmarks > 0 ? "BOVA11, SMAL11" : "—"}</Row>
        <Row label="Última coleta">
          {run ? (
            <span
              className={cn(
                run.status === "success" && "text-up",
                run.status === "failed" && "text-down",
              )}
            >
              {RUN_LABEL[run.status]} · {dateTimeFmt.format(new Date(run.started_at))}
            </span>
          ) : (
            "—"
          )}
        </Row>
        {run?.errors ? <Row label="Ativos com erro na coleta">{run.errors}</Row> : null}
      </CardContent>
    </Card>
  );
}
