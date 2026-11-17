---
description: Atalho sem análise prévia — lê uma planilha (CSV, Excel ou texto colado), tipa as colunas e gera o relatório de qualidade
argument-hint: "[caminho do arquivo — ou cole a tabela na mensagem]"
---

Atalho do ciclo: a planilha vai direto para o BI, sem passar pelo `/analise`
do plugin analise-dados. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

O usuário passou isto junto do comando (pode estar vazio): `$ARGUMENTS`

## Passo 1 — Avisar o que o atalho significa

Em uma linha: sem análise prévia, ninguém revisou os dados nem registrou a
pergunta de negócio, e o dashboard vai sair com o aviso "sem análise prévia".
O caminho recomendado é o `/analise`. Siga em frente se o usuário quiser o
atalho (ele já pediu ao chamar este comando).

## Passo 2 — Ingerir

- Se `$ARGUMENTS` é um caminho, chame `ingerir`
  (`mcp__plugin_bi-html_bi-dados__ingerir`) com ele. Para Excel com várias
  abas, a ferramenta usa a primeira; se o resultado mostrar `outras_abas`,
  pergunte se era essa a aba certa.
- Se o usuário colou uma tabela, chame `ingerir_texto`
  (`mcp__plugin_bi-html_bi-dados__ingerir_texto`) com o texto exatamente como
  veio e um nome curto que você propõe e ele confirma.
- Sem nenhum dos dois, pergunte onde está a planilha.

Se a ferramenta devolver `ok: false`, mostre o `erro` e os `detalhes` como
vieram, explique a correção em uma frase e pare. Não tente "consertar" o
arquivo por conta própria: `dados/` guarda os originais e não é editada.

## Passo 3 — Confirmar a leitura

Mostre, numa tabela curta, cada coluna com o tipo lido (`inteiro`, `decimal`,
`data`, `mes`, `data_hora`, `booleano`, `texto`) e diga como o arquivo foi lido
(separador, decimal, codificação ou aba). Pergunte se algum tipo está errado.
Se estiver, a correção é no arquivo de origem; a ingestão não adivinha.

## Passo 4 — Perfil

Chame `perfilar` (`mcp__plugin_bi-html_bi-dados__perfilar`) com o nome da
tabela. Mostre, sem recalcular nada:
- a `situacao` (`ok`, `com_alertas` ou `bloqueado`);
- os `bloqueios` e os `alertas`, um por linha, como vieram;
- os `dados_pessoais`, se houver, dizendo que a publicação fica bloqueada até
  remover ou agregar essas colunas;
- o caminho do relatório completo (`arquivo`).

Termine dizendo que a próxima etapa é a camada de métricas (fase F2), ainda em
construção, e que `/bi-html:ciclo` mostra o estado do projeto a qualquer hora.
