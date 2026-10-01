import { FlaskConical } from "lucide-react";

import { EmptyState, PageBody, PageHeader } from "@/components/page";

export default function Page() {
  return (
    <PageBody>
      <PageHeader title="Laboratório" description="Quais setups têm vantagem comprovada, em quais ativos." />
      <EmptyState
        icon={FlaskConical}
        title="Teste o primeiro setup"
        description="Cada setup é testado em anos de histórico, com custos, gaps e validação fora da amostra. Só os aprovados viram sinais."
        phase="Fase 4 · Laboratório"
      />
    </PageBody>
  );
}
