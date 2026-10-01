"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LogoMark } from "@/components/logo";
import { mainNav, secondaryNav, type NavItem } from "@/components/nav";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function NavMenu({ items, pathname }: { items: NavItem[]; pathname: string }) {
  return (
    <SidebarMenu>
      {items.map((item) => (
        <SidebarMenuItem key={item.href}>
          <SidebarMenuButton
            isActive={isActive(pathname, item.href)}
            tooltip={item.title}
            render={<Link href={item.href} />}
          >
            <item.icon />
            <span>{item.title}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  );
}

export function AppSidebar({ apiOnline }: { apiOnline: boolean }) {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <LogoMark />
              <span className="font-semibold tracking-tight">FinanceTracker</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <NavMenu items={mainNav} pathname={pathname} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <NavMenu items={secondaryNav} pathname={pathname} />
        <div
          className="text-muted-foreground flex items-center gap-2 px-2 py-1 text-xs group-data-[collapsible=icon]:justify-center"
          title={apiOnline ? "API conectada" : "API indisponível"}
        >
          <span
            className={`size-2 shrink-0 rounded-full ${apiOnline ? "bg-up" : "bg-down"}`}
            aria-hidden="true"
          />
          <span className="group-data-[collapsible=icon]:hidden">
            {apiOnline ? "API conectada" : "API indisponível"}
          </span>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
