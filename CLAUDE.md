# Regras do projeto FinanceTracker

## Inegociáveis
1. **Segurança em primeiro lugar.** Diante de duas opções, escolher a mais segura. Nunca expor a API publicamente, nunca versionar segredos, nunca colocar chaves de produção em `.env` local.
2. **Não alucinar.** Toda premissa não confirmada (limites de API, custos da B3, regras de IR, flags de CLI, versões) é verificada na fonte ou marcada como **[VERIFICAR]** em `docs/` e perguntada ao usuário antes de implementar.
3. **Perguntar quando houver ambiguidade.** Não decidir sozinho regras de negócio, parâmetros de risco ou de setups.
4. **App analisa, usuário opera.** Nada de envio de ordens. A IA explica sinais; nunca cria ou altera entrada/stop/alvo.

## Fluxo
- Trabalho sempre na branch `developer` (deploy em staging). `main` só via Pull Request revisado pelo usuário.
- Commits pequenos e descritivos, em português.
- Antes de commitar: `uv run ruff check . && uv run pytest` em `api/`; `npm run lint && npm run build` em `web/`.

## Referências
- Visão: `docs/VISAO.md` · Arquitetura: `docs/ARQUITETURA.md` · Setup de infra: `infra/SETUP.md`
- `web/` usa Next.js 16: consultar `web/node_modules/next/dist/docs/` antes de usar APIs do Next (ver `web/AGENTS.md`).
