import { ChartCandlestick } from "lucide-react";

import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "bg-primary text-primary-foreground flex size-8 shrink-0 items-center justify-center rounded-md",
        className,
      )}
      aria-hidden="true"
    >
      <ChartCandlestick className="size-4.5" strokeWidth={2.25} />
    </span>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2">
      <LogoMark />
      <span className="text-sm font-semibold tracking-tight">FinanceTracker</span>
    </span>
  );
}
