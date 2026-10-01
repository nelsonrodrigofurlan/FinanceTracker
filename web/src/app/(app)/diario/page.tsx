import { NotebookPen } from "lucide-react";

import { EmptyState, PageBody, PageHeader } from "@/components/page";

export default function Page() {
  return (
    <PageBody>
      <PageHeader title="Diário" description="O que você operou, por quê, e como foi comparado ao plano." />
      <EmptyState
        icon={NotebookPen}
        title="Registre seu primeiro trade"
        description="Compare o resultado real com o que o setup previa e descubra se o ajuste está no setup ou na execução."
        phase="Fase 6 · Diário"
      />
    </PageBody>
  );
}
