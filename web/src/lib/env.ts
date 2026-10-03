import "server-only";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Variável de ambiente obrigatória ausente: ${name}`);
  }
  return value;
}

// Somente valores públicos do Supabase: o frontend NUNCA recebe a chave secreta.
export const serverEnv = {
  supabaseUrl: () => required("SUPABASE_URL"),
  supabasePublishableKey: () => required("SUPABASE_PUBLISHABLE_KEY"),
  apiUrl: () => required("API_URL"),
};
