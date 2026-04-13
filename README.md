# LinkedIn Job Matcher V2 💼

Busca vagas no LinkedIn e usa **IA via OpenRouter** para avaliar o match com o seu perfil — score de 0 a 10, com skills match, lacunas e análise de senioridade.

Disponível como **CLI** (`main.py`) e **interface web** (`streamlit run web/app.py`).

## Como funciona

```
LinkedIn (linkedin-api, session-based) → vagas brutas → OpenRouter LLM → lista rankeada por match
```

Para cada vaga, o LLM retorna:
- **Score de 0 a 10**
- Skills que você tem ✅
- Skills que faltam ❌
- Análise de senioridade
- Resumo em português

---

## Instalação

### 1. Pré-requisitos

- Python 3.11+
- Conta no LinkedIn (para extrair cookies de sessão)
- Conta no [OpenRouter](https://openrouter.ai) (API key gratuita disponível)

### 2. Instalar dependências Python

```bash
# Windows: instalar lxml antes dos demais
pip install lxml --only-binary :all:
pip install -r requirements.txt
```

### 3. Configurar `.env`

Copie o exemplo e preencha com suas credenciais:

```bash
cp .env.example .env
```

```dotenv
# .env
OPENROUTER_API_KEY=sk-or-...        # obrigatório — chave do OpenRouter
OPENROUTER_MODEL=qwen/qwen3.6-plus:free  # opcional — sobrescreve config.toml

LI_AT=<cookie li_at do LinkedIn>    # obrigatório — cookie de sessão
JSESSIONID=<cookie JSESSIONID>      # obrigatório — cookie de sessão

# Opcional — usado pelo session_manager para login automático via Chrome
LINKEDIN_EMAIL=seu@email.com
LINKEDIN_PASSWORD=suasenha
```

**Como obter os cookies do LinkedIn:**
1. Faça login em linkedin.com no Chrome/Firefox
2. Abra DevTools → Aba **Application** → **Cookies** → `https://www.linkedin.com`
3. Copie os valores de `li_at` e `JSESSIONID`

> Ou deixe `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` preenchidos — o `session_manager.py` faz login automático via Chrome quando os cookies estiverem ausentes/expirados.

### 4. Configurar seu perfil

Edite `my_profile.txt` com suas informações profissionais (experiência, skills, stacks).

### 5. Configurar buscas

Edite `config.toml`:

```toml
[scraper]
max_jobs = 30
listed_at = 604800   # 7 dias em segundos
skip_closed = true

[llm]
model = "qwen/qwen3.6-plus:free"

[app]
min_score = 6

[[queries]]
query = "Python Backend Engineer"
location = "Brazil"
experience = ["4"]   # Mid-Senior
job_type = ["F"]     # Full-time
remote = ["2", "3"]  # Remote, Hybrid
```

---

## Uso — CLI

### Busca + análise completa

```bash
python main.py
```

### Apenas coletar vagas (sem análise LLM)

```bash
python main.py --scrape-only --max-jobs 50
```

### Apenas analisar o que está no banco

```bash
python main.py --analyze-only
```

### Mostrar resultados salvos com filtros

```bash
python main.py --show
python main.py --show --work-type remote --min-score 7
python main.py --show --country international --sort date
python main.py --show --has-salary --currency USD --min-salary 5000
python main.py --show --easy-apply --company "Google"
```

### Exportar para CSV

```bash
python main.py --export vagas.csv --min-score 6 --work-type remote
```

### Retomar busca interrompida

```bash
python main.py --resume
```

### Todos os filtros disponíveis

| Flag | Tipo | Descrição |
|---|---|---|
| `--min-score N` | int | Score mínimo (sobrescreve config.toml) |
| `--work-type` | remote/hybrid/onsite/all | Tipo de trabalho |
| `--country` | national/international/all | `national` = Brasil |
| `--has-salary` | flag | Só vagas com salário divulgado |
| `--min-salary N` | int | Salário mínimo |
| `--currency CODE` | str | Moeda: USD, BRL, EUR… |
| `--easy-apply` | flag | Só Easy Apply |
| `--company NOME` | str | Filtro por empresa (substring) |
| `--sort` | score/date | Ordenação dos resultados |
| `--date-posted` | 24h/week/month/any | Data de postagem |
| `--skip-closed` / `--no-skip-closed` | flag | Ignorar vagas fechadas (padrão: ativo) |
| `--max-jobs N` | int | Máximo de vagas a coletar |
| `--scrape-only` | flag | Só coleta, sem análise LLM |
| `--analyze-only` | flag | Só analisa vagas já coletadas |
| `--resume` | flag | Retoma busca, pula já coletadas/analisadas |
| `--export PATH` | path | Exporta CSV com os filtros aplicados |
| `--show` | flag | Exibe resultados sem scraping |

---

## Uso — Interface Web

```bash
streamlit run web/app.py
```

Abre em `http://localhost:8501` com 3 abas:

- **📋 Resultados** — filtros ao vivo, cards expandíveis, exportação CSV
- **🚀 Executar Busca** — dispara scraping + análise LLM pela interface com output em tempo real
- **🗄️ Banco de Dados** — métricas, tabela completa, exportação CSV total

---

## Estrutura do projeto

```
main.py            — CLI (argparse), orquestra o fluxo completo
scraper.py         — Scraping via linkedin-api (session-based)
analyzer.py        — Análise de vagas com LLM
llm.py             — Cliente OpenRouter (OpenAI-compat) com retry
storage.py         — SQLite: upsert, queries, filtros, CSV export
models.py          — Dataclasses JobResult e JobFilter
anti_block.py      — RateLimiter, cooldown, delays
session_manager.py — Login automático via Chrome (undetected-chromedriver)
config.toml        — Queries, limites, modelo LLM
my_profile.txt     — Perfil do candidato (gitignored)
web/app.py         — Interface Streamlit
```

---

## Limitações e avisos

- **Cookies expiram**: o LinkedIn invalida sessões periodicamente. Use `LINKEDIN_EMAIL`/`LINKEDIN_PASSWORD` para renovação automática.
- **Rate limiting**: o LinkedIn pode bloquear temporariamente. Os delays em `config.toml` ajudam a mitigar.
- **Modelo LLM lento**: modelos gratuitos do OpenRouter têm limite de ~1 req/min. Para 30 vagas, espere ~30 min.
- **Termos de uso**: scraping viola os ToS do LinkedIn. Use com moderação e por conta e risco.
