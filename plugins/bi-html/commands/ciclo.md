---
description: Conduz o ciclo Planilha → Análise → Dashboard → BI, a partir da etapa em que o projeto está
argument-hint: "[caminho da planilha — opcional]"
---

Você conduz o ciclo do plugin bi-html. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

O usuário passou isto junto do comando (pode estar vazio): `$ARGUMENTS`

## Passo 1 — Ler o estado

Chame a ferramenta `estado_do_ciclo` do servidor **bi-dados** do plugin
(`mcp__plugin_bi-html_bi-dados__estado_do_ciclo`). Decida a etapa pelo
resultado da ferramenta, não listando pastas por conta própria.

Se a ferramenta não estiver disponível, o servidor MCP não conectou (na
primeira vez, o `uv` ainda pode estar baixando as dependências). Peça ao
usuário para digitar `/mcp`, escolher o servidor **bi-dados** do plugin
bi-html → **Reconnect**, e avisar quando terminar.

## Passo 2 — Seguir pela etapa

Abra a resposta com uma linha que diga a etapa atual. Depois:

**planilha** — Se `$ARGUMENTS` trouxe um caminho, confirme que ele existe e
copie o arquivo para `dados/` (copie, não mova). Se não, pergunte onde está a
planilha. Com o arquivo em `dados/`, volte ao Passo 1.

**analise** — Há duas situações, e o resultado diz qual é:
- `contrato` vazio: a análise não começou. Indique o `/analise` do plugin
  analise-dados, que conduz o notebook com o usuário (caminho recomendado).
  Mencione o atalho `/bi-html:ingerir`, que leva a planilha direto ao BI com
  o aviso "sem análise prévia". Se o analise-dados não estiver instalado,
  diga isso e ofereça o atalho.
- `contrato` com `faltando`: a análise começou, mas não entregou tudo.
  Mostre cada item de `faltando` como veio (arquivo, o que falta e a
  correção), sem reformular nem acrescentar itens. Itens com estado
  `alerta` vão numa linha à parte, como pontos a conferir que não bloqueiam.

**metricas** — Falta definir (ou corrigir) o modelo de métricas. Se o
projeto veio da análise, faça antes o resumo descrito em **dashboard** abaixo
(objetivo e conclusão, sem perguntar de novo). Depois indique
`/bi-html:metricas`. Se o `proximo_passo` traz problemas do modelo, mostre-os
como vieram.

**dashboard** — Métricas validadas. Se o projeto veio da análise, chame `checar_contrato`
(`mcp__plugin_bi-html_bi-dados__checar_contrato`) e mostre, **sem perguntar
de novo ao usuário**:
- a pergunta de negócio, o público e a decisão, como estão no `contexto`;
- os itens da `conclusao`, que serão as métricas candidatas do dashboard;
- o tamanho dos dados tratados (linhas e colunas) e os alertas, se houver.

Os números que aparecem nesses textos vêm da análise, que já foi revisada;
repita-os como estão, sem recalcular nem arredondar. Depois diga com clareza
que o dashboard (F4) ainda está em construção, e não tente gerar dashboard,
spec ou números por outro caminho; para ver números agora, use `consultar`.

**perfil** — Há tabelas ingeridas pelo atalho, mas todas bloqueadas pelo
perfil. Mostre o `proximo_passo` como veio.

**bi** e **pbix** — Diga que essas etapas estão em construção (fases F5 a F7
do `PLANO_DE_CONSTRUCAO.md`).
