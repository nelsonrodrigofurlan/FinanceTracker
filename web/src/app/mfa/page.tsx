import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

import { signOut } from "./actions";
import { MfaChallenge, MfaEnroll } from "./mfa-forms";

export default async function MfaPage() {
  const supabase = await createClient();
  const { data: claimsData } = await supabase.auth.getClaims();
  if (!claimsData?.claims) redirect("/login");

  const { data: factors } = await supabase.auth.mfa.listFactors();
  const verifiedTotp = factors?.totp[0];

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Verificação em duas etapas</h1>
      {verifiedTotp ? <MfaChallenge factorId={verifiedTotp.id} /> : <MfaEnroll />}
      <form action={signOut}>
        <button type="submit" className="text-xs text-zinc-500 underline">
          Sair
        </button>
      </form>
    </main>
  );
}
