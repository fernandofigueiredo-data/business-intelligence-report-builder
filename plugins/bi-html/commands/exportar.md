---
description: Gera uma cópia do dashboard num único arquivo HTML que abre sem internet, para enviar por WhatsApp, e-mail ou pendrive
argument-hint: "[spec de outra página, opcional]"
---

Você vai gerar a cópia de envio do dashboard. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

## Passo 1 — Explicar o que muda em relação ao Artifact

Diga, em uma ou duas frases, antes de gerar:

- o arquivo pode ser reencaminhado sem controle e **não pode ser revogado**
  depois de enviado (o Artifact pode ser apagado e derruba o link);
- ele leva só os números agregados do dashboard, não as linhas da tabela;
- ele não se atualiza: é uma cópia congelada, com a data no rodapé.

## Passo 2 — Gerar

Chame `exportar_offline` (`mcp__plugin_bi-html_bi-dados__exportar_offline`).
Com `$ARGUMENTS` (uma spec de página, por exemplo
`dashboard/paginas/visao_geral.json`), passe em `spec`.

- `ok: false` por dados pessoais: **não** contorne (regra 5). Diga quais
  colunas e que o caminho é removê-las ou agregá-las.
- `ok: false` porque o ECharts não pôde ser baixado: mostre os detalhes como
  vieram (sem internet, a variável `BI_HTML_ECHARTS` aponta para um
  `echarts.min.js` local da versão indicada).
- `ok: true`: mostre o caminho e o tamanho do arquivo.
