import { cn } from "@/lib/utils";
import { STATUS_LABEL, type StrategyStatus } from "@/lib/signals";

export function StatusBadge({ status }: { status: StrategyStatus }) {
  return (
    <span
      className={cn(
        "inline-flex rounded-md border px-2 py-0.5 text-xs font-medium",
        status === "approved" && "border-up/40 bg-up/10 text-up",
        status === "observation" && "border-warning/40 bg-warning/10 text-warning",
        status === "rejected" && "border-border bg-muted text-muted-foreground",
      )}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
