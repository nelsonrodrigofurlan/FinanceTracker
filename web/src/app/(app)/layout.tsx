import { redirect } from "next/navigation";

import { signOut } from "@/app/mfa/actions";
import { getVerifiedSession } from "@/lib/supabase/server";

// Defesa em profundidade: além do proxy, toda página da área logada exige sessão aal2.
export default async function AppLayout({ children }: LayoutProps<"/">) {
  const session = await getVerifiedSession();
  if (!session) redirect("/login");
  if (session.aal !== "aal2") redirect("/mfa");

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
        <span className="font-semibold tracking-tight">FinanceTracker</span>
        <div className="flex items-center gap-4 text-sm text-zinc-500">
          <span>{session.email}</span>
          <form action={signOut}>
            <button type="submit" className="underline">
              Sair
            </button>
          </form>
        </div>
      </header>
      {children}
    </div>
  );
}
