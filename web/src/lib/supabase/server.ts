import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

import { serverEnv } from "@/lib/env";
import { sessionCookieOptions } from "@/lib/supabase/cookie-options";

/** Cliente Supabase para Server Components e Server Functions. Um por requisição. */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(serverEnv.supabaseUrl(), serverEnv.supabasePublishableKey(), {
    cookieOptions: sessionCookieOptions,
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, { ...options, ...sessionCookieOptions }),
          );
        } catch {
          // Server Components não podem gravar cookies; o proxy renova a sessão.
        }
      },
    },
  });
}

export type Session = {
  userId: string;
  email: string | null;
  aal: string;
};

/** Lê a sessão validando a assinatura do JWT (via JWKS), não apenas o cookie. */
export async function getVerifiedSession(): Promise<Session | null> {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) return null;

  const claims = data.claims;
  return {
    userId: claims.sub,
    email: typeof claims.email === "string" ? claims.email : null,
    aal: typeof claims.aal === "string" ? claims.aal : "aal1",
  };
}
