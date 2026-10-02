"use client";

import { useActionState } from "react";

import { FormError } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SETTINGS_LIMITS, type UserSettings } from "@/lib/settings";

import { saveSettings, type SaveState } from "./actions";

function Field({
  name,
  label,
  hint,
  defaultValue,
  suffix,
}: {
  name: keyof UserSettings;
  label: string;
  hint: string;
  defaultValue: number | null;
  suffix?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <Input
          name={name}
          inputMode="decimal"
          defaultValue={defaultValue === null ? "" : String(defaultValue).replace(".", ",")}
          className="num max-w-48"
        />
        {suffix && <span className="text-muted-foreground">{suffix}</span>}
      </div>
      <span className="text-muted-foreground text-xs">{hint}</span>
    </label>
  );
}

export function SettingsForm({ current }: { current: UserSettings }) {
  const [state, action, pending] = useActionState<SaveState, FormData>(saveSettings, {
    error: null,
    saved: false,
  });

  return (
    <form action={action} className="flex flex-col gap-5">
      <Field
        name="sim_capital"
        label="Capital do modo simulado"
        hint="Valor fictício usado para acompanhar a carteira simulada."
        defaultValue={current.sim_capital}
        suffix="R$"
      />
      <Field
        name="risk_pct"
        label="Risco por operação"
        hint={`Quanto do capital perder se o stop for atingido (${SETTINGS_LIMITS.risk_pct}%).`}
        defaultValue={current.risk_pct}
        suffix="%"
      />
      <Field
        name="max_positions"
        label="Posições simultâneas"
        hint={`Máximo de operações abertas ao mesmo tempo (${SETTINGS_LIMITS.max_positions}).`}
        defaultValue={current.max_positions}
      />
      <Field
        name="max_position_pct"
        label="Teto por posição"
        hint={`Limite do capital em uma única ação (${SETTINGS_LIMITS.max_position_pct}%).`}
        defaultValue={current.max_position_pct}
        suffix="%"
      />
      <FormError message={state.error} />
      {state.saved && <p className="text-up text-sm">Ajustes salvos.</p>}
      <Button type="submit" disabled={pending} className="self-start">
        {pending ? "Salvando…" : "Salvar ajustes"}
      </Button>
    </form>
  );
}
