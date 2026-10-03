"use client";

import { Sparkles } from "lucide-react";
import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

import { explainSignal, type ExplainResult } from "./actions";

/** Botão "Explicar" + texto da IA. Uma explicação por sinal (gerada uma vez e reaproveitada). */
export function ExplainSignal({ signalId }: { signalId: number }) {
  const [result, setResult] = useState<ExplainResult | null>(null);
  const [pending, start] = useTransition();

  if (result?.content) {
    return (
      <div className="bg-muted/40 mt-2 rounded-md p-3 text-sm leading-relaxed whitespace-pre-line">
        {result.content}
        <p className="text-muted-foreground mt-2 text-[11px]">
          Gerado por {result.model}
          {result.cost_usd != null && ` · custo US$ ${result.cost_usd.toFixed(4)}`}
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={pending}
        onClick={() => start(async () => setResult(await explainSignal(signalId)))}
      >
        <Sparkles className="size-3.5" />
        {pending ? "Gerando…" : "Explicar"}
      </Button>
      {result?.error && <span className="text-destructive text-xs">{result.error}</span>}
    </div>
  );
}
