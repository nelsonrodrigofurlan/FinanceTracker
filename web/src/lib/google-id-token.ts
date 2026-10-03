import "server-only";

/**
 * ID token do Google para chamar a API PRIVADA no Cloud Run (service-to-service).
 *
 * Obtido do metadata server da própria instância (conta de serviço do ft-web), com o
 * `audience` = URL da API. Enviado no cabeçalho `X-Serverless-Authorization` — documentado
 * pelo Cloud Run para quando o `Authorization` já é usado pela aplicação (aqui: JWT do Supabase).
 * Fora do Google Cloud (desenvolvimento local) API_AUDIENCE fica vazia e nada é enviado.
 */

const METADATA_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
const REFRESH_MARGIN_MS = 5 * 60 * 1000;

let cached: { token: string; expiresAt: number } | null = null;

function expiryOf(token: string): number {
  try {
    const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString("utf8"));
    return typeof payload.exp === "number" ? payload.exp * 1000 : Date.now();
  } catch {
    return Date.now();
  }
}

export async function serverlessAuthHeader(): Promise<Record<string, string>> {
  const audience = process.env.API_AUDIENCE;
  if (!audience) return {};

  if (!cached || cached.expiresAt - REFRESH_MARGIN_MS < Date.now()) {
    const url = `${METADATA_URL}?audience=${encodeURIComponent(audience)}`;
    const response = await fetch(url, {
      headers: { "Metadata-Flavor": "Google" },
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Metadata server respondeu ${response.status}`);
    const token = (await response.text()).trim();
    cached = { token, expiresAt: expiryOf(token) };
  }
  return { "X-Serverless-Authorization": `Bearer ${cached.token}` };
}
