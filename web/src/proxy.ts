import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { sessionCookieOptions } from "@/lib/supabase/cookie-options";

const PUBLIC_PATHS = ["/login"];
const MFA_PATH = "/mfa";

function buildCsp(nonce: string): string {
  const isDev = process.env.NODE_ENV === "development";
  return `
    default-src 'self';
    script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""};
    style-src 'self' 'nonce-${nonce}';
    img-src 'self' blob: data:;
    font-src 'self';
    connect-src 'self';
    object-src 'none';
    base-uri 'self';
    form-action 'self';
    frame-ancestors 'none';
    ${isDev ? "" : "upgrade-insecure-requests;"}
  `
    .replace(/\s{2,}/g, " ")
    .trim();
}

export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = buildCsp(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  let response = NextResponse.next({ request: { headers: requestHeaders } });
  let noStoreHeaders: Record<string, string> = {};

  const supabase = createServerClient(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_PUBLISHABLE_KEY!,
    {
      cookieOptions: sessionCookieOptions,
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request: { headers: requestHeaders } });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, { ...options, ...sessionCookieOptions }),
          );
          // Respostas que gravam cookie de sessão não podem ser cacheadas.
          noStoreHeaders = headers ?? {};
        },
      },
    },
  );

  // getClaims() valida a assinatura do JWT e renova a sessão quando necessário.
  const { data } = await supabase.auth.getClaims();
  const claims = data?.claims;
  const aal = typeof claims?.aal === "string" ? claims.aal : null;
  const path = request.nextUrl.pathname;

  const redirectTo = (target: string) => {
    const redirect = NextResponse.redirect(new URL(target, request.url));
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    return redirect;
  };

  let result: NextResponse = response;
  if (!claims) {
    if (!PUBLIC_PATHS.includes(path)) result = redirectTo("/login");
  } else if (aal !== "aal2") {
    // Logado só com senha: obrigatório passar pelo 2FA.
    if (path !== MFA_PATH) result = redirectTo(MFA_PATH);
  } else if (PUBLIC_PATHS.includes(path) || path === MFA_PATH) {
    result = redirectTo("/");
  }

  result.headers.set("Content-Security-Policy", csp);
  Object.entries(noStoreHeaders).forEach(([key, value]) => result.headers.set(key, value));
  return result;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico|robots.txt).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
