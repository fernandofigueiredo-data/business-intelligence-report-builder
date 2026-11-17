---
description: Monta o dashboard — escreve a spec a partir das métricas e do design, renderiza o HTML e publica como Artifact
argument-hint: "(sem argumentos)"
---

Você vai montar o dashboard do projeto. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as. Regra 1 e regra 2 valem aqui com
força total: a spec descreve o dashboard e **não carrega número nenhum**.

## Passo 1 — Reunir o que já foi decidido

- Chame `validar_modelo` para ter as métricas e dimensões (ids, descrições).
- Leia `design/tokens.json` só para saber o domínio e o estilo; se não existir,
  indique `/bi-html:design` e pare.
- Chame `propor_estilos` para ver os blocos típicos do domínio.
- Se existir `contexto.md`, use a pergunta de negócio e o público dele
  (`origem: "analise"`). Sem análise prévia, use `origem: "planilha_direta"`.

## Passo 2 — Escrever `dashboard/spec.json`

Siga o schema em `${CLAUDE_PLUGIN_ROOT}/schemas/dashboard-spec.schema.json` e o
exemplo `${CLAUDE_PLUGIN_ROOT}/modelo/exemplos/spec-vendas.json`. Regras:

- Textos sem algarismos. Valor no texto só como `{id_da_metrica}`, com a
  métrica no próprio bloco; num bloco com dimensão, o marcador mostra a linha
  líder. Ano, mês e período não vão no texto: o cabeçalho já mostra o período.
- Comece pelo que responde à pergunta de negócio: um `numero_destaque`, depois
  o apoio (`faixa_kpis`), depois os blocos que explicam o número.
- Forma de cada bloco:
  - sem dimensão: `numero_destaque`, `faixa_kpis`, `funil` (duas ou mais
    métricas, uma por etapa);
  - uma dimensão: `linha_tempo` (dimensão de tempo), `barras_ranking`,
    `rosca`, `tabela`, `cascata`, `mapa_uf` (dimensão com siglas de UF);
  - uma ou duas: `barras_agrupadas`;
  - duas: `area_empilhada` (tempo primeiro), `mapa_calor`.
- `comparacao` só em bloco sem dimensão de tempo e com `periodo` diferente de
  `tudo`. Comparação com `meta` ainda não existe.
- `filtros_globais`: até quatro dimensões sem tempo, com poucos valores.
- Use `filtros` no bloco para tirar o que não pertence a ele (por exemplo, um
  centro de distribuição num ranking de lojas).

## Passo 3 — Renderizar

Chame `renderizar_dashboard` (`mcp__plugin_bi-html_bi-dados__renderizar_dashboard`).
Se vier `ok: false`, corrija a spec pelos problemas listados e renderize de
novo. Com `ok: true`, mostre os `avisos` como vieram, o tamanho e o caminho de
`saidas/bi/dashboard.html`, que abre direto no navegador.

## Passo 4 — Publicar (com o ok do usuário)

- Se `publicacao_bloqueada` não estiver vazio, **não publique**: diga os
  motivos e que o caminho é remover ou agregar essas colunas.
- Senão, ofereça publicar como Artifact do claude.ai (privado até o usuário
  compartilhar; apagar o Artifact derruba o link). Com o ok, publique
  `saidas/bi/dashboard.artifact.html` com a ferramenta Artifact, `icon` "chart"
  e uma descrição de uma frase. Nas próximas versões, republique no mesmo
  arquivo para manter o link.
