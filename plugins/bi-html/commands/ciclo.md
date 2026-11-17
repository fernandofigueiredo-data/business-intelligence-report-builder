---
description: Mostra em que etapa do ciclo Planilha → Análise → Dashboard → BI o projeto está e qual é o próximo passo
argument-hint: "(sem argumentos)"
---

Você conduz o ciclo do plugin bi-html. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

## Passo 1 — Ler o estado

Chame a ferramenta `estado_do_ciclo` do servidor **bi-dados** do plugin
(`mcp__plugin_bi-html_bi-dados__estado_do_ciclo`). Não liste pastas por conta
própria para decidir a etapa: use o resultado da ferramenta.

Se a ferramenta não estiver disponível, o servidor MCP não conectou (na
primeira vez, o `uv` ainda pode estar baixando as dependências). Peça ao
usuário para digitar `/mcp`, escolher o servidor **bi-dados** do plugin
bi-html → **Reconnect**, e avisar quando terminar.

## Passo 2 — Mostrar ao usuário

Em até 5 linhas: a etapa atual, o que já existe (os itens `presentes` que
estão como verdadeiros) e o `proximo_passo` devolvido pela ferramenta.

- Etapa **planilha**: pergunte onde está o arquivo e ofereça copiá-lo para
  `dados/` (copie, não mova).
- Etapa **analise**: indique o `/analise` do plugin analise-dados. Se ele não
  estiver instalado, diga isso e mencione o atalho sem análise prévia.
- Etapas **dashboard**, **bi** e **pbix**: diga com clareza que essas etapas
  ainda estão em construção (fases F1 a F7 do `PLANO_DE_CONSTRUCAO.md`) e não
  tente produzir dashboard ou números por outro caminho.
