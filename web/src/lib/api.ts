import "server-only";

import { serverEnv } from "@/lib/env";
import { serverlessAuthHeader } from "@/lib/google-id-token";
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
 * No Cloud Run, anexa também o ID token da conta de serviço (API privada, ver google-id-token).
 */
export async function apiGet<T>(path: string): Promise<T> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, path);

  const response = await fetch(`${serverEnv.apiUrl()}${path}`, {
    headers: { Authorization: `Bearer ${token}`, ...(await serverlessAuthHeader()) },
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status, path);
  return (await response.json()) as T;
}

export async function apiSend<T>(
  path: string,
  method: "PUT" | "POST" | "DELETE",
  body?: unknown,
): Promise<T> {
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new ApiError(401, path);

  const response = await fetch(`${serverEnv.apiUrl()}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(await serverlessAuthHeader()),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status, path);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
