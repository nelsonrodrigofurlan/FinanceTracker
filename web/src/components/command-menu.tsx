"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { mainNav, secondaryNav } from "@/components/nav";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="border-input bg-muted/40 text-muted-foreground hover:bg-muted flex h-8 w-full max-w-sm items-center gap-2 rounded-md border px-2.5 text-sm transition-colors"
      >
        <Search className="size-4" aria-hidden="true" />
        <span className="flex-1 text-left">Buscar ativo ou tela</span>
        <kbd className="bg-background rounded border px-1.5 font-mono text-[11px]">Ctrl K</kbd>
      </button>
      <CommandDialog
        open={open}
        onOpenChange={setOpen}
        title="Busca"
        description="Busque um ativo ou navegue para uma tela"
      >
        <CommandInput placeholder="Digite um ticker (ex.: PETR4) ou uma tela" />
        <CommandList>
          <CommandEmpty>Nada encontrado. A busca de ativos chega com os dados de mercado.</CommandEmpty>
          <CommandGroup heading="Telas">
            {[...mainNav, ...secondaryNav].map((item) => (
              <CommandItem key={item.href} value={item.title} onSelect={() => go(item.href)}>
                <item.icon />
                <span>{item.title}</span>
                <span className="text-muted-foreground ml-auto text-xs">{item.description}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
