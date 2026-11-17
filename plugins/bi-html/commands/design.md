---
description: Define o visual do dashboard — design system enviado (DESIGN.md, tema do Power BI, CSS, guia de marca) ou estilo proposto pelo domínio dos dados
argument-hint: "[arquivo do design system — opcional]"
---

Você vai definir o visual do dashboard com o usuário. Antes de tudo, leia as
regras em `${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

O usuário passou isto junto do comando (pode estar vazio): `$ARGUMENTS`

## Passo 1 — Há um design system para usar?

Pergunte (ou use o que veio em `$ARGUMENTS`). As entradas aceitas são:

- **DESIGN.md** (formato aberto do Google Labs), **tema JSON do Power BI**,
  **CSS com variáveis** (padrão shadcn/ui) ou um `tokens.json` do bi-html:
  chame `importar_design` (`mcp__plugin_bi-html_bi-dados__importar_design`)
  com o caminho.
- **Imagem ou PDF de guia de marca**: leia o arquivo e escreva um rascunho em
  `design/DESIGN.md`, no formato do exemplo
  `${CLAUDE_PLUGIN_ROOT}/modelo/exemplos/DESIGN.md`, com
  as cores que você vê (`primary`, `surface`, `on-surface`, `secondary`…) e as
  famílias tipográficas. Mostre ao usuário as cores que você extraiu e peça
  confirmação **antes** de importar: cor lida de imagem é aproximada.
- **O `estilos/design-system.md` do analise-dados**, se existir no projeto:
  ofereça usá-lo, para o dashboard ter as mesmas cores dos gráficos da
  análise. Importe com `importar_design`.

## Passo 2 — Sem design system: propor pelo domínio

Chame `propor_estilos` (`mcp__plugin_bi-html_bi-dados__propor_estilos`).
Mostre em poucas linhas:
- o domínio inferido, a confiança e as colunas que serviram de evidência
  (com confiança baixa, pergunte se o domínio está certo antes de seguir);
- as duas opções de estilo, cada uma com a descrição e a cor primária;
- os blocos típicos do domínio, que serão a base da spec na fase F4.

Com a escolha do usuário, chame `aplicar_estilo`
(`mcp__plugin_bi-html_bi-dados__aplicar_estilo`) com o estilo, o domínio e
`com_acento` como veio na opção. Os estilos base são `claro`, `escuro`,
`corporativo` e `alto_contraste`.

## Passo 3 — Mostrar o resultado

Diga onde ficaram `design/tokens.json` e `design/tokens.css`, o modo padrão
(claro ou escuro, o outro é gerado) e a tipografia. Se vierem
`ajustes_de_contraste`, liste cada um (papel, cor antes e depois, contraste
antes) e explique em uma frase: a cor original não passava no critério AA da
WCAG como texto (4,5:1) ou como cor de gráfico (3:1), e só a luminosidade foi
ajustada. Se o usuário quiser a cor original mesmo assim, explique que ela
pode ficar em elementos decorativos, mas não em texto.

Termine dizendo que o dashboard é a fase F4.
