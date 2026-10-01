# FinanceTracker

Aplicação pessoal de análise técnica para **swing trade na B3**: laboratório de backtest, scanner de setups aprovados, painel de sinais com gestão de risco e diário de trades. A execução das ordens é manual.

> Ferramenta de análise. Não constitui recomendação de investimento.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `web/` | Frontend Next.js (UI, login, gráficos) |
| `api/` | FastAPI + engine de setups/backtest + Job diário (`ft.pipeline`) |
| `infra/` | Cloud Build e guia de setup ([infra/SETUP.md](infra/SETUP.md)) |
| `docs/` | [Visão](docs/VISAO.md) e [Arquitetura](docs/ARQUITETURA.md) |

## Fluxo de branches

- `developer` → deploy automático em **staging**
- `main` → deploy automático em **produção**, apenas via Pull Request

## Desenvolvimento local

```bash
cp .env.example .env   # preencher com o projeto Supabase de TESTE
```

API:
```bash
cd api
uv sync
uv run pytest
uv run uvicorn ft.main:app --reload --port 8000
```

Banco e dados (sempre no projeto Supabase do `.env`, que é o de TESTE):
```bash
cd api
uv run python -m ft.db.migrate --status
uv run python -m ft.db.migrate
uv run python -m ft.pipeline
```

Web:
```bash
cd web
npm ci
npm run dev
```
