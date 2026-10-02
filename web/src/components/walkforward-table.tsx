import { EvidenceBadge } from "@/components/evidence-badge";
import { fmtR, type WalkForward } from "@/lib/lab";
import { cn } from "@/lib/utils";

/** Walk-forward por setup: a escolha de cada ano usa só os anos anteriores. */
export function WalkForwardTable({ data }: { data: WalkForward[] }) {
  return (
    <div className="flex flex-col gap-3">
      {data.map((wf) => {
        const positive = (wf.expectancy_r ?? 0) > 0;
        return (
          <div key={wf.setup_code} className="rounded-lg border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">
                {wf.setup_code} · {wf.setup_name}
              </span>
              <EvidenceBadge
                approved={positive && wf.trades >= 30}
                expectancy={wf.expectancy_r}
                trades={wf.trades}
                label={positive ? "Vantagem" : "Sem vantagem"}
              />
            </div>
            <div className="mt-3 flex flex-wrap gap-1" aria-label="Resultado por ano">
              {wf.years.map((y) => (
                <span
                  key={y.year}
                  title={`${y.year}: ${y.would_trade ? `${fmtR(y.expectancy_r)} em ${y.trades} trades · variante ${y.chosen_variant}` : "não operaria (melhor do passado era negativo)"}`}
                  className={cn(
                    "num rounded px-1.5 py-0.5 text-[11px]",
                    !y.would_trade && "bg-muted text-muted-foreground",
                    y.would_trade && y.total_r > 0 && "bg-up/15 text-up",
                    y.would_trade && y.total_r <= 0 && "bg-down/15 text-down",
                  )}
                >
                  {String(y.year).slice(2)}
                </span>
              ))}
            </div>
            <p className="text-muted-foreground mt-2 text-xs">
              {wf.years_positive ?? 0} de {wf.years_traded ?? 0} anos operados positivos · cinza =
              ano em que o melhor do passado já era negativo (não operaria).
            </p>
          </div>
        );
      })}
    </div>
  );
}
