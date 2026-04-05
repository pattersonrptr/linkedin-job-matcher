# LinkedIn Job Matcher com IA 🎯

Busca vagas no LinkedIn e usa o **Gemini** para avaliar o match com o seu perfil — muito melhor que o algoritmo nativo do LinkedIn.

## Como funciona

```
LinkedIn (scraping) → vagas brutas → Gemini (análise) → lista rankeada por match
```

Para cada vaga, o Gemini retorna:
- **Score de 0 a 10**
- Skills que você tem ✅
- Skills que faltam ❌
- Análise de senioridade
- Resumo em português

---

## Instalação

### 1. Pré-requisitos

- Python 3.9+
- Google Chrome instalado
- ChromeDriver compatível com sua versão do Chrome

**Instalar ChromeDriver (Ubuntu/Debian):**
```bash
sudo apt install chromium-chromedriver
```

**Instalar ChromeDriver (Mac com Homebrew):**
```bash
brew install chromedriver
```

**Instalar ChromeDriver (Windows):**
Baixe em: https://chromedriver.chromium.org/downloads  
Adicione ao PATH do sistema.

### 2. Instalar dependências Python

```bash
pip install linkedin-jobs-scraper google-generativeai rich
```

### 3. Obter chave do Gemini (gratuita)

1. Acesse: https://aistudio.google.com/app/apikey
2. Crie uma chave (plano gratuito é suficiente)
3. Configure a variável de ambiente:

```bash
set GEMINI_API_KEY=<your_api_key_here>
```

---

## Uso

```bash
python job_matcher.py
```

O script vai:
1. Abrir um Chrome headless e coletar vagas do LinkedIn
2. Analisar cada vaga com o Gemini
3. Exibir uma tabela rankeada no terminal
4. Salvar os resultados em `resultados.json`

---

## Personalização

### Mudar as buscas

Edite o array `SEARCH_QUERIES` no script. Exemplos:

```python
Query(
    query="Backend Engineer Python FastAPI",
    options=QueryOptions(
        locations=["Brazil", "Remote"],
        filters=QueryFilters(
            time=TimeFilters.MONTH,         # ou WEEK, DAY
            remote=[RemoteFilters.REMOTE],  # só remoto
            experience=[ExperienceLevelFilters.SENIOR],
        ),
        limit=20,
    )
)
```

### Mudar o perfil

Edite o arquivo `my_profile.txt` na raiz do projeto com suas informações atualizadas.

### Ajustar filtros de resultado

```python
CONFIG = {
    "min_score": 7,      # só mostra vagas com score >= 7
    "jobs_per_query": 20, # mais vagas por busca
    "gemini_delay": 2,    # mais tempo entre chamadas (evita rate limit)
}
```

---

## Estrutura do resultado JSON

```json
[
  {
    "score": 9,
    "title": "Senior Python Backend Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "link": "https://linkedin.com/jobs/...",
    "matched_skills": ["Python", "FastAPI", "Docker", "GCP"],
    "missing_skills": ["Kubernetes"],
    "seniority_match": "exato",
    "summary": "Vaga com excelente match. Todos os requisitos principais batem com..."
  }
]
```

---

## Limitações e avisos

- **O scraping pode quebrar**: o `linkedin-jobs-scraper` depende de como o LinkedIn renderiza as páginas. Se o LinkedIn mudar o HTML, pode parar de funcionar até a lib ser atualizada.
- **Rate limiting**: o LinkedIn pode bloquear temporariamente seu IP se fizer muitas requisições. Use `slow_mo` e `gemini_delay` para moderar.
- **Termos de uso**: scraping viola os ToS do LinkedIn. Use com moderação e por conta e risco.
- **Gemini gratuito**: tem limite de ~1500 requisições/dia, mais que suficiente para uso pessoal.

---

## Solução de problemas

**Erro: `chromedriver not found`**
→ Instale o chromedriver e certifique que está no PATH.

**Erro: `selenium.common.exceptions.WebDriverException`**
→ Versão do chromedriver incompatível com o Chrome. Atualize um dos dois.

**Erro: `google.api_core.exceptions.ResourceExhausted`**
→ Rate limit do Gemini atingido. Aumente `gemini_delay` ou aguarde alguns minutos.

**Nenhuma vaga coletada**
→ O LinkedIn pode ter mudado o HTML. Verifique se há uma versão mais nova do `linkedin-jobs-scraper`:
```bash
pip install --upgrade linkedin-jobs-scraper
```