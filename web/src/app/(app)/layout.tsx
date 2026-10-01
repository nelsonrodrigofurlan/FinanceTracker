import { LogOut } from "lucide-react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { signOut } from "@/app/mfa/actions";
import { AppSidebar } from "@/components/app-sidebar";
import { CommandMenu } from "@/components/command-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { isAllowedUser } from "@/lib/allowlist";
import { apiGet } from "@/lib/api";
import { getVerifiedSession } from "@/lib/supabase/server";

async function isApiOnline(): Promise<boolean> {
  try {
    await apiGet("/me");
    return true;
  } catch {
    return false;
  }
}

// Defesa em profundidade: além do proxy, toda página da área logada exige sessão aal2.
export default async function AppLayout({ children }: LayoutProps<"/">) {
  const session = await getVerifiedSession();
  if (!session || !isAllowedUser(session.userId)) redirect("/login");
  if (session.aal !== "aal2") redirect("/mfa");

  const [apiOnline, cookieStore] = await Promise.all([isApiOnline(), cookies()]);
  const sidebarOpen = cookieStore.get("sidebar_state")?.value !== "false";

  return (
    <SidebarProvider defaultOpen={sidebarOpen}>
      <AppSidebar apiOnline={apiOnline} />
      <SidebarInset>
        <header className="bg-background/80 sticky top-0 z-10 flex h-14 items-center gap-3 border-b px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="h-5" />
          <CommandMenu />
          <div className="ml-auto flex items-center gap-1">
            <span className="text-muted-foreground mr-2 hidden text-sm md:inline">
              {session.email}
            </span>
            <ThemeToggle />
            <form action={signOut}>
              <Button variant="ghost" size="icon" type="submit" aria-label="Sair">
                <LogOut className="size-4" />
              </Button>
            </form>
          </div>
        </header>
        {children}
      </SidebarInset>
    </SidebarProvider>
  );
}
