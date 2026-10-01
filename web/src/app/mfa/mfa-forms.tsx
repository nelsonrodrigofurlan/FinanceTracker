"use client";

import { useActionState, useState, useTransition } from "react";

import { enrollTotp, verifyTotp, type EnrollState, type VerifyState } from "./actions";

const inputClass =
  "rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-center font-mono tracking-[0.4em] dark:border-zinc-700";
const buttonClass =
  "rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900";

function VerifyForm({ factorId }: { factorId: string }) {
  const [state, formAction, pending] = useActionState<VerifyState, FormData>(verifyTotp, {
    error: null,
  });

  return (
    <form action={formAction} className="flex w-full flex-col gap-4">
      <input type="hidden" name="factorId" value={factorId} />
      <label className="flex flex-col gap-1 text-sm">
        Código do aplicativo autenticador
        <input
          name="code"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d{6}"
          maxLength={6}
          required
          autoFocus
          className={inputClass}
        />
      </label>
      {state.error && (
        <p role="alert" className="text-sm text-red-600">
          {state.error}
        </p>
      )}
      <button type="submit" disabled={pending} className={buttonClass}>
        {pending ? "Verificando..." : "Verificar"}
      </button>
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
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          A verificação em duas etapas é obrigatória. Tenha em mãos um aplicativo autenticador
          (Google Authenticator, Microsoft Authenticator, 1Password, Authy etc.).
        </p>
        {enrollment?.error && (
          <p role="alert" className="text-sm text-red-600">
            {enrollment.error}
          </p>
        )}
        <button
          type="button"
          disabled={pending}
          className={buttonClass}
          onClick={() => startTransition(async () => setEnrollment(await enrollTotp()))}
        >
          {pending ? "Gerando..." : "Configurar 2FA"}
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Escaneie o QR code no aplicativo autenticador e digite o código gerado.
      </p>
      {/* eslint-disable-next-line @next/next/no-img-element -- QR em data URI gerado pelo Supabase */}
      <img
        src={enrollment.qrCode ?? ""}
        alt="QR code para o aplicativo autenticador"
        className="mx-auto h-48 w-48 rounded-md bg-white p-2"
      />
      <details className="text-xs text-zinc-500">
        <summary className="cursor-pointer">Não consegue escanear? Digite a chave manualmente</summary>
        <code className="mt-2 block break-all font-mono">{enrollment.secret}</code>
      </details>
      <VerifyForm factorId={enrollment.factorId} />
    </div>
  );
}
