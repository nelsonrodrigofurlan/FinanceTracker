import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="text-muted-foreground text-sm">{description}</p>}
    </div>
  );
}

export function PageBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 p-6", className)}>
      {children}
    </div>
  );
}

/** Estado vazio: um convite, não um pedido de desculpas. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  phase,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  phase?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center",
        className,
      )}
    >
      <span className="bg-muted text-muted-foreground flex size-10 items-center justify-center rounded-full">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-1">
        <p className="font-medium">{title}</p>
        <p className="text-muted-foreground max-w-md text-sm">{description}</p>
      </div>
      {phase && (
        <span className="text-muted-foreground bg-muted rounded px-2 py-0.5 font-mono text-[11px]">
          {phase}
        </span>
      )}
    </div>
  );
}

/** Indicador numérico. Valor ausente aparece como travessão, nunca como zero inventado. */
export function Metric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string | null;
  hint?: string;
  tone?: "neutral" | "up" | "down";
}) {
  return (
    <div className="bg-card flex flex-col gap-1 rounded-lg border p-4">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span
        className={cn(
          "num text-2xl font-semibold tracking-tight",
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          value === null && "text-muted-foreground",
        )}
      >
        {value ?? "—"}
      </span>
      {hint && <span className="text-muted-foreground text-xs">{hint}</span>}
    </div>
  );
}
