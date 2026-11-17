---
description: Publica o dashboard com um assistente de perguntas em que cada número da resposta é conferido contra o dashboard
argument-hint: "(sem argumentos)"
---

Você vai publicar o dashboard com o painel "Pergunte ao dashboard" (fase F10 do
plano). Antes de tudo, leia as regras em `${CLAUDE_PLUGIN_ROOT}/REGRAS.md` e
siga-as. Esta é a única parte do sistema em que o Claude lê números fora da
camada de métricas, por isso a página tem controles próprios: o assistente só
enxerga o cubo do dashboard, e uma resposta com número que ele não consultou é
retida.

## Passo 1 — Pré-requisitos

O dashboard precisa estar renderizado (`/bi-html:dashboard`). Diga ao usuário
que cada pergunta gasta o uso de Claude **de quem pergunta**, que a página pede
autorização na primeira pergunta e que o assistente só funciona dentro do
claude.ai (no arquivo local o painel fica escondido).

## Passo 2 — Gerar

Chame `renderizar_assistente` (`mcp__plugin_bi-html_bi-dados__renderizar_assistente`).
Se `publicacao_bloqueada` não estiver vazio, **não publique** (regra 5).

## Passo 3 — Publicar (com o ok do usuário)

Publique `saidas/bi/assistente.artifact.html` com a ferramenta Artifact,
`icon` "chart", passando em `capabilities` exatamente o objeto que veio em
`capacidades` (o assistente usa `sample`; o teste grava em `db`, com escrita
só para quem edita). Nas próximas versões, republique no mesmo arquivo.

## Passo 4 — Teste com perguntas de resposta conhecida

A página traz perguntas de controle com a resposta calculada pela camada de
métricas. Quem edita a página vê o botão "Testar o assistente". Peça ao
usuário para clicar nele (leva alguns minutos e gasta o uso dele). Depois:

1. Leia a coleção `avaliacoes` do Artifact (`ArtifactData`, `list`).
2. Mostre acertos e respostas com número fora do dashboard **como vieram** do
   registro. O critério da fase é de pelo menos 90% de acertos e nenhuma
   resposta com número fora do cubo.
3. Se houver erro, mostre a pergunta, a resposta e o motivo. Não reescreva a
   resposta do assistente.
