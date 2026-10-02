import { PageBody, PageHeader } from "@/components/page";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet } from "@/lib/api";
import { settingsComplete, type UserSettings } from "@/lib/settings";

import { SettingsForm } from "./settings-form";

const EMPTY: UserSettings = {
  sim_capital: null,
  risk_pct: null,
  max_positions: null,
  max_position_pct: null,
};

export default async function AjustesPage() {
  const current = await apiGet<UserSettings>("/settings").catch(() => EMPTY);

  return (
    <PageBody>
      <PageHeader title="Ajustes" description="Parâmetros do modo simulado e da calculadora de posição." />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Modo simulado e risco</CardTitle>
          <CardDescription>
            {settingsComplete(current)
              ? "Esses valores definem a quantidade sugerida em cada sinal e a carteira simulada."
              : "Enquanto estes campos estiverem vazios, os sinais aparecem sem quantidade calculada."}{" "}
            A escolha dos valores é sempre sua; o app não sugere percentuais.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SettingsForm current={current} />
        </CardContent>
      </Card>
    </PageBody>
  );
}
