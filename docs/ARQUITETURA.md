# FinanceTracker — Arquitetura

> Status: **rascunho para revisão** · Versão 0.1 · 2026-10-01
> Itens marcados com **[VERIFICAR]** são premissas ainda não confirmadas. Nada marcado assim deve ser implementado antes da confirmação.

## 1. Visão geral

```
GitHub nelsonrodrigofurlan/FinanceTracker
  main ───────► Cloud Build (triggers) ──► Artifact Registry ──► Cloud Run  [PRODUÇÃO]
  developer ──► Cloud Build (triggers) ──► Artifact Registry ──► Cloud Run  [TESTE]

Cloud Run (por ambiente)
  ft-web        Next.js (standalone)       UI, login, gráficos
  ft-api        FastAPI (Python 3.12)      backtest, sinais, cálculo de posição, IA
  ft-pipeline   Cloud Run Job              coleta diária + scanner + alertas
                (mesma imagem da API, outro entrypoint)

Cloud Scheduler ──(dias úteis, pós-fechamento)──► ft-pipeline

Supabase (um projeto por ambiente)
  Auth (MFA TOTP, signup desligado) · Postgres · RLS

Secret Manager: chaves Supabase (service role), brapi, Anthropic, Telegram
```

## 2. Ambientes

| | Produção | Teste |
|---|---|---|
| Branch | `main` | `developer` |
| Projeto GCP | `finance-tracker` (novo) **[VERIFICAR nome/ID]** | mesmo projeto |
| Região Cloud Run | `southamerica-east1` | `southamerica-east1` |
| Serviços | `ft-web`, `ft-api`, job `ft-pipeline` | `ft-web-staging`, `ft-api-staging`, job `ft-pipeline-staging` |
| Supabase | projeto prod (`sa-east-1`) | projeto test (`sa-east-1`) |
| Chaves no `.env` local | **nunca** | sim |

Fluxo de trabalho: o agente trabalha na `developer`; promoção para `main` via PR revisado pelo usuário.

## 3. Repositório (monorepo)

```
FinanceTracker/
├─ web/                 Next.js + TypeScript + Tailwind + Lightweight Charts
├─ api/                 FastAPI + pandas + engine de setups/backtest
│  ├─ src/ft/
│  │  ├─ data/          DataProvider (yfinance, brapi), ajuste de proventos
│  │  ├─ universe/      seleção de ativos líquidos
│  │  ├─ indicators/    médias, IFR, ATR, Donchian (implementação própria + testes)
│  │  ├─ setups/        um módulo por setup, interface comum
│  │  ├─ backtest/      engine de simulação, custos, métricas
│  │  ├─ signals/       scanner e cálculo de posição
│  │  ├─ ai/            prompt + chamada Claude
│  │  ├─ alerts/        Telegram
│  │  └─ pipeline.py    entrypoint do Job
│  └─ tests/
├─ supabase/migrations/ SQL versionado (Supabase CLI)
├─ infra/               cloudbuild-web.yaml, cloudbuild-api.yaml, scripts gcloud
└─ docs/
```

Build: padrão do projeto `poc-app-cursor-1` (docker build → Artifact Registry → `gcloud run`), um trigger por serviço × branch com filtro de caminho (`web/**`, `api/**`).

## 4. Segurança

- **Auth:** Supabase Auth, e-mail + senha + **MFA TOTP obrigatório**; signup público desligado; usuário criado manualmente no painel.
- **Sessão no web:** toda a autenticação roda no servidor (Server Functions + `src/proxy.ts`); o navegador não recebe chave do Supabase; cookie de sessão `httpOnly`, `SameSite=Lax`, `Secure` em produção, 7 dias. O proxy valida o JWT (`getClaims`) e exige `aal2` em todas as rotas, exceto `/login` e `/mfa`; o layout da área logada repete a checagem (defesa em profundidade).
- **CSP com nonce** por requisição (`script-src 'nonce-…' 'strict-dynamic'`), o que torna todas as páginas dinâmicas.
- **API:** valida JWT ES256 via JWKS, `iss`/`aud`/`exp`, `aal2` e allowlist `ALLOWED_USER_IDS` (vazia = bloqueia todos). Erros sempre genéricos (401 "Não autorizado").
- **API privada:** `ft-api` no Cloud Run **sem acesso público** (`--no-allow-unauthenticated`); só a service account do `ft-web` tem `roles/run.invoker`. O navegador nunca fala com a API diretamente.
- **Web → API (defesa em profundidade):** o servidor Next.js chama a API com ID token do Google (IAM) **e** repassa o JWT do Supabase; a API valida assinatura/expiração e confere se o `sub` é o usuário autorizado (allowlist por env var).
- **RLS** em todas as tabelas com dados do usuário (`user_id = auth.uid()`). Tabelas de mercado (candles, ativos) são somente leitura para `authenticated`; escrita apenas via service role (pipeline).
- **Segredos:** Secret Manager montado como env var no Cloud Run; `.env` local só com o projeto de teste.
- **Pipeline:** Cloud Run Job sem endpoint público; disparado pelo Scheduler com service account dedicada.
- Headers de segurança (CSP, HSTS) no Next.js; rate limit simples na API.

