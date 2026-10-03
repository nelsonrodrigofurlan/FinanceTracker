"use server";

import { redirect } from "next/navigation";

import { isAllowedUser } from "@/lib/allowlist";
import { createClient } from "@/lib/supabase/server";

export type LoginState = { error: string | null };

export async function signIn(_prev: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { error: "Informe e-mail e senha." };
  }

  const supabase = await createClient();
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });

  if (error || !isAllowedUser(data.user?.id)) {
    if (!error) await supabase.auth.signOut();
    // Mensagem genérica: não revelar se o e-mail existe nem se o usuário é autorizado.
    return { error: "Credenciais inválidas." };
  }

  redirect("/mfa");
}
