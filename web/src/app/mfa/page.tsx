import { redirect } from "next/navigation";

import { AuthShell } from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
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
    <AuthShell
      title="Verificação em duas etapas"
      description={
        verifiedTotp
          ? "Digite o código de 6 dígitos do seu aplicativo autenticador."
          : "Obrigatória para acessar. Configure uma vez e use em todo login."
      }
      footer={
        <form action={signOut}>
          <Button type="submit" variant="link" size="sm" className="text-muted-foreground">
            Sair
          </Button>
        </form>
      }
    >
      {verifiedTotp ? <MfaChallenge factorId={verifiedTotp.id} /> : <MfaEnroll />}
    </AuthShell>
  );
}
