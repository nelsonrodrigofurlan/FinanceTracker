"use server";

import { revalidatePath } from "next/cache";

import { ApiError, apiSend } from "@/lib/api";
import type { UserSettings } from "@/lib/settings";

export type SaveState = { error: string | null; saved: boolean };

function parseNumber(raw: FormDataEntryValue | null): number | null {
  const text = String(raw ?? "").trim().replace(/\./g, "").replace(",", ".");
  if (!text) return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : NaN;
}

export async function saveSettings(_prev: SaveState, form: FormData): Promise<SaveState> {
  const body: UserSettings = {
    sim_capital: parseNumber(form.get("sim_capital")),
    risk_pct: parseNumber(form.get("risk_pct")),
    max_positions: parseNumber(form.get("max_positions")),
    max_position_pct: parseNumber(form.get("max_position_pct")),
  };
  if (Object.values(body).some((v) => Number.isNaN(v))) {
    return { error: "Use apenas números.", saved: false };
  }
  try {
    await apiSend<UserSettings>("/settings", "PUT", body);
  } catch (error) {
    if (error instanceof ApiError && error.status === 422) {
      return { error: "Algum valor está fora dos limites permitidos.", saved: false };
    }
    return { error: "Não foi possível salvar. Tente novamente.", saved: false };
  }
  revalidatePath("/ajustes");
  return { error: null, saved: true };
}
