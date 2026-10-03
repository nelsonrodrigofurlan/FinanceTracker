"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiSend } from "@/lib/api";
import { parseBR } from "@/lib/journal";

export type FormState = { error: string | null; ok: boolean };

function apiError(error: unknown): FormState {
  if (error instanceof ApiError && error.status === 422) {
    return { error: "Confira os valores: algum está fora das regras.", ok: false };
  }
  return { error: "Não foi possível salvar. Tente novamente.", ok: false };
}

export async function createTrade(_prev: FormState, form: FormData): Promise<FormState> {
  const numbers = {
    entry_price: parseBR(form.get("entry_price")),
    quantity: parseBR(form.get("quantity")),
    stop_planned: parseBR(form.get("stop_planned")),
    target_planned: parseBR(form.get("target_planned")),
    entry_fees: parseBR(form.get("entry_fees")) ?? 0,
  };
  if (Object.values(numbers).some((v) => Number.isNaN(v))) {
    return { error: "Use apenas números nos campos de valor.", ok: false };
  }
  if (numbers.entry_price == null || numbers.quantity == null) {
    return { error: "Informe preço de entrada e quantidade.", ok: false };
  }
  if (numbers.stop_planned != null && numbers.stop_planned >= numbers.entry_price) {
    return { error: "O stop precisa ficar abaixo do preço de entrada.", ok: false };
  }
  const emotion = String(form.get("emotion") ?? "") || null;
  const reason = String(form.get("reason") ?? "").trim() || null;
  try {
    await apiSend("/journal", "POST", {
      ticker: String(form.get("ticker") ?? ""),
      entry_date: String(form.get("entry_date") ?? ""),
      ...numbers,
      emotion,
      reason,
    });
  } catch (error) {
    return apiError(error);
  }
  revalidatePath("/diario");
  return { error: null, ok: true };
}

export async function closeTrade(_prev: FormState, form: FormData): Promise<FormState> {
  const id = Number(form.get("id"));
  const exitPrice = parseBR(form.get("exit_price"));
  const exitFees = parseBR(form.get("exit_fees")) ?? 0;
  if (!Number.isInteger(id) || id < 1) return { error: "Trade inválido.", ok: false };
  if (exitPrice == null || Number.isNaN(exitPrice) || Number.isNaN(exitFees)) {
    return { error: "Informe o preço de saída.", ok: false };
  }
  try {
    await apiSend(`/journal/${id}/close`, "PUT", {
      exit_date: String(form.get("exit_date") ?? ""),
      exit_price: exitPrice,
      exit_fees: exitFees,
      exit_notes: String(form.get("exit_notes") ?? "").trim() || null,
    });
  } catch (error) {
    return apiError(error);
  }
  revalidatePath("/diario");
  return { error: null, ok: true };
}

export async function deleteTrade(id: number): Promise<FormState> {
  if (!Number.isInteger(id) || id < 1) return { error: "Trade inválido.", ok: false };
  try {
    await apiSend(`/journal/${id}`, "DELETE");
  } catch (error) {
    return apiError(error);
  }
  revalidatePath("/diario");
  return { error: null, ok: true };
}
