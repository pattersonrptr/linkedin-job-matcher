# AGENTS.md — Instruções para AI Coding Agents

## Visão geral do projeto

LinkedIn Job Matcher — script Python que coleta vagas via scraping e as analisa com Gemini para rank por compatibilidade com o perfil do usuário.

Arquivo principal: `job_matcher.py` (self-contained, ~440 linhas).

## Diretrizes de trabalho

### Estrutura

- Projeto com arquivo único — não criar estrutura de pacotes desnecessária
- Se adicionar funcionalidades significativas, extrair em módulos separados sob um diretório `src/`

### Dependências

- `linkedin-jobs-scraper`, `google-generativeai`, `rich`
- Sempre verificar compatibilidade de versões ao atualizar qualquer dependência
- **Não introduzir novas dependências sem discutir antes** — um `requirements.txt` ou `pyproject.toml` será criado para controle; qualquer pacote novo precisa aprovação explícita antes de instalar

### Convenções

- Comentários e output em português
- Nomes de variáveis/funções em inglês
- Usar Rich para qualquer output no terminal
- Manter as seções do script separadas com o pattern `# ── NOME ──`

### Git

- **Nunca fazer push direto para `main` ou `master`** — sempre criar feature branch e PR
- Se o usuário pedir para commitar, criar uma branch nova se não existir uma
- Commits devem ter mensagens claras e concisas

### Planejamento

- **Atualizar PLAN.md ao implementar mudanças** — marcar itens como `[x]` ao completar
- Não implementar mudanças do PLAN.md sem confirmação do usuário
- Adicionar notas sobre decisões tomadas ou trade-offs encontrados

### Testes e qualidade

- Não há setup de testes atualmente — não adicionar um sem pedir antes
- Ao modificar o script, verificar manualmente que `python -c "import py_compile; py_compile.compile('job_matcher.py')"` passa

### Segurança

- **Nunca commitar ou expor chaves de API** — `GEMINI_API_KEY`, `sk-*`, ou qualquer padrão de API key em arquivos tracked. Usar variáveis de ambiente ou arquivo `.env` ignorado pelo git
- Arquivos `.env`, `*.key`, `*credentials*` devem estar no `.gitignore`
- Se encontrar credenciais acidentalmente commitadas, alertar o usuário imediatamente

### Proteção de arquivos

- **Nunca deletar `job_matcher.py`** — é o único arquivo do projeto; qualquer mudança significativa deve manter um backup ou trabalhar em branch separada

## Riscos conhecidos

- O scraping do LinkedIn é frágil (depende do HTML), pode parar de funcionar sem aviso
- API do Gemini tem rate limit — manter delays entre chamadas
- A resposta do Gemini pode vir malformada — já há tratamento básico, mas validar ao alterar prompts
