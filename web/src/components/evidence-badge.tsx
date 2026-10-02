import { cn } from "@/lib/utils";
import { fmtR } from "@/lib/lab";

/**
 * Assinatura do produto: a evidência estatística acompanha o setup/sinal.
 * Expectativa fora da amostra em R + número de trades que a sustentam.
 */
export function EvidenceBadge({
  expectancy,
  trades,
  approved,
  label,
  className,
}: {
  expectancy: number | null | undefined;
  trades: number | null | undefined;
  approved: boolean;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "num inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        approved
          ? "border-up/40 bg-up/10 text-up"
          : "border-border bg-muted text-muted-foreground",
        className,
      )}
      title="Expectativa por trade fora da amostra, em múltiplos do risco (R)"
    >
      {label ?? (approved ? "Aprovado" : "Reprovado")}
      <span className="opacity-60">·</span>
      {fmtR(expectancy)}
      <span className="opacity-60">em {trades ?? 0} trades</span>
    </span>
  );
}
