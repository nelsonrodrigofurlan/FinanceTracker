# FinanceTracker — Documento de Visão

> Status: **rascunho para revisão** · Versão 0.1 · 2026-10-01

## 1. Propósito

Aplicação web **pessoal** (um único usuário) para análise técnica de ações da B3 com foco em **swing trade**.
O app **analisa e alerta**; a execução das ordens é **manual**, feita pelo usuário na corretora (Clear).

## 2. Princípio central

> **Nenhum setup é sugerido sem ter vantagem estatística comprovada em backtest.**

Fluxo de valor:

1. **Laboratório** testa setups (regras objetivas) em anos de histórico.
2. Só combinações *setup × ativo* aprovadas por critérios mínimos vão para o **scanner**.
3. O scanner gera **sinais** com entrada, stop, alvo e tamanho de posição.
4. A **IA (Claude)** redige o racional do sinal a partir de dados já calculados — ela **não** cria sinais.
5. O **diário** compara o resultado real com o previsto e alimenta o aprendizado.

## 3. Regra financeira do projeto

O custo operacional do app (infra, dados, IA) deve ser coberto pelo resultado das operações.
Consequências práticas:
- Começar com camadas gratuitas (dados, Cloud Run com escala a zero).
- O app exibe o **custo mensal estimado** ao lado do resultado do período.
- Upgrade de plano (ex.: brapi) só com justificativa medida.

## 4. Escopo

### V1 (MVP)
| Módulo | Entrega |
|---|---|
| 0. Acesso | Login Supabase Auth, cadastro desligado, MFA TOTP, RLS |
| 1. Coleta | Job diário pós-fechamento; histórico ajustado por proventos |
| 2. Universo | Lista dinâmica de ativos líquidos, recalculada mensalmente |
| 3. Gráficos | Candles diários + indicadores + marcação de sinais |
| 4. Laboratório | Backtest dos 5 setups iniciais, com métricas e aprovação |
| 5. Painel do sinal | Entrada/stop/alvo, R:R, calculadora de posição, racional da IA |
| 6. Scanner | Sinais do dia dos setups aprovados |
| 7. Diário | Registro de trades reais e comparação com o previsto |
| 8. Alertas | Telegram |

### Fora da V1
- Day trade / intraday (exigiria MT5/Profit em máquina Windows).
- Operações vendidas (aluguel de ações).
- Envio automático de ordens.
- Padrões gráficos "desenhados" (OCO, triângulos etc.).
- FIIs, BDRs, opções.

## 5. Gestão de risco (funcionalidade, não recomendação)

O app oferece ferramentas; **os parâmetros são decisão do usuário**:
- Capital alocado e % de risco por operação configuráveis.
- Tamanho de posição = `floor((capital × risco%) / (entrada − stop))`, limitado por % máximo do capital por posição.
- Exposição total máxima e número máximo de posições simultâneas configuráveis.
- O laboratório mostra o drawdown histórico de cada setup para apoiar essa escolha.

> O app é uma ferramenta de análise. Não constitui recomendação de investimento.

## 6. Critérios de sucesso da V1

1. Login com MFA funcionando em prod e test.
2. Histórico ajustado de ≥ 10 anos (quando disponível) para o universo.
3. Backtest dos 5 setups com relatório de métricas e validação fora da amostra.
4. Job diário gerando sinais e alertando no Telegram sem intervenção manual.
5. Diário registrando trades e comparando com o sinal original.

## 7. Questões em aberto

Ver seção "Questões em aberto" em [ARQUITETURA.md](ARQUITETURA.md#11-questões-em-aberto).
