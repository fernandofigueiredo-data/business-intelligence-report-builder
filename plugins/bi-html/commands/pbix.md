---
description: Converte um relatório do Power BI (.pbix em modo de importação) em dashboard do bi-html, com o teste de equivalência das medidas e o relatório de fidelidade
argument-hint: "<caminho do .pbix>"
---

Você vai converter um .pbix em dashboard do bi-html (Fluxo 2, via (a) do plano).
Antes de tudo, leia as regras em `${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.
A regra 1 vale com força total: os números do dashboard saem da camada de
métricas, recalculados sobre os dados do .pbix; nada é copiado do relatório.

Arquivo: `$ARGUMENTS`. Sem argumento, pergunte o caminho do .pbix.

## Passo 1 — Converter

Chame `converter_pbix` (`mcp__plugin_bi-html_bi-dados__converter_pbix`) com o
caminho. A ferramenta faz tudo e pode levar alguns minutos num modelo grande
(o teste de equivalência avalia cada medida traduzida no Power BI). Avise o
usuário antes de chamar.

- `ok: false` com DirectQuery, conexão dinâmica ou modo misto: explique que os
  dados não estão no arquivo e apresente as duas saídas que vieram em
  `detalhes` (a via (b), que incorpora o relatório original pelo Power BI, ou
  salvar uma cópia em importação). Não tente contornar.
- `ok: false` porque `modelo/metricas.yaml` já existe: pergunte se é para
  sobrescrever (`sobrescrever: true`) ou usar outra pasta.

## Passo 2 — Mostrar o resultado com franqueza

Leia `saidas/bi/pbix/fidelidade.md` e resuma, nesta ordem:

1. **Tabelas:** se a contagem de linhas bateu em todas (`tabelas_iguais`).
2. **Medidas:** quantas foram traduzidas, quantas são de texto e quantas não
   foram traduzidas, com os motivos mais comuns. Diga quais traduzidas
   passaram no teste de equivalência (`equivalencia`, "n de n contextos") e
   quais ficaram com o selo "não validada".
3. **Visuais:** quantos viraram bloco ou filtro, quantos ficaram parciais e
   quantos não foram convertidos, página a página, com os motivos.
4. **Semântica:** as diferenças conhecidas, como estão no relatório (filtro
   numa tabela que não se liga ao fato; filtro do CALCULATE).

Não arredonde nem reescreva números: cite as contagens como vieram.

## Passo 3 — Ver e publicar

- As páginas ficam em `saidas/bi/paginas/<pagina>.html` e a primeira também em
  `saidas/bi/dashboard.html`. Ofereça abrir.
- Para pôr o relatório original do Power BI ao lado do convertido, indique
  `/bi-html:comparar` (via (b)).
- Se `publicacao_bloqueada` não estiver vazio, **não publique** (regra 5).
- Senão, com o ok do usuário, publique a página como Artifact
  (`saidas/bi/paginas/<pagina>.artifact.html`, `icon` "chart"). Medidas não
  traduzidas não aparecem no dashboard; diga isso ao publicar.

## Passo 4 — Ajustes

O modelo convertido (`modelo/metricas.yaml`) e as specs
(`dashboard/paginas/*.json`) são pontos de partida: o usuário pode renomear
métricas, mudar blocos e trocar o estilo (`/bi-html:design`). Para renderizar
de novo a página principal, use `/bi-html:dashboard`. Converter de novo o mesmo
.pbix sobrescreve o que a conversão gerou.
