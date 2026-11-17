---
description: Valida uma spec de dashboard contra o schema e as regras do bi-html
argument-hint: "[caminho da spec — padrão: dashboard/spec.json]"
---

Valide a spec de dashboard indicada pelo usuário: `$ARGUMENTS` (se vazio, use
`dashboard/spec.json`).

1. Chame a ferramenta `validar_spec` do servidor **bi-dados**
   (`mcp__plugin_bi-html_bi-dados__validar_spec`) com o caminho relativo à pasta
   do projeto.
2. Se a spec for válida, diga isso em uma linha.
3. Se houver problemas, liste cada um como veio da ferramenta e explique a
   correção em linguagem simples. O problema mais comum é número literal num
   texto: a correção é trocar o valor por um marcador `{id_da_metrica}` e
   garantir que essa métrica está na lista `metricas` do mesmo bloco.

Não corrija a spec sem o usuário pedir. O schema fica em
`${CLAUDE_PLUGIN_ROOT}/schemas/dashboard-spec.schema.json` e um exemplo válido
em `${CLAUDE_PLUGIN_ROOT}/modelo/exemplos/spec-vendas.json`.
