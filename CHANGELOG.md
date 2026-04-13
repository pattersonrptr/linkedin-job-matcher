# Changelog

Todas as mudanças notáveis neste projeto estão documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versionamento segue [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added (feature/job-filters)
- `models.py`: 9 novos campos em `JobResult` — `is_closed`, `is_easy_apply`, `work_type`, `has_salary`, `salary_min`, `salary_max`, `salary_currency`, `listed_at_ts`, `country`
- `models.py`: dataclass `JobFilter` com filtros de score, país, tipo de trabalho, salário, moeda, easy-apply, empresa e ordenação
- `scraper.py`: extração dos novos campos + helpers `_parse_country`, `_parse_work_type`, `_parse_easy_apply`, `_parse_salary`; parâmetro `skip_closed`
- `storage.py`: migração automática de DB (`_migrate_db`), `get_filtered_jobs(JobFilter)`, `export_csv(JobFilter)`; consultas com filtros dinâmicos
- `main.py`: novos args CLI `--country`, `--work-type`, `--has-salary`, `--min-salary`, `--currency`, `--easy-apply`, `--company`, `--sort`, `--date-posted`, `--skip-closed/--no-skip-closed`; tabela rich com colunas de país, tipo, salário e easy-apply
- `config.toml`: opção `skip_closed = true` em `[scraper]`

### Added (docs/github-workflow)
- `.github/CONTRIBUTING.md` — guia de contribuição com regras de Git, Conventional Commits e SemVer
- `.github/PULL_REQUEST_TEMPLATE.md` — template padrão para PRs
- `.github/copilot-instructions.md` — instruções para AI coding agents
- `CHANGELOG.md` — este arquivo
- Planejamento de novos filtros CLI e interface web Streamlit (ver `PLAN_V2.md`)

---

## [0.2.0] — 2026-04-06

### Added
- **V2 completa**: reescrita do projeto com arquitetura modular
- `scraper.py` — scraping via `linkedin-api` (session-based, sem browser)
- `llm.py` — cliente OpenRouter (OpenAI-compat) com retry e backoff exponencial
- `analyzer.py` — análise de vagas com LLM, score 0-10
- `storage.py` — banco SQLite com upsert, deduplicação, filtros e export CSV
- `anti_block.py` — RateLimiter com cooldown periódico e rotação de User-Agent
- `models.py` — dataclass `JobResult`
- `session_manager.py` — login automático via `undetected-chromedriver`; persiste cookies no `.env`
- `main.py` — CLI completa com argparse (`--show`, `--export`, `--resume`, `--scrape-only`, `--analyze-only`)
- `config.toml` — queries, limites, modelo LLM externalizados
- `requirements.txt` com todas as dependências

### Fixed
- Extração de `company` e `location`: estrutura da `linkedin-api` mudou (chave dinâmica voyager em `companyDetails`, `formattedLocation` em vez de `locationName`)
- Prioridade de `OPENROUTER_MODEL`: variável de ambiente tem precedência sobre `config.toml`
- Perda de progresso na análise: cada vaga agora é salva no DB imediatamente após análise (save incremental)

### Changed
- Substituído `linkedin-jobs-scraper` (Selenium) por `linkedin-api` (session cookies)
- Substituído Google Gemini por OpenRouter (API OpenAI-compatível)
- Storage migrado de JSON para SQLite

---

## [0.1.0] — 2026-03-01

### Added
- Versão inicial (`job_matcher.py`) — script monolítico com `linkedin-jobs-scraper`, Gemini e Rich
