# PLAN.md — Melhorias do LinkedIn Job Matcher

---

## 1. Scraping mais confiável

**Problema:** `linkedin-jobs-scraper` depende de Selenium/ChromeDriver, que quebra frequentemente e é lento.

**Solução:**
- **Opção A:** Trocar por [linkedin-api](https://github.com/tomquirk/linkedin-api) (usa requests sem browser, mais estável). Requer login via session cookie.
- **Opção B:** Manter o scraper atual mas pinar versão, adicionar health check na inicialização e fallback com mensagem clara.
- **Decisão pendente:** Avaliar se `linkedin-api` suporta os mesmos filtros (remote, experience level, location). Se sim, Opção A. Caso contrário, Opção B.

**Files affected:** `job_matcher.py` (função `collect_jobs`)

---

## 2. Resiliência — resume e salvamento incremental

**Problema:** Se o scraper ou Gemini falha no meio, perde todo o trabalho.

**Solução:**
- Salvar cada vaga analisada em um arquivo `.partial.jsonl` (append-only)
- Flag `--resume` recarrega vagas já processadas e continua de onde parou
- Flag `--output` para nomear o arquivo de saída
- No fim, mesclar parcial + novos → `resultados.json`

**Pseudocode:**
```python
def load_resume(path):
    # lê JSONL, retorna set de URLs já processadas
    ...

def save_partial(job, path):
    # append JSON ao .partial.jsonl
    ...
```

**Files affected:** `job_matcher.py` (funções `analyze_with_gemini`, `save_results`, `main`)

---

## 3. Chamadas concorrentes ao Gemini

**Problema:** 45 vagas × 1.5s delay = ~70s de espera desnecessária.

**Solução:**
- Usar `concurrent.futures.ThreadPoolExecutor` com max 5 workers
- Manter rate limit respeitando por-worker delay
- Manter output com Rich (progress bar ou status spinner)

**Pseudocode:**
```python
with ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(analyze_one, jobs))
```

**Files affected:** `job_matcher.py` (função `analyze_with_gemini`)

---

## 4. Extração robusta de JSON

**Problema:** Regex `r"^```json\s*...\s*```$"` falha se Gemini adiciona texto antes/depois ou usa outro label.

**Solução:**
- Procurar o primeiro `{` e o último `}` do texto de resposta
- Tentar `json.loads(content[start:end+1])`
- Se falhar, tentar novamente com o segundo `{`…
- Logear a resposta crua em caso de erro

**Pseudocode:**
```python
def extract_json(text):
    # encontra o JSON mais externo por matching de braces
    ...
```

**Files affected:** `job_matcher.py` (dentro de `analyze_with_gemini`)

---

## 5. Remover `"Remote"` da lista de locations

**Problema:** `"Remote"` não é uma location válida no LinkedIn. O filtro de remoto é feito via `RemoteFilters`, não via `locations`.

**Solução:**
- Remover `"Remote"` do array `locations=["Brazil", "Remote"]`
- Manter apenas `locations=["Brazil"]`
- O `remote=[RemoteFilters.REMOTE, RemoteFilters.HYBRID]` já filtra o que importa

**Files affected:** `job_matcher.py` (`SEARCH_QUERIES`)

---

## 6. Config e perfil em arquivo externo

**Problema:** Editar código para mudar queries, perfil ou configurações.

**Solução:**
- Criar `config.toml` com 3 seções:
  - `[app]` — gemini_api_key (ou manter env var), min_score, jobs_per_query, gemini_delay, save_json, output_file
  - `[profile]` — profile_file (path para `.toml` ou string inline)
  - `[[queries]]` — array de queries com query text, locations, filters sub-fields
- Manter `MY_PROFILE` em arquivo `.toml` separado por seção (permite múltiplos perfis: `backend.toml`, `devops.toml`)
- CLI flag `--config config.toml` (default `config.toml` no cwd)
- **Opcional:** `--profile devops.toml` para trocar perfil sem editar nada

**Example `config.toml`:**
```toml
[app]
min_score = 6
jobs_per_query = 15
gemini_delay = 1.5
save_json = true
output_file = "resultados.json"

[[queries]]
query = "Python Backend Engineer"
locations = ["Brazil"]
filters.time = "WEEK"
filters.type = ["FULL_TIME"]
filters.experience = ["MID_SENIOR", "SENIOR"]
filters.remote = ["REMOTE", "HYBRID"]

[[queries]]
query = "DevOps Platform Engineer Terraform"
locations = ["Brazil"]
filters.time = "WEEK"
filters.remote = ["REMOTE", "HYBRID"]
```

**Example `profile.toml`:**
```toml
name = "Patterson A. da Silva Junior"
title = "Software Engineer"
experience_years = "10+"
summary = "Engenheiro de software com foco em backend..."

[skills]
languages = ["Python", "C#", "JavaScript"]
frameworks = ["FastAPI", "Django", "Flask", "React"]
cloud = ["GCP", "AWS"]
devops = ["Terraform", "Docker", "GitLab CI/CD"]
databases = ["PostgreSQL", "SQL"]
other = ["Selenium", "Git", "Google Pub/Sub", "SQLAlchemy"]

[preferences]
remote = true
hybrid = true
roles = ["Backend", "Cloud", "DevOps", "Platform Engineering"]
```

**Files affected:** `job_matcher.py`, `config.toml` (novo), `profile.toml` (novo), dependência `tomli`/`tomllib` (Python 3.11+ já inclui `tomllib`)

---

## 7. Deduplicação por URL

**Problema:** Mesma vaga aparece em múltiplas queries.

**Solução:**
- Usar um `dict[str, JobResult]` com URL como key
- Vagas duplicadas são sobrepostas (a primeira que aparece vence, ou a com maior score se analisar antes)

**Files affected:** `job_matcher.py` (merge logic pós-coleta)

---

## 8. CLI com argumentos

**Problema:** Queries e configuração só via edição de código/arquivo.

**Solução:**
- Usar `argparse` (stdlib, zero deps)
- Flags:
  - `--config` — path do config (default `config.toml`)
  - `--profile` — path do profile (default `profile.toml`)
  - `--query` — adiciona queries extras via CLI (pode repetir: `--query "X" --query "Y"`)
  - `--resume` — retoma de arquivo existente
  - `--min-score` — override do config
  - `--output` — override do output file
  - `--workers` — número de workers Gemini (default 5)

**Files affected:** `job_matcher.py` (nova função `parse_args`, mudanças em `main`)

---

## 9. Tracking de data nos resultados

**Problema:** `resultados.json` não diz quando foi gerado.

**Solução:**
- Envolver output em objeto `{ "generated_at": "2026-04-05T...", "profile": "...", "jobs": [...] }`
- Adicionar campo `query_source` por vaga para saber de onde veio

**Files affected:** `job_matcher.py` (função `save_results`)

---

## 10. Descrições longas — chunking ou summarização

**Problema:** `job.description[:3000]` corta no meio e pode perder requisitos.

**Solução:**
- Se descrição > 3000 chars, mandar o Gemini resumir para 1500 chars em uma chamada preliminar
- Usar o resumo + primeiros 3000 chars na análise principal
- Ou usar um modelo com contexto maior (`gemini-1.5-pro` suporta 2M tokens)

**Trade-off:** Chamada extra ao Gemini = mais tempo/custo. Para `gemini-1.5-flash` que suporta 1M tokens, pode-se simplesmente remover o corte de 3000 chars.

**Files affected:** `job_matcher.py` (função `build_prompt`, `analyze_with_gemini`)

---

## Ordem sugerida de execução

| Etapa | Mudança | Dependências |
|-------|---------|--------------|
| 1 | Config externo (#6) | Nenhum refactor — base para o resto |
| 2 | Profile externo (#6) | Independente |
| 3 | CLI args (#8) | Depende de #6 |
| 4 | Fix locations (#5) | Independente, quick win |
| 5 | Resume + salvamento incremental (#2) | Independente |
| 6 | Deduplicação (#7) | Independente |
| 7 | JSON robusto (#4) | Independente |
| 8 | Concorrência Gemini (#3) | Depende de #2 (resume) |
| 9 | Tracking de data (#9) | Independente, trivial |
| 10 | Scraping confiável (#1) | Risco alto — fazer por último, isolado |
| 11 | Descrições longas (#10) | Depende da escolha do modelo |

**Etapa 4 (fix locations) é um quick win — 1 linha de mudança, pode ser feita primeiro.**

---

## Riscos e considerações

- **#1 (Scraping) é o mais arriscado** — pode quebrar completamente. Fazer isolado, testar bem antes de mergear.
- **#3 (Concorrência) pode hit Gemini rate limits** — implementar com backoff exponencial.
- **#6/#8 mudam a interface** — qualquer automation ou script que chama `python job_matcher.py` vai precisar de ajuste. Manter compatibilidade: se `config.toml` não existe, cair nos defaults hardcoded.
