---
description: Escreve o documento de decisão — achados calculados, conclusão da análise reproduzida, texto verificado número a número e HTML em até duas páginas A4
argument-hint: "(sem argumentos)"
---

Você vai escrever o documento de decisão. Antes de tudo, leia as regras em
`${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e siga-as. A regra 7 manda aqui: você redige,
mas todo número vem de um achado calculado ou de um item reproduzido da
conclusão da análise.

## Passo 1 — Achados

Chame `gerar_achados` (`mcp__plugin_bi-html_bi-dados__gerar_achados`). Leia a
lista: cada achado tem `id`, `titulo`, `valores` e `formatado` (os textos que
você pode citar). Escolha de três a cinco que respondam à pergunta de negócio.

## Passo 2 — Reproduzir a conclusão da análise (se o projeto passou pelo `/analise`)

Se existir `analise.ipynb`, escreva `decisao/verificacoes.yaml` com uma
verificação para cada número da conclusão do notebook. O formato e os três
tipos de verificação (`onde`, `variacao`, `todas_as_linhas`) estão no topo de
`${CLAUDE_PLUGIN_ROOT}/lib/bi_html/conclusao.py`. Escreva `numero` exatamente
como está no item e use a afirmação que o texto faz (`aproximado` para "cerca
de", `mais_de`, `menos_de`, `igual`). Chame `reproduzir_conclusao`.

Mostre ao usuário o estado de cada item. Item `nao_reproduzido` não entra no
documento: diga qual número divergiu e quanto a camada de métricas calculou.
Não ajuste a verificação para "fazer passar" um número que não confere.

## Passo 3 — Escrever `decisao/documento.md`

Formato (o verificador confere):

    # Título curto (o nome do documento)
    **Pergunta:** a pergunta de negócio do contexto.md
    **Decisão:** a decisão que o documento apoia (do contexto.md)

    ## Resposta
    No máximo duas frases.

    ## Achados
    ### Frase que diz o achado [A6] [C1]
    Um parágrafo curto com os números do achado.
    (de três a cinco achados)

    ## O que os dados não permitem afirmar
    ## Opções de decisão
    ## Próximas perguntas

Regras de escrita:
- Copie os números de `formatado` ou arredonde para menos casas
  (R$ 25.016.139,62 → R$ 25,0 milhões); nada de número calculado por você.
  Anos e datas só do período dos dados.
- Associação não é causa; concentração não é risco por si só; um ano só não
  separa sazonalidade de crescimento. Diga isso na seção de limites.
- Participação vem com o n: cite a contagem do achado de liderança junto do
  percentual. "A maior parte" só para mais da metade.
- A opção de decisão não pode contradizer os limites: se o documento não sabe
  a causa ou o custo, a opção diz o que precisa ser verdade para ela valer.
- Cada opção de decisão traz o a favor, o contra e o que monitorar.
- Português de negócio, sem jargão. Duas páginas A4 no máximo.

## Passo 4 — Verificar e renderizar

Chame `verificar_documento`. Se `ok` for falso, corrija cada problema da lista
(o número sem origem, a seção faltando) e verifique de novo. Com 100% dos
números rastreados, chame `renderizar_documento`.

Se o plugin analise-dados estiver instalado, peça ao subagente `revisor` dele
uma leitura de `decisao/documento.md` com `saidas/bi/achados.json` e
`saidas/bi/reproducao.json` ao lado, procurando conclusão sem sustentação.
Corrija o que ele apontar e renderize de novo.

## Passo 5 — Entregar

Mostre o caminho de `saidas/bi/decisao.html` e o resumo da verificação. Com o
ok do usuário, e se a publicação não estiver bloqueada por dados pessoais,
publique `saidas/bi/decisao.artifact.html` como Artifact (`icon` "document").
