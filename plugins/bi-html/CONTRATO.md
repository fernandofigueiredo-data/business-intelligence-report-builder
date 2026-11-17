# Contrato entre o analise-dados e o bi-html

**Versão:** 0.1 (rascunho da F0; a checagem automática chega na F0b)
**analise-dados mínimo:** 1.1.0

A etapa de BI começa quando a etapa de análise entrega os três arquivos abaixo
na pasta do projeto. Sem eles, o `/bi-html:ciclo` aponta o que falta; o atalho
sem análise usa o perfilamento próprio do bi-html.

| Arquivo | Quem grava | O que o bi-html usa |
|---|---|---|
| `saidas/dados_tratados.parquet` | Notebook da análise (o `/painel` do analise-dados insere a célula se faltar) | Base da camada de métricas; a checagem confere esquema, tipos e nulos |
| `analise.ipynb` com conclusão em markdown no fim | `/analise` do analise-dados | Achados da conclusão viram métricas candidatas; só entram no documento de decisão os que a camada de métricas reproduz |
| `contexto.md` | `/analise` do analise-dados | Pergunta de negócio, público, decisão apoiada, dicionário de colunas e decisões de tratamento, sem perguntar de novo ao usuário |

Opcional: `estilos/design-system.md` (paleta do analise-dados), lido como ponto
de partida do design quando o usuário não envia outro.

Mudanças neste contrato sobem a versão e precisam de teste nos dois repositórios.
