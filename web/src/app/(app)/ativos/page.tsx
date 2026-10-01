import { ChartCandlestick } from "lucide-react";

import { EmptyState, PageBody, PageHeader } from "@/components/page";

export default function Page() {
  return (
    <PageBody>
      <PageHeader title="Ativos" description="Gráficos diários com indicadores e os setups marcados." />
      <EmptyState
        icon={ChartCandlestick}
        title="Escolha um ativo para analisar"
        description="Use Ctrl K para buscar um ticker. Os gráficos chegam junto com a carga do histórico."
        phase="Fase 3 · Gráficos"
      />
    </PageBody>
  );
}
