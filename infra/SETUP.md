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

### 1.4 Configuração: híbrida (variáveis do gatilho + 3 segredos)
**Segredos (Secret Manager)** — só os 3 valores realmente sensíveis, nome `ft-<ambiente>-<nome>`:

| Segredo | Conteúdo | Lido por |
|---|---|---|
| `ft-<amb>-supabase-db-url` | **URL do pooler** do Supabase (Connect → Session pooler), com a senha | `ft-api`, `ft-pipeline` |
| `ft-<amb>-openrouter-api-key` | chave do OpenRouter (exclusiva do FinanceTracker) | `ft-api` |
| `ft-<amb>-telegram-bot-token` | token do bot | `ft-pipeline` |

3 segredos × 2 ambientes = 6 versões ativas = cota grátis do Secret Manager.

**Variáveis do gatilho** (públicas ou inofensivas):

| Variável | Valor |
|---|---|
| `_APP_ENV` | `staging` ou `production` |
| `_SUFFIX` | `-staging` ou vazio (produção) |
| `_SUPABASE_URL` | URL do projeto Supabase |
| `_SUPABASE_PUBLISHABLE_KEY` | chave pública `sb_publishable_…` |
| `_SUPABASE_PROJECT_REF` | ref do projeto |
| `_ALLOWED_USER_IDS` | UUID do seu usuário naquele Supabase |
| `_AI_MODEL` | `~anthropic/claude-sonnet-latest` |
| `_TELEGRAM_CHAT_ID` | seu chat id |

A URL da API é descoberta automaticamente no deploy (não precisa configurar).
Por que o **pooler**: o endereço direto `db.<ref>.supabase.co` só responde em IPv6 e o
Cloud Run sai por IPv4.

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
| `ft-staging` | `^developer$` | `_APP_ENV=staging`, `_SUFFIX=-staging` + variáveis do item 1.4 |
| `ft-production` | `^main$` | `_APP_ENV=production`, `_SUFFIX=` **(criar a chave, vazia)** + variáveis do item 1.4 |

Se `_SUFFIX` não existir no gatilho de produção, vale o default `-staging` (falha segura).
`_IMAGE_BASE` usa substituições aninhadas (`dynamicSubstitutions: true`) — confirmado no 1º build.

### 1.7 Primeiro deploy (ordem)
1. Criar os 3 segredos e as variáveis do gatilho.
2. Rodar o gatilho → migrations, API, Job e Web sobem.
3. Dar *Cloud Run Invoker* à conta `ft-web` no serviço `ft-api-<amb>` (item 1.5).
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
