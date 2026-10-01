"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export type EnrollState = {
  error: string | null;
  factorId: string | null;
  qrCode: string | null;
  secret: string | null;
};

export type VerifyState = { error: string | null };

const TOTP_CODE = /^\d{6}$/;

/** Cadastra um novo fator TOTP, descartando cadastros anteriores não concluídos. */
export async function enrollTotp(): Promise<EnrollState> {
  const supabase = await createClient();

  const { data: factors, error: listError } = await supabase.auth.mfa.listFactors();
  if (listError) return { error: "Não foi possível iniciar o 2FA.", factorId: null, qrCode: null, secret: null };

  if (factors.totp.length > 0) {
    return { error: "2FA já configurado. Recarregue a página.", factorId: null, qrCode: null, secret: null };
  }

  for (const factor of factors.all.filter((f) => f.status === "unverified")) {
    await supabase.auth.mfa.unenroll({ factorId: factor.id });
  }

  const { data, error } = await supabase.auth.mfa.enroll({
    factorType: "totp",
    friendlyName: "Autenticador",
    issuer: "FinanceTracker",
  });
  if (error || !data) {
    return { error: "Não foi possível gerar o QR code.", factorId: null, qrCode: null, secret: null };
  }

  return { error: null, factorId: data.id, qrCode: data.totp.qr_code, secret: data.totp.secret };
}

export async function verifyTotp(_prev: VerifyState, formData: FormData): Promise<VerifyState> {
  const factorId = String(formData.get("factorId") ?? "");
  const code = String(formData.get("code") ?? "").trim();

  if (!factorId || !TOTP_CODE.test(code)) {
    return { error: "Informe o código de 6 dígitos." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.mfa.challengeAndVerify({ factorId, code });
  if (error) {
    return { error: "Código inválido ou expirado." };
  }

  redirect("/");
}

export async function signOut(): Promise<void> {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
