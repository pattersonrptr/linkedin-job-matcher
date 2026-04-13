---
name: Pull Request
about: Proposta de mudança no LinkedIn Job Matcher
---

## Tipo de mudança

<!-- Marque com [x] o que se aplica -->
- [ ] `feat` — Nova funcionalidade
- [ ] `fix` — Correção de bug
- [ ] `refactor` — Refatoração sem mudança de comportamento
- [ ] `docs` — Documentação
- [ ] `chore` — Manutenção / deps
- [ ] `breaking` — Quebra de compatibilidade (API/CLI/DB)

## O que faz este PR?

<!-- Descrição objetiva em 2-4 frases do que foi implementado/corrigido. -->

## Por que é necessário?

<!-- Contexto ou problema que motivou a mudança. -->

## Como testar

```bash
# Passos mínimos para verificar que funciona
python main.py --...
```

## Checklist

- [ ] Código segue as convenções do projeto (inglês para código, PT para comentários)
- [ ] `CHANGELOG.md` atualizado (nova entrada na versão apropriada)
- [ ] `PLAN_V2.md` atualizado (itens marcados como `[x]` se aplicável)
- [ ] `requirements.txt` atualizado se novas dependências foram adicionadas
- [ ] Sem segredos, chaves ou dados pessoais no diff
- [ ] `python -c "import py_compile; py_compile.compile('main.py')"` passa

## Breaking changes

<!-- Se houver: descreva o que muda e como migrar. Caso contrário: N/A -->
