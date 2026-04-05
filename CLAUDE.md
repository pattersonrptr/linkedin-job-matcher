# CLAUDE.md — LinkedIn Job Matcher

## Sobre o projeto

Script Python que busca vagas no LinkedIn e usa o Google Gemini para avaliar compatibilidade com o perfil do usuário, gerando um score de 0–10 com skills matching, lacunas e análise de senioridade.

## Estrutura

- `job_matcher.py` — único arquivo do projeto, contém toda a lógica: scraping via `linkedin-jobs-scraper`, análise com Gemini (`google-generativeai`), exibição com Rich e salvamento JSON
- `resultados.json` — gerado em runtime

## Tech stack

- Python 3.9+
- `linkedin-jobs-scraper` (scraping via Chrome headless/Selenium)
- `google-generativeai` (modelo `gemini-1.5-flash`)
- `rich` (display no terminal)

## Execução

```bash
pip install linkedin-jobs-scraper google-generativeai rich
export GEMINI_API_KEY="sua_chave"
python job_matcher.py
```

## Variáveis de configuração (no próprio script)

- `CONFIG` — API key, modelo, score mínimo, jobs por query, delay
- `MY_PROFILE` — perfil profissional usado na análise
- `SEARCH_QUERIES` — queries e filtros aplicados na busca

## Convenções

- O script é self-contained; não há pacotes multi-módulo, tests, ou CI/CD
- Configurações ficam hardcoded no topo do arquivo (exceto Gemini key via env var)
- Idiomas: comentários e docs em português, código em inglês
