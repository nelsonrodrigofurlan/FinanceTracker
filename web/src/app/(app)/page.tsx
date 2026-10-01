import { Radar } from "lucide-react";

import { MarketStatusCard } from "@/components/market-status-card";
import { EmptyState, Metric, PageBody, PageHeader } from "@/components/page";

export default function PainelPage() {
  return (
    <PageBody>
      <PageHeader title="Painel" description="Como você está e o que o mercado oferece hoje." />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-5" aria-label="Resumo do mês">
        <Metric label="Resultado do mês" value={null} hint="em R (múltiplos do risco)" />
        <Metric label="Resultado em R$" value={null} hint="após custos e taxas" />
        <Metric label="Custo do app no mês" value={null} hint="infra, dados e IA" />
        <Metric label="Posições abertas" value={null} />
        <Metric label="Risco em aberto" value={null} hint="% do capital" />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <EmptyState
          className="lg:col-span-2"
          icon={Radar}
          title="Sinais de hoje"
          description="Aqui aparecem os sinais dos setups aprovados no laboratório, com entrada, stop, alvo e a evidência histórica de cada um."
          phase="Fase 5 · Sinais"
        />
        <MarketStatusCard />
      </section>
    </PageBody>
  );
}