## 5. Dados de mercado

### 5.1 Fontes
| Fonte | Uso | Observações |
|---|---|---|
| Yahoo Finance (`yfinance`) | Histórico longo para backtest | Gratuito, não oficial, pode quebrar |
| brapi.dev | Atualização diária | Plano gratuito no início; limites **[VERIFICAR na documentação atual]** |

Interface `DataProvider` com as duas implementações; fallback automático e log de divergências entre fontes.

### 5.2 Regras
- Candles **diários** (V1).
- Guardar preço bruto **e** ajustado (proventos/desdobramentos). Backtest usa ajustado; sinais e ordens usam bruto.
- Validação de qualidade: candles faltantes, OHLC inconsistente (high < low), saltos > X% sem evento corporativo → marcar e alertar.

### 5.3 Universo de ativos
- Critério: volume financeiro médio de 21 pregões ≥ **R$ 30 mi** (parâmetro configurável). É o volume negociado **pelo mercado inteiro** no papel por dia — filtro de liquidez, sem relação com o capital do usuário.
- Recalculado mensalmente; snapshot salvo (`universe_snapshots`) para reduzir viés de sobrevivência em backtests futuros.
- Referência de mercado: BOVA11 (filtro de regime) e SMAL11.
- Excluídos na V1: FIIs, BDRs, units ilíquidas.

## 6. Setups iniciais (especificação formal)

Convenções: `C/H/L/O` = fechamento/máxima/mínima/abertura; `[0]` = candle atual, `[1]` = anterior.
Todos **long-only**. Os parâmetros entre `{}` são **hipóteses iniciais** a serem testadas no laboratório, não valores definitivos.
Entrada "stop de compra" = ordem de compra 1 tick acima do nível indicado, válida por `{validade}` pregões.

### S1 — IFR2 (reversão à média, Larry Connors)
- Filtro: `C > MMA({200})`.
- Sinal: `IFR(2) < {10}` no fechamento.
- Entrada: no fechamento do candle de sinal **ou** abertura seguinte (testar as duas).
- Saída: `C > máxima dos {2} últimos candles` **ou** `C > MMA({5})` (variantes).
- Stop de tempo: `{7}` pregões. Stop de preço: opcional (testar com e sem).
- Observação: na versão original de Connors não há stop de preço; vamos medir o impacto.

### S2 — 9.1 (Larry Williams)
- Sinal: `MME(9)` vira para cima: `MME9[0] > MME9[1]` e `MME9[1] <= MME9[2]`.
- Entrada: stop de compra acima da máxima do candle de sinal; se não executar e a média continuar subindo, o nível é ajustado para a máxima do novo candle.
- Stop: mínima do candle de sinal.
- Saída: quando a `MME(9)` virar para baixo, sair na perda da mínima do candle que virou.

### S3 — Pullback na média
- Filtro: `C > MMA({200})` e `MME({21})` inclinada para cima (`MME21[0] > MME21[{5}]`).
- Sinal: `L[0] <= MME21[0] × (1 + {0,5%})` e `C[0] > MME21[0]`.
- Entrada: stop de compra acima de `H[0]`.
- Stop: `L[0]` (ou `entrada − {2}×ATR(14)`, testar).
- Saída: alvo `{2}R` **ou** trailing pela mínima dos últimos `{3}` candles (testar).

### S4 — Rompimento Donchian
- Sinal: `C[0] > máxima de H[1..{20}]` e `Volume[0] > {1,5} × média volume({20})`.
- Entrada: abertura seguinte.
- Stop inicial: `entrada − {2}×ATR(20)`.
- Saída: `C < mínima de L[1..{10}]` (trailing).

### S5 — 123 de compra (Stormer)
- Filtro: `C > MMA({200})` **[VERIFICAR se aplicamos filtro de tendência]**.
- Sinal: candle `[1]` com mínima menor que as mínimas de `[2]` e `[0]`.
- Entrada: stop de compra acima de `H[0]`.
- Stop: `L[1]`.
- Saída: alvo `{2}R` ou trailing (testar).

### Filtro de regime (opcional, todos os setups)
Só operar compra se `BOVA11 > MMA({200})`. Medido com e sem.

## 7. Laboratório de backtest

### 7.1 Simulação
- Execução candle a candle, sem olhar o futuro (*no look-ahead*): sinal no candle `t` só executa a partir de `t` (fechamento) ou `t+1`.
- **Gap contra o stop:** se a abertura já estiver abaixo do stop, a saída é na abertura (não no preço do stop).
- Se stop e alvo forem tocados no mesmo candle, assume-se o **stop** (premissa conservadora).
- Custos configuráveis: corretagem (Clear: zero **[VERIFICAR condições atuais]**), emolumentos/taxas B3 **[VERIFICAR valores atuais]**, slippage `{0,1%}` por lado.
- IR: calculado à parte, no relatório mensal (swing trade: 15% sobre lucro líquido; isenção para vendas de ações à vista até R$ 20 mil/mês) **[VERIFICAR regras vigentes com contador]**.

