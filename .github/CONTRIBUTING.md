# Guia de Contribuição — LinkedIn Job Matcher

## Regras inegociáveis

| Regra | Detalhe |
|---|---|
| **Nunca push direto a `main`** | Todo código vai por feature branch + PR |
| **Convenção de commits obrigatória** | Ver seção Conventional Commits abaixo |
| **PR com template** | Usar o template em `.github/PULL_REQUEST_TEMPLATE.md` |
| **CHANGELOG atualizado** | Todo PR que muda comportamento deve atualizar `CHANGELOG.md` |
| **PLAN_V2.md atualizado** | Marcar itens como `[x]` ao concluir |
| **Sem segredos no código** | `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `LI_AT`, `JSESSIONID` jamais commitados |

---

## Fluxo de trabalho Git

```
main  ──── feature/minha-feature ──── PR ──── merge ──── main
              └── commits
```

1. Sempre criar branch antes de codificar:
   ```bash
   git checkout main
   git pull upstream main
   git checkout -b feature/nome-descritivo
   ```
2. Commits frequentes e atômicos seguindo Conventional Commits
3. PR via GitHub com título e descrição do template
4. Ao menos 1 revisão antes do merge (pode ser self-review se for projeto solo)
5. Deletar branch após merge

---

## Conventional Commits

Formato: `<tipo>(<escopo opcional>): <descrição curta em inglês>`

### Tipos válidos

| Tipo | Quando usar |
|---|---|
| `feat` | Nova funcionalidade visível ao usuário |
| `fix` | Correção de bug |
| `refactor` | Refatoração sem mudança de comportamento |
| `docs` | Só documentação |
| `chore` | Manutenção, deps, config (nenhum impacto no usuário) |
| `test` | Adição/correção de testes |
| `perf` | Melhoria de performance |
| `ci` | Mudanças em CI/CD |

### Exemplos

```
feat(filters): add salary and country filter on display
fix(scraper): skip closed jobs (jobState != LISTED)
refactor(storage): extract filter builder to helper function
docs(github): add contributing guide and PR template
chore(deps): add streamlit to requirements.txt
feat(web): add streamlit job browser with live filters
```

### Breaking changes

Adicionar `!` após o tipo ou footer `BREAKING CHANGE:`:
```
feat(models)!: rename work_type field to workplace_type
```

---

## Versionamento Semântico

O projeto segue [SemVer](https://semver.org/):

```
MAJOR.MINOR.PATCH
  │     │     └── Bug fix, sem quebra de API
  │     └──────── Feature nova, sem quebra de API
  └────────────── Breaking change ou mudança de arquitetura
```

**Versão atual:** ver `CHANGELOG.md`

### Quando bumpar

- `fix` → PATCH (0.x.Y → 0.x.Y+1)
- `feat` → MINOR (0.X.y → 0.X+1.0)
- `feat!` / breaking → MAJOR (X.y.z → X+1.0.0)
- `docs`, `chore`, `refactor` → sem bump de versão

---

## Branches

| Padrão | Uso |
|---|---|
| `feature/<nome>` | Nova funcionalidade |
| `fix/<nome>` | Correção de bug |
| `refactor/<nome>` | Refatoração |
| `docs/<nome>` | Documentação |
| `chore/<nome>` | Manutenção, deps |
| `release/vX.Y.Z` | Preparação de release |

---

## Segurança

- Arquivos `.env`, `*.key`, `*credentials*`, `my_profile.txt` estão no `.gitignore` — nunca forçar o commit deles
- Se credenciais forem commitadas acidentalmente: revogar imediatamente, não apenas deletar do histórico
- Variáveis de ambiente para tudo que é segredo ou muda entre ambientes
