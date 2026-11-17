---
description: Define e valida as métricas do projeto (modelo/metricas.yaml), a única fonte de números do dashboard e do documento de decisão
argument-hint: "[tabela — opcional; padrão: os dados tratados da análise]"
---

Você vai definir, com o usuário, as métricas do projeto. Antes de tudo, leia
as regras em `${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as. A regra 1 vale aqui
com força total: nenhum número sai de você; todo valor vem de `consultar`.

O usuário passou isto junto do comando (pode estar vazio): `$ARGUMENTS`

## Passo 1 — Ter um rascunho

Se `modelo/metricas.yaml` ainda não existe, chame `propor_modelo`
(`mcp__plugin_bi-html_bi-dados__propor_modelo`), com `tabela` = `$ARGUMENTS`
se ele veio. Sem tabela, a ferramenta usa `saidas/dados_tratados.parquet` da
análise ou a única tabela ingerida.

## Passo 2 — Revisar com o usuário (não pule)

Leia `modelo/metricas.yaml` e mostre, numa tabela curta, cada métrica com o
id, a descrição e o tipo. O rascunho é mecânico: aponte o que merece atenção
antes de o usuário confirmar, por exemplo:
- somas que não fazem sentido somar (saldo, estoque, nota, percentual);
- uma coluna de valor que mistura receitas e despesas com sinais diferentes;
- descrições genéricas ("Soma de receita"): proponha uma descrição de negócio;
- métricas que a pergunta de negócio do `contexto.md` pede e que faltam
  (por exemplo, margem = lucro ÷ faturamento, como `razao`);
- métricas que só fazem sentido com filtro (por exemplo, só o cenário
  Realizado), usando `filtro` na própria métrica.

Edite o YAML só com o ok do usuário. O formato está documentado no topo de
`${CLAUDE_PLUGIN_ROOT}/lib/bi_html/modelo.py`: ids só com minúsculas e
sublinhado, sem algarismos; todo campo `descricao` é obrigatório.

## Passo 3 — Validar e registrar a linhagem

Chame `validar_modelo` (`mcp__plugin_bi-html_bi-dados__validar_modelo`). Se
vier `ok: false`, mostre cada problema como veio, corrija com o usuário e
valide de novo. Com `ok: true`, diga que a definição, as colunas e a origem
(com hash) de cada métrica ficaram registradas em `saidas/bi/manifesto.json`.

## Passo 4 — Primeira leitura

Mostre uma consulta que responda à pergunta de negócio (do `contexto.md`, ou
pergunte qual é): chame `consultar`
(`mcp__plugin_bi-html_bi-dados__consultar`) com a métrica principal aberta
pela dimensão mais relevante. Mostre os valores **exatamente** como vieram em
`formatado`, sem arredondar nem recalcular, com a `definicao` de cada métrica.

Se o projeto veio da análise, compare com a conclusão do notebook só para
dizer se os números conferem ou divergem; quem decide o que entra no
documento de decisão é a fase F5. Termine dizendo que o dashboard é a fase F4.
