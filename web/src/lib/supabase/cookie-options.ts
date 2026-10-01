import type { CookieOptions } from "@supabase/ssr";

// Toda a autenticação roda no servidor, então o cookie de sessão pode ser httpOnly:
// JavaScript no navegador não consegue lê-lo (mitiga roubo de sessão via XSS).
export const sessionCookieOptions: CookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax",
  path: "/",
  maxAge: 7 * 24 * 60 * 60, // 7 dias
};
