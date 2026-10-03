"use server";

import { apiSend } from "@/lib/api";

export type ExplainResult = {
  content?: string;
  model?: string;
  cost_usd?: number | null;
  error?: string;
};

export async function explainSignal(signalId: number): Promise<ExplainResult> {
  if (!Number.isInteger(signalId) || signalId < 1) return { error: "Sinal inválido." };
  try {
    const r = await apiSend<{ content: string; model: string; cost_usd: number | null }>(
      `/signals/${signalId}/explain`,
      "POST",
      {},
    );
    return { content: r.content, model: r.model, cost_usd: r.cost_usd };
  } catch {
    return { error: "Explicação indisponível no momento." };
  }
}
