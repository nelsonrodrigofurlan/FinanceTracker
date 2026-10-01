// Allowlist de usuários (fail-closed): se a variável estiver vazia, ninguém entra.
// Defesa em profundidade: vale mesmo que o cadastro público do Supabase esteja ligado por engano.
export function isAllowedUser(userId: string | undefined | null): boolean {
  if (!userId) return false;
  const allowed = (process.env.ALLOWED_USER_IDS ?? "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
  return allowed.includes(userId);
}
