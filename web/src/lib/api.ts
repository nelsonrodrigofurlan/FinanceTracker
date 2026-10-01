import "server-only";

import { serverEnv } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

/**
 * Chamada servidor → API. O navegador nunca fala com a API diretamente.
 * Repassa o JWT do Supabase; a API valida assinatura, aal2 e allowlist.
 * TODO(deploy): no Cloud Run, anexar também o ID token da service account (API privada).
 */
export async function apiGet<T>(path: string): Promise<T> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Sessão ausente");

  const response = await fetch(`${serverEnv.apiUrl()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`API ${path} respondeu ${response.status}`);
  return (await response.json()) as T;
}
