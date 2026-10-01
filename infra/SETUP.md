# Setup inicial (feito uma vez, pelo usuário)

> Os nomes de menus do Console podem variar um pouco. Se algo não bater, pare e me avise; não improvise permissões.

## 1. Google Cloud

### 1.1 Projeto
1. Console → seletor de projetos → **Novo projeto** → nome `finance-tracker`.
2. Anote o **ID do projeto** (pode ganhar um sufixo numérico) e me passe.
3. Vincule a conta de faturamento.

### 1.2 APIs a ativar
- Cloud Run Admin API
- Cloud Build API
- Artifact Registry API
- Secret Manager API
- Cloud Scheduler API (usada na F2)

### 1.3 Artifact Registry
Repositório **Docker** chamado `finance-tracker`, região `southamerica-east1`.

### 1.4 Service accounts (IAM → Contas de serviço)
| Conta | Uso | Papéis (mínimos) |
|---|---|---|
| `ft-web` | roda o frontend | nenhum no projeto; recebe *Invoker* só no serviço da API (passo 1.6) |
| `ft-api` | roda a API | *Secret Manager Secret Accessor* (só nos segredos que usar, F1+) |
| `ft-pipeline` | roda o Job diário | *Secret Manager Secret Accessor* (F2+) |
| `ft-scheduler` | dispara o Job | *Cloud Run Invoker* no Job (F2) |

### 1.5 Permissões da conta do Cloud Build
A conta que executa os gatilhos precisa de:
- *Cloud Run Admin*
- *Artifact Registry Writer*
- *Service Account User* **apenas** nas contas `ft-web`, `ft-api` e `ft-pipeline` (não no projeto todo)
- *Logs Writer*

### 1.6 Após o primeiro deploy da API (staging e prod)
Cloud Run → `ft-api-staging` (e depois `ft-api`) → **Permissões** → adicionar `ft-web@<PROJECT_ID>.iam.gserviceaccount.com` com papel **Cloud Run Invoker**.
Confirme que **não** existe `allUsers` nas permissões da API.

### 1.7 Gatilhos do Cloud Build (4 no total)
Repositório GitHub `nelsonrodrigofurlan/FinanceTracker`. Tipo de configuração: **arquivo do Cloud Build (no repositório)** — não usar YAML inline.

| Nome | Branch | Arquivo | Filtro "arquivos incluídos" | Substituições |
|---|---|---|---|---|
| `ft-api-staging` | `^developer$` | `infra/cloudbuild-api.yaml` | `api/**`, `infra/cloudbuild-api.yaml` | `_APP_ENV=staging`, `_SUFFIX=-staging` |
| `ft-web-staging` | `^developer$` | `infra/cloudbuild-web.yaml` | `web/**`, `infra/cloudbuild-web.yaml` | `_APP_ENV=staging`, `_SUFFIX=-staging` |
| `ft-api-prod` | `^main$` | `infra/cloudbuild-api.yaml` | `api/**`, `infra/cloudbuild-api.yaml` | `_APP_ENV=production`, `_SUFFIX=` (vazio) |
| `ft-web-prod` | `^main$` | `infra/cloudbuild-web.yaml` | `web/**`, `infra/cloudbuild-web.yaml` | `_APP_ENV=production`, `_SUFFIX=` (vazio) |

Atenção: nos gatilhos de **prod**, `_SUFFIX` precisa existir **e** estar vazio. Se a chave não for criada, vale o default do arquivo (`-staging`), e o deploy vai para staging (falha segura, mas não é o que queremos).

### 1.8 Proteção da `main` no GitHub
Settings → Branches → regra para `main`: exigir Pull Request antes do merge; bloquear force push.

## 2. Supabase
1. Criar dois projetos: `finance-tracker-prod` e `finance-tracker-test`, região **South America (São Paulo)**.
2. Em ambos: Authentication → desligar **"Allow new users to sign up"**.
3. Copiar `.env.example` para `.env` na raiz do repositório e preencher **apenas com o projeto de teste**.
4. Chaves de **produção**: não colocar em arquivo; vamos cadastrá-las juntos no Secret Manager na F1.

## 3. Telegram
1. No Telegram, conversar com **@BotFather** → `/newbot` → escolher nome → guardar o token.
2. Mandar qualquer mensagem para o seu bot novo.
3. Abrir `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador e anotar o `chat.id`.
4. Token e chat id vão no `.env` (teste) e no Secret Manager (prod).

## 4. OpenRouter
Gerar uma chave **exclusiva** para o FinanceTracker (não reutilizar a do palpitaria) e, se o painel permitir, definir limite de crédito para ela.