### 7.2 Métricas
Nº de trades · taxa de acerto · payoff médio · **expectativa em R** · profit factor · drawdown máximo · retorno anualizado · Sharpe · tempo médio em posição · exposição · maior sequência de perdas.

### 7.3 Validação (anti-overfitting)
- Divisão **dentro da amostra** (otimização) / **fora da amostra** (validação), ex.: 70/30 temporal; evoluir para *walk-forward*.
- Critérios mínimos de aprovação (iniciais, ajustáveis): ≥ `{30}` trades fora da amostra, expectativa > 0 após custos, profit factor > `{1,3}`, resultado fora da amostra sem degradação grave.
- Grade de parâmetros pequena; preferir parâmetros "em platô" a picos isolados.

## 8. Modelo de dados (Postgres / Supabase)

```
assets               id, ticker, name, type(stock|etf), sector, active, created_at
candles_daily        asset_id, date, open, high, low, close, adj_close, volume, fin_volume, source
                     PK(asset_id, date)
corporate_events     asset_id, date, type(dividend|split|...), value
universe_snapshots   id, ref_month, criteria jsonb, asset_ids int[]
setups               id, code(S1..S5), name, version, default_params jsonb, active
backtest_runs        id, setup_id, params jsonb, universe_snapshot_id, period_start, period_end,
                     split jsonb, costs jsonb, metrics jsonb, approved bool, created_at
backtest_trades      run_id, asset_id, entry_date, entry_price, exit_date, exit_price,
                     stop, target, r_multiple, exit_reason, sample(in|out)
approved_strategies  id, setup_id, asset_id (nullable = todos), params jsonb, backtest_run_id, active
signals              id, strategy_id, asset_id, date, entry, stop, target, rr, qty_suggested,
                     status(new|triggered|expired|ignored), ai_analysis_id
ai_analyses          id, signal_id, model, prompt_hash, content, created_at
trades               id, user_id, signal_id (nullable), asset_id, side, qty, entry_date, entry_price,
                     exit_date, exit_price, stop, fees, notes, emotion, created_at
settings             user_id, capital, risk_pct, max_position_pct, max_open_positions, ...
pipeline_runs        id, started_at, finished_at, status, stats jsonb, error
alerts_log           id, signal_id, channel, sent_at, status
```

## 9. Camada de IA

- Entrada: JSON com dados calculados (tendência por timeframe, setup, níveis, estatísticas do backtest, proximidade de balanço).
- Saída: texto estruturado (contexto, por que o setup, o que invalida, riscos).
- Proibido à IA: criar/alterar níveis de entrada, stop ou alvo.
- Modelo configurável por env var; gerado sob demanda ou só para sinais novos (controle de custo).
- Provedor: **OpenRouter** (mesmo padrão do projeto `palpitaria`: SDK compatível OpenAI + `base_url`), créditos pré-pagos como teto de gasto. Modelo: apelido `~anthropic/claude-sonnet-latest` (decisão do usuário, 2026-10-01; em 2026-10-01 custava US$ 2/M entrada e US$ 10/M saída). Como o apelido pode mudar de modelo/preço sem aviso, registrar em `ai_analyses` o modelo efetivamente usado e o custo de cada chamada, conforme retornado pela resposta do OpenRouter **[VERIFICAR campos da resposta na implementação]**.
- Cliente encapsulado em `ai/` para permitir trocar de provedor sem mexer no resto.

## 10. Roadmap da V1

| Fase | Entregas | Pronto quando |
|---|---|---|
| F0 Fundação | Monorepo, Dockerfiles, cloudbuild, triggers, Supabase migrations base | Deploy "hello" em prod e test |
| F1 Acesso | Login + MFA, RLS, API validando JWT | Só o usuário acessa, com 2FA |
| F2 Dados | DataProviders, carga histórica, universo, job diário | Histórico carregado e atualização diária automática |
| F3 Gráficos | Tela de ativo com candles e indicadores | Gráfico navegável por ativo |
| F4 Laboratório | Engine de backtest, S1–S5, métricas, tela de resultados | Relatório comparativo dos 5 setups |
| F5 Sinais | Scanner, painel do sinal, calculadora de posição, IA | Sinais diários com racional |
| F6 Diário + Alertas | Registro de trades, Telegram | Alerta chega no celular; diário compara previsto × real |

## 11. Questões em aberto

1. ID/nome do novo projeto GCP (criado pelo usuário no Console; `gcloud` não está instalado nesta máquina).
2. Horário do job/alerta (proposta: 19h00 BRT, dias úteis).
3. Calendário de feriados da B3: fonte a definir.

Decididas em 2026-10-01: URL padrão `*.run.app`; API privada; IA via OpenRouter; histórico de 10–15 anos; universo ≥ R$ 30 mi/dia.
