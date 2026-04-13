# PLAN V2 — LinkedIn Job Matcher Rebuild

## Summary of architectural decisions

| Aspect | Current (V1) | V2 Target | Rationale |
|--------|--------------|-----------|-----------|
| LLM | Google Gemini (`google.generativeai`) | OpenRouter → Qwen | User preference, already has key, no vendor lock-in via standard OpenAI-compatible API |
| Scraper | `linkedin-jobs-scraper` (Selenium) | `linkedin-api` (session-based, no browser) | More stable, no ChromeDriver breakage, lighter weight |
| Anti-blocking | None | Rotating user-agents, random delays, exponential backoff, session rotation | Reduce ban risk |
| Job limit | None (runs until scraper finishes) | `max_jobs` config field | User explicitly requests it |
| Storage | JSON file | SQLite + optional CSV export | Queryable, dedupable, persistent state |
| Config | Hardcoded in script | `.env` + `config.toml` / CLI args | Externalize everything sensitive or mutable |
| Resilience | None — all-or-nothing | Resume support, error recovery | Long scrapes fail sometimes |

---

## Phase 1: Project structure & dependencies

### 1.1 New dependencies
- `linkedin-api` — scraping without browser (uses LinkedIn internal API via session cookie)
- `httpx` or `openai` — OpenAI-compatible client for OpenRouter API
- `python-dotenv` — load `.env`
- `rich` — keep for terminal UI
- `tqdm` — progress bars
- `sqlite3` — stdlib, no new dep

### 1.2 Project structure
```
linkedin-searcher/
├── .env                      # secrets (gitignored)
├── config.toml               # queries, filters, LLM settings
├── my_profile.txt            # user profile (gitignored)
├── job_matcher.db            # SQLite results (gitignored)
├── main.py                   # entry point, CLI parsing
├── scraper.py                # LinkedIn scraping logic
├── llm.py                    # LLM abstraction (OpenRouter)
├── analyzer.py               # Job analysis & scoring
├── storage.py                # SQLite operations
├── anti_block.py             # Anti-blocking utilities
└── models.py                 # Data classes
```

---

## Phase 2: Anti-blocking layer

### 2.1 Browser/User-Agent rotation
Even with `linkedin-api` (no browser), HTTP headers matter. We'll rotate:
- **User-Agent strings** — pool of ~20 recent Chrome/Firefox/Edge UAs
- **Accept-Language** — randomize slightly
- **sec-ch-ua headers** — rotate Chrome versions

### 2.2 Delay strategy
- **Random delay** between API calls: `random.uniform(2, 5)` seconds
- **Exponential backoff** on 429/rate-limit: `base_delay * (2 ** attempt_count) + jitter`
- **Per-session request budget**: limit N requests per session, then rotate
- **Daily request cap**: configurable max requests per day
- **Cooldown windows**: after N consecutive jobs, pause for random 30-120 seconds

### 2.3 Session management
- Support multiple LinkedIn session cookies in `.env`
- Rotate between cookies every N requests
- Track session health (detect when a session gets banned)

---

## Phase 3: Scraper (`linkedin-api`)

### 3.1 Why `linkedin-api` over Selenium
- No ChromeDriver compatibility issues
- No headless browser overhead (faster, less memory)
- Uses LinkedIn's internal API directly (more stable HTML changes)
- Supports all the same filters: location, experience level, remote, date posted
- Session cookie auth (same as logging into LinkedIn)

### 3.2 How it works
- User provides `LI_AT` cookie from browser (grabbed manually from LinkedIn.com)
- Library handles authentication and job search
- Returns structured job data without browser rendering
- Rate limits still apply but are more predictable

### 3.3 Job limit enforcement
- `max_jobs` config field: stop collecting after N unique jobs
- Tracks count across multiple queries to avoid over-fetching
- Progress bar showing jobs collected / max_jobs target

---

## Phase 4: LLM layer (OpenRouter → Qwen)

### 4.1 API
- OpenRouter provides OpenAI-compatible endpoint: `https://openrouter.ai/api/v1`
- Base URL: `https://openrouter.ai/api/v1/chat/completions`
- Model: `qwen/qwen-2.5-72b-instruct` (or latest available)
- Client: `openai` Python package (just change `base_url` and `api_key`)
- No `google.generativeai` deprecation issues
- Standard streaming/non-streaming support

### 4.2 Why Qwen
- Strong code reasoning, competitive with Claude/GPT on benchmarks
- OpenRouter has free tiers and cheap rates for Qwen models
- 32K+ context window handles full job descriptions easily
- Good at structured JSON output with prompts

### 4.3 Fallback
- Configurable fallback model list: if primary fails, try secondary
- Retry logic with exponential backoff per OpenRouter rate limits

---

## Phase 5: Storage (SQLite)

### 5.1 Schema
```sql
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,      -- LinkedIn job ID
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    link TEXT,
    description TEXT,
    score INTEGER,
    matched_skills TEXT,              -- JSON array
    missing_skills TEXT,              -- JSON array
    seniority_match TEXT,
    summary TEXT,
    query_source TEXT,                -- which query found this job
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    jobs_collected INTEGER DEFAULT 0,
    jobs_analyzed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
```

