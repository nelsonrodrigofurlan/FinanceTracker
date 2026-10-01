import { Radar } from "lucide-react";

import { EmptyState, PageBody, PageHeader } from "@/components/page";

export default function Page() {
  return (
    <PageBody>
      <PageHeader title="Scanner" description="Onde existe setup agora, entre os ativos líquidos da B3." />
      <EmptyState
        icon={Radar}
        title="Nenhum setup aprovado ainda"
        description="O scanner só usa setups que provaram vantagem no laboratório. Os sinais aparecem aqui, ordenados pela força da evidência."
        phase="Fase 5 · Sinais"
      />
    </PageBody>
  );
}
