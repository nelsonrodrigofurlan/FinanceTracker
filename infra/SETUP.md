# Setup do deploy (feito uma vez, pelo usuário)

> Menus do Console podem variar. Se algo não bater, pare e me avise; não improvise permissões.
> Itens **[VERIFICAR]** ainda não foram testados num deploy real — confirmar no primeiro build.

## 0. Decisão de região (importante)
App e banco precisam ficar **na mesma região** (cada página faz várias consultas ao banco).
- Supabase de **produção** e Cloud Run na mesma região. Recomendado: **São Paulo**
  (Supabase `sa-east-1` + Cloud Run `southamerica-east1`, que é o padrão do `cloudbuild.yaml`).
- Se usar outra região, ajuste `_REGION` no gatilho.

## 1. Google Cloud

### 1.1 Projeto e APIs
1. Novo projeto `finance-tracker` (anote o **ID**) e vincule o faturamento.
2. Ative: Cloud Run Admin, Cloud Build, Artifact Registry, Secret Manager, Cloud Scheduler.

### 1.2 Artifact Registry
Repositório **Docker** `finance-tracker`, na região escolhida.

### 1.3 Contas de serviço (IAM → Contas de serviço)
| Conta | Uso |
|---|---|
| `ft-web` | roda o frontend |
| `ft-api` | roda a API |
| `ft-pipeline` | roda os Jobs (pipeline diário e migrations) |
| `ft-scheduler` | dispara o Job diário |

### 1.4 Segredos (Secret Manager) — um conjunto por ambiente
Nome = `ft-<ambiente>-<nome>`, com ambiente `staging` ou `production`
(ex.: `ft-staging-supabase-db-url`). Valor = conteúdo indicado.

| Segredo | Conteúdo | Usado por |
|---|---|---|
| `supabase-url` | URL do projeto Supabase | web, api, jobs |
| `supabase-publishable-key` | chave pública (`sb_publishable_…`) | web |
| `supabase-jwks-url` | `<URL>/auth/v1/.well-known/jwks.json` | api, jobs |
| `supabase-project-ref` | ref do projeto | api, jobs |
| `supabase-db-url` | **URL do pooler** (Connect → Connection pooling), não a direta | api, jobs |
| `allowed-user-ids` | UUID do seu usuário no Supabase daquele ambiente | web, api |
| `openrouter-api-key` | chave do OpenRouter (exclusiva do FinanceTracker) | api |
| `ai-model` | `~anthropic/claude-sonnet-latest` | api |
| `telegram-bot-token` | token do bot | job pipeline |
| `telegram-chat-id` | seu chat id | job pipeline |
| `api-url` | URL do serviço `ft-api` (criar **depois** do 1º deploy da API) | web |

Por que o **pooler**: o endereço direto `db.<ref>.supabase.co` só responde em IPv6 e o
Cloud Run sai por IPv4. A API já está configurada para o modo transação do pooler.

### 1.5 Permissões (mínimas)
- `ft-api`: *Secret Manager Secret Accessor* **só** nos segredos da API.
- `ft-pipeline`: *Secret Accessor* nos segredos dos jobs.
- `ft-web`: *Secret Accessor* nos segredos do web; *Cloud Run Invoker* **só** no serviço
  `ft-api` (e `ft-api-staging`). **Nunca** `allUsers` na API.
- `ft-scheduler`: *Cloud Run Invoker* no Job `ft-pipeline` (e `-staging`).
- Conta do Cloud Build: *Cloud Run Admin*, *Artifact Registry Writer*, *Logs Writer* e
  *Service Account User* **apenas** em `ft-web`, `ft-api` e `ft-pipeline`.

### 1.6 Gatilhos do Cloud Build (2 no total)
Repositório `nelsonrodrigofurlan/FinanceTracker`, configuração **arquivo do repositório**
`/cloudbuild.yaml` (não usar YAML inline).

| Gatilho | Branch | Substituições |
|---|---|---|
| `ft-staging` | `^developer$` | `_APP_ENV=staging`, `_SUFFIX=-staging` |
| `ft-production` | `^main$` | `_APP_ENV=production`, `_SUFFIX=` **(criar a chave, com valor vazio)** |

Se `_SUFFIX` não existir no gatilho de produção, vale o default `-staging` (falha segura).
**[VERIFICAR no 1º build]** `_IMAGE_BASE` usa substituições aninhadas
(`dynamicSubstitutions: true`).

### 1.7 Primeiro deploy (ordem)
1. Criar todos os segredos, **exceto** `api-url`.
2. Rodar o gatilho de staging → API e Jobs sobem; o Web pode falhar por falta de `api-url`.
3. Copiar a URL do serviço `ft-api-staging`, criar `ft-staging-api-url` e rodar o gatilho de novo.
4. Conferir que a API **não** abre no navegador (403) e que o Web abre e faz login.

### 1.8 Agendamento do pipeline (Cloud Scheduler)
Cloud Run → Jobs → `ft-pipeline` → **Gatilhos** → adicionar agendamento:
- Frequência: `0 19 * * 1-5` (19h, dias úteis), fuso **America/Sao_Paulo**.
- Conta de serviço: `ft-scheduler`.
O candle do dia só é gravado após 18h30; às 19h o pregão já fechou.

### 1.9 Proteção da `main` (GitHub)
Settings → Branches → regra para `main`: exigir Pull Request; bloquear force push.

## 2. Supabase (produção)
1. Projeto `finance-tracker-prod` na região escolhida no item 0.
2. Authentication → desligar **"Allow new users to sign up"** (também no de teste).
3. Criar seu usuário (Add user, Auto Confirm) e copiar o UUID para `allowed-user-ids`.
4. As tabelas são criadas automaticamente pelo Job de migrations a cada deploy.
5. Carga inicial de dados: executar o Job `ft-pipeline` uma vez manualmente
   (~10 min; inclui histórico completo e CDI desde 2005).

## 3. Telegram e OpenRouter
- Bot: @BotFather (selo azul) → `/newbot`; token e chat id vão para o Secret Manager.
- OpenRouter: chave exclusiva para o FinanceTracker, com limite de crédito se o painel permitir.
