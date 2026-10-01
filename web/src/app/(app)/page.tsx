import { apiGet } from "@/lib/api";

type Me = { user_id: string; aal: string };

async function checkApi(): Promise<string> {
  try {
    const me = await apiGet<Me>("/me");
    return `API conectada (sessão ${me.aal}).`;
  } catch {
    return "API indisponível.";
  }
}

export default async function Home() {
  const apiStatus = await checkApi();

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-2 p-8">
      <h1 className="text-2xl font-semibold tracking-tight">Bem-vindo</h1>
      <p className="text-sm text-zinc-500">{apiStatus}</p>
    </main>
  );
}
