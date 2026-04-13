# Copilot Instructions — LinkedIn Job Matcher

## Sobre o projeto

Script Python (+ interface web Streamlit) que busca vagas no LinkedIn via `linkedin-api`
(session-based, sem browser) e usa OpenRouter/Qwen para avaliar compatibilidade com o
perfil do usuário. Score 0–10 com skills matching, lacunas e análise de senioridade.

## Estrutura de arquivos

```
main.py           — CLI (argparse), orquestra fluxo completo
scraper.py        — LinkedIn scraping via linkedin-api
analyzer.py       — Análise de vagas com LLM
llm.py            — Cliente OpenRouter (OpenAI-compat) com retry
storage.py        — SQLite: upsert, queries, filtros, CSV export
models.py         — Dataclass JobResult
anti_block.py     — RateLimiter, cooldown, User-Agent rotation
session_manager.py— Login automático via Chrome (undetected-chromedriver)
config.toml       — Queries, limites, modelo LLM
.env              — Segredos (gitignored)
my_profile.txt    — Perfil do candidato (gitignored)
web/app.py        — Interface Streamlit (quando existir)
```

## Regras de desenvolvimento

### Git
- **Nunca push direto para `main` ou `master`** — sempre feature branch + PR
- Mensagens de commit em inglês seguindo Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)
- PR obrigatório: título no formato `feat(scope): description`, usar template em `.github/PULL_REQUEST_TEMPLATE.md`
- Branches: `feature/<nome>`, `fix/<nome>`, `docs/<nome>`, `chore/<nome>`

### Código
- Comentários e output do terminal em **português**
- Nomes de variáveis/funções em **inglês**
- Seções separadas com `# ── NOME ──`
- Usar `rich` para qualquer output no terminal
- Usar `tqdm` para barras de progresso
- Nenhuma nova dependência sem discussão prévia

### Documentação
- Atualizar `CHANGELOG.md` em todo PR com mudança visível ao usuário
- Marcar itens concluídos em `PLAN_V2.md` com `[x]`
- Se arquitetura mudar: atualizar este arquivo

### Segurança
- `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `LI_AT`, `JSESSIONID`, `LINKEDIN_EMAIL`, `LINKEDIN_PASSWORD` — **nunca commitar**
- Se encontrar credenciais acidentalmente commitadas: alertar o usuário imediatamente

### Banco de dados
- Migrações são feitas via `ALTER TABLE IF NOT EXISTS` em `storage.py`
- Nunca dropar tabela em produção sem confirmação explícita do usuário

### Qualidade
- Antes de qualquer commit: `python -c "import py_compile; py_compile.compile('main.py')"`
- Arquivo protegido: nunca deletar `main.py` nem `job_matcher.db` sem confirmação

## Stack

- Python 3.11+
- `linkedin-api>=2.3.0` — scraping session-based
- `openai` — cliente OpenRouter
- `rich`, `tqdm` — UI terminal
- `streamlit` — interface web
- `sqlite3` — banco de dados local
- `python-dotenv` — `.env`
- `undetected-chromedriver` — login automático opcional

## Campos do JobResult (models.py)

Quando adicionar campos novos:
1. Adicionar ao `@dataclass` em `models.py`
2. Adicionar column ao `_SCHEMA` em `storage.py`
3. Adicionar migration em `_migrate_db()` em `storage.py`
4. Atualizar `job_to_row()` e `row_to_job()` em `storage.py`
5. Preencher no `scraper.py`
6. Expor como CLI arg em `main.py` se filterable

## Versão semântica (SemVer)

`MAJOR.MINOR.PATCH` — ver `CHANGELOG.md` para versão atual
