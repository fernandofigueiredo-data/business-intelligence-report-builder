---
description: Põe o relatório original do Power BI ao lado da versão convertida (via (b)), numa página estática para hospedar
argument-hint: "[link do Power BI] [free|pro|ppu]"
---

Você vai montar a comparação entre o relatório original no Power BI e a página
convertida pelo bi-html (Fluxo 2, via (b) do plano). Antes de tudo, leia as
regras em `${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as.

Argumentos: `$ARGUMENTS` (o link e a licença, nessa ordem; ambos opcionais).

## Passo 1 — Pré-requisito

A conversão precisa existir (`saidas/bi/pbix/conversao.json`). Se não existir,
indique `/bi-html:pbix` e pare.

## Passo 2 — O caminho certo para a licença

Pergunte a licença se ela não veio nos argumentos e não está em
`saidas/bi/manifesto.json` (`incorporacao.licenca`):

- **Free:** o único caminho é "Publicar na Web". O administrador do tenant
  precisa habilitar a opção. O link fica público: qualquer pessoa com ele vê
  os dados, sem login. Só use com dados fictícios ou públicos. Se o relatório
  tiver dados reais de pessoas ou de clientes, **não** recomende publicar.
- **Pro ou PPU:** além de "Publicar na Web", há a incorporação segura (o
  leitor entra com a conta Microsoft e precisa de licença).

Sem link ainda, explique os passos que a página mostra (enviar o .pbix ao
serviço, Arquivo > Inserir relatório > Publicar na Web, copiar o link). Você
não publica nada no Power BI: quem publica é o usuário, na conta dele.

## Passo 3 — Montar

Chame `montar_comparativo` (`mcp__plugin_bi-html_bi-dados__montar_comparativo`)
com `link_power_bi`, `licenca` e, se o usuário pedir, `pagina`. Com `ok: false`,
mostre o erro e os detalhes como vieram. Com `ok: true`, mostre os `avisos`
como vieram e o caminho de `saidas/bi/comparativo/index.html`.

## Passo 4 — Onde a página mora

- A pasta `saidas/bi/comparativo/` é estática: abre direto do disco e pode ser
  hospedada em qualquer lugar (GitHub Pages, a vitrine da fase F9).
- **Não publique a comparação como Artifact.** O Artifact do claude.ai não
  carrega iframes de outros sites, então o original ficaria em branco (o teste
  está em `provas/f7b/RESULTADO.md` do repositório do plugin). O dashboard
  convertido, sozinho, continua publicável como Artifact pelo `/bi-html:pbix`.
