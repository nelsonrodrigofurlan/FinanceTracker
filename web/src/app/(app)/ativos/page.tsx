import { ChartCandlestick } from "lucide-react";

import { AssetsTable } from "@/components/assets-table";
import { EmptyState, PageBody, PageHeader } from "@/components/page";
import { apiGet } from "@/lib/api";
import type { AssetSummary } from "@/lib/market";

export default async function AtivosPage() {
  let assets: AssetSummary[] | null = null;
  try {
    assets = await apiGet<AssetSummary[]>("/market/assets");
  } catch {
    assets = null;
  }

  return (
    <PageBody>
      <PageHeader
        title="Ativos"
        description="Universo líquido acompanhado. Clique em um ativo para ver o gráfico."
      />
      {assets && assets.length > 0 ? (
        <AssetsTable assets={assets} />
      ) : (
        <EmptyState
          icon={ChartCandlestick}
          title={assets ? "Nenhum ativo carregado" : "Não foi possível carregar os ativos"}
          description={
            assets
              ? "Rode a coleta de dados para montar o universo."
              : "Verifique se a API está no ar."
          }
        />
      )}
    </PageBody>
  );
}
