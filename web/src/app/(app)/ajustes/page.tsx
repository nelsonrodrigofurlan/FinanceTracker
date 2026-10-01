import { Settings } from "lucide-react";

import { EmptyState, PageBody, PageHeader } from "@/components/page";

export default function Page() {
  return (
    <PageBody>
      <PageHeader title="Ajustes" description="Capital, risco por operação e preferências." />
      <EmptyState
        icon={Settings}
        title="Defina seu capital e risco"
        description="Esses parâmetros alimentam a calculadora de posição. A decisão dos valores é sempre sua."
        phase="Fase 5 · Sinais"
      />
    </PageBody>
  );
}