### 5.2 Operations
- Upsert on job_id (dedup built-in)
- Query by score, company, date range
- Export to CSV on demand
- Resume: check existing job_ids before analyzing

---

## Phase 6: CLI

### 6.1 Commands
```bash
# Full run
python main.py

# With config
python main.py --config my-config.toml

# Override max jobs
python main.py --max-jobs 50

# Export to CSV
python main.py --export results.csv

# Show results from DB
python main.py --show --min-score 7

# Resume from last run
python main.py --resume

# Only scrape, don't analyze
python main.py --scrape-only

# Only analyze already-collected jobs
python main.py --analyze-only
```

---

## Implementation order

1. Scaffold: `models.py`, `storage.py`, `.env` structure
2. Anti-blocking: `anti_block.py` with UA rotation + delay strategies
3. Scraper: `scraper.py` using `linkedin-api` with anti-blocking integration
4. LLM: `llm.py` with OpenRouter/Qwen support
5. Analyzer: `analyzer.py` with prompt building + JSON parsing
6. CLI: `main.py` with argparse, subcommands, config loading
7. Integration test & polish

---

## Risks
- `linkedin-api` requires a valid LinkedIn session cookie — user must grab it from browser
- OpenRouter API may have different availability per region

---

## Phase 7: Job Filters & New Fields

> Status: [x] **completo** — branch `feature/job-filters`

### 7.1 New fields in `JobResult` (and DB)

| Field | Type | Source | Description |
|---|---|---|---|
| `is_closed` | `bool` | `details["jobState"]` | Se `jobState != "LISTED"`, vaga está fechada |
| `is_easy_apply` | `bool` | `details["applyMethod"]` | Chave começa com `...ComplexOnsiteApply` |
| `work_type` | `str` | `details["workplaceTypes"]` | `"remote"` / `"hybrid"` / `"onsite"` / `""` |
| `has_salary` | `bool` | `details.get("salary")` | Se a vaga divulga faixa salarial |
| `salary_min` | `int\|None` | `details["salary"]` | Valor mínimo (na moeda indicada) |
| `salary_max` | `int\|None` | `details["salary"]` | Valor máximo |
| `salary_currency` | `str` | `details["salary"]` | `"USD"` / `"BRL"` / `"EUR"` etc. |
| `country` | `str` | parsed de `formattedLocation` | Último token da string de localização |
| `listed_at_ts` | `int` | `details["listedAt"]` | Timestamp Unix da postagem |

### 7.2 Scraper changes
- [x] Extrair todos os campos acima em `search_jobs`
- [x] Skip automático de vagas fechadas (`is_closed=True`) durante scraping — configurável com `skip_closed` (default `True`)

### 7.3 New `listed_at` CLI override (`--date-posted`)
Mapear para segundos passados ao `search_jobs`:
- `any` → sem filtro (valor grande)
- `24h` → `86400`
- `week` → `604800` (default atual)
- `month` → `2592000`

### 7.4 New CLI display/show filters

| Flag | Tipo | Exemplo |
|---|---|---|
| `--skip-closed / --no-skip-closed` | flag | default: skip ativado |
| `--country [national\|international\|all]` | choice | `--country international` |
| `--has-salary` | flag | só vagas com salário divulgado |
| `--min-salary VALUE` | int | `--min-salary 5000` |
| `--currency CODE` | str | `--currency USD` |
| `--easy-apply` | flag | só Easy Apply |
| `--work-type [remote\|hybrid\|onsite\|all]` | choice | `--work-type remote` |
| `--company PATTERN` | str | `--company "Google"` (case-insensitive) |
| `--date-posted [any\|24h\|week\|month]` | choice | `--date-posted week` |
| `--sort [score\|date]` | choice | `--sort date` |

### 7.5 Storage changes
- [x] Adicionar novas colunas ao `_SCHEMA`
- [x] Adicionar `_migrate_db()` com `ALTER TABLE ... ADD COLUMN`
- [x] Atualizar `get_filtered_jobs()` para aceitar `JobFilter` dataclass

---

## Phase 8: Streamlit Web Interface

> Status: [x] **completo** — branch `feature/streamlit-web`

### 8.1 Requisitos funcionais
- Visualizar vagas do DB com filtros ao vivo (todos os filtros da Phase 7)
- Disparar scraping e análise pela interface (sem precisar do terminal)
- Ordenação por score ou data
- Card expandível por vaga com todos os detalhes
- Link direto para a vaga no LinkedIn
- Exportar CSV dos resultados filtrados

### 8.2 Stack
- `streamlit` — framework da interface
- `streamlit-extras` ou componentes nativos para cards expandíveis
- Backend: chama as mesmas funções de `storage.py`, `scraper.py`, `analyzer.py`

### 8.3 Arquivo: `web/app.py`
- Sidebar com todos os filtros
- Área principal com tabela/cards de resultados
- Seção "Executar busca" com configurações e botão
- Seção "Resultado da análise" com progresso em tempo real (st.empty/placeholder)
- LinkedIn API changes can break `linkedin-api` — but fixes are usually faster than Selenium-based approaches
