"use client";

import { Trash2 } from "lucide-react";
import { useActionState, useState, useTransition } from "react";

import { FormError } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EMOTIONS } from "@/lib/journal";

import { closeTrade, createTrade, deleteTrade, type FormState } from "./actions";

const INITIAL: FormState = { error: null, ok: false };

function today() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
    </label>
  );
}

const selectClass =
  "border-input bg-background h-9 rounded-md border px-2 text-sm dark:bg-input/30";

export function NewTradeForm() {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState(createTrade, INITIAL);

  if (!open) {
    return (
      <Button type="button" onClick={() => setOpen(true)} className="self-start">
        Registrar trade
      </Button>
    );
  }

  return (
    <form action={action} className="flex flex-col gap-4 rounded-lg border p-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Field label="Ativo">
          <Input name="ticker" required placeholder="PETR4" className="uppercase" />
        </Field>
        <Field label="Data de entrada">
          <Input name="entry_date" type="date" required defaultValue={today()} max={today()} />
        </Field>
        <Field label="Preço de entrada (R$)">
          <Input name="entry_price" required inputMode="decimal" className="num" />
        </Field>
        <Field label="Quantidade">
          <Input name="quantity" required inputMode="numeric" className="num" />
        </Field>
        <Field label="Stop planejado (R$)">
          <Input name="stop_planned" inputMode="decimal" className="num" />
        </Field>
        <Field label="Alvo planejado (R$)">
          <Input name="target_planned" inputMode="decimal" className="num" />
        </Field>
        <Field label="Custos da entrada (R$)">
          <Input name="entry_fees" inputMode="decimal" className="num" placeholder="0" />
        </Field>
        <Field label="Como você estava?">
          <select name="emotion" className={selectClass} defaultValue="">
            <option value="">—</option>
            {Object.entries(EMOTIONS).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Motivo da operação">
        <textarea
          name="reason"
          maxLength={2000}
          rows={2}
          className="border-input bg-background rounded-md border px-3 py-2 text-sm dark:bg-input/30"
          placeholder="Por que entrei? Qual era o plano?"
        />
      </Field>
      <p className="text-muted-foreground text-xs">
        Sem stop planejado o resultado não é medido em R. Registrar o stop antes de entrar é o
        principal indicador de disciplina.
      </p>
      <FormError message={state.error} />
      {state.ok && <p className="text-up text-sm">Trade registrado.</p>}
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? "Salvando…" : "Salvar"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Fechar
        </Button>
      </div>
    </form>
  );
}

export function CloseTradeForm({ id, entryDate }: { id: number; entryDate: string }) {
  const [open, setOpen] = useState(false);
  const [state, action, pending] = useActionState(closeTrade, INITIAL);

  if (!open) {
    return (
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
        Encerrar
      </Button>
    );
  }
  return (
    <form action={action} className="flex flex-wrap items-end gap-2">
      <input type="hidden" name="id" value={id} />
      <Input
        name="exit_date"
        type="date"
        required
        min={entryDate}
        max={today()}
        defaultValue={today()}
        className="w-36"
        aria-label="Data de saída"
      />
      <Input
        name="exit_price"
        required
        inputMode="decimal"
        placeholder="Preço"
        className="num w-24"
        aria-label="Preço de saída"
      />
      <Input
        name="exit_fees"
        inputMode="decimal"
        placeholder="Custos"
        className="num w-20"
        aria-label="Custos da saída"
      />
      <Button type="submit" size="sm" disabled={pending}>
        {pending ? "…" : "Salvar"}
      </Button>
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
        Cancelar
      </Button>
      <FormError message={state.error} />
    </form>
  );
}

export function DeleteTradeButton({ id, ticker }: { id: number; ticker: string }) {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <Button
        type="button"
        size="icon"
        variant="ghost"
        aria-label={`Excluir trade de ${ticker}`}
        disabled={pending}
        onClick={() => {
          if (!window.confirm(`Excluir definitivamente o registro de ${ticker}?`)) return;
          start(async () => setError((await deleteTrade(id)).error));
        }}
      >
        <Trash2 className="size-4" />
      </Button>
      {error && <span className="text-destructive text-xs">{error}</span>}
    </>
  );
}
