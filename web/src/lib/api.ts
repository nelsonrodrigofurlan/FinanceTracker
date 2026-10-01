import "server-only";

import { serverEnv } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    path: string,
  ) {
    super(`API ${path} respondeu ${status}`);
  }
}

/**
 * Chamada servidor → API. O navegador nunca fala com a API diretamente.
 * Repassa o JWT do Supabase; a API valida assinatura, aal2 e allowlist.
 * TODO(deploy): no Cloud Run, anexar também o ID token da service account (API privada).
 */
export async function apiGet<T>(path: string): Promise<T> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, path);

  const response = await fetch(`${serverEnv.apiUrl()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status, path);
  return (await response.json()) as T;
}
