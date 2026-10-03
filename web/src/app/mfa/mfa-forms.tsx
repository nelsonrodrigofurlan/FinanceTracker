"use client";

import { useActionState, useState, useTransition } from "react";

import { FormError } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { enrollTotp, verifyTotp, type EnrollState, type VerifyState } from "./actions";

function VerifyForm({ factorId }: { factorId: string }) {
  const [state, formAction, pending] = useActionState<VerifyState, FormData>(verifyTotp, {
    error: null,
  });

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <input type="hidden" name="factorId" value={factorId} />
      <label className="flex flex-col gap-1.5 text-sm font-medium">
        Código
        <Input
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          autoFocus
          className="num h-11 text-center font-mono text-lg tracking-[0.5em]"
        />
      </label>
      <FormError message={state.error} />
      <Button type="submit" disabled={pending} className="w-full">
        {pending ? "Verificando…" : "Verificar"}
      </Button>
    </form>
  );
}

export function MfaChallenge({ factorId }: { factorId: string }) {
  return <VerifyForm factorId={factorId} />;
}

export function MfaEnroll() {
  const [enrollment, setEnrollment] = useState<EnrollState | null>(null);
  const [pending, startTransition] = useTransition();

  if (!enrollment?.factorId) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          Tenha em mãos um aplicativo autenticador (Google Authenticator, Microsoft
          Authenticator, 1Password, Authy).
        </p>
        <FormError message={enrollment?.error ?? null} />
        <Button
          type="button"
          disabled={pending}
          className="w-full"
          onClick={() => startTransition(async () => setEnrollment(await enrollTotp()))}
        >
          {pending ? "Gerando…" : "Configurar 2FA"}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Escaneie o QR code no aplicativo e digite o código gerado.
      </p>
      {/* eslint-disable-next-line @next/next/no-img-element -- QR em data URI gerado pelo Supabase */}
      <img
        src={enrollment.qrCode ?? ""}
        alt="QR code para o aplicativo autenticador"
        className="mx-auto size-48 rounded-md bg-white p-2"
      />
      <details className="text-muted-foreground text-xs">
        <summary className="cursor-pointer">Não consegue escanear? Use a chave manual</summary>
        <code className="mt-2 block font-mono break-all">{enrollment.secret}</code>
      </details>
      <VerifyForm factorId={enrollment.factorId} />
    </div>
  );
}
