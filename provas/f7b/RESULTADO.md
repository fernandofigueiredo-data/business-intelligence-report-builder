# F7b — teste do iframe do Power BI

Gerado por `provas/f7b/executar.py` a partir de `resultados.json`; não edite à mão.

**Execução:** 2026-11-18T09:03:45-03:00. Os três primeiros endereços usam identificadores fictícios; o último é o link público do relatório fictício publicado. Nenhum dado do usuário vai nas requisições.

## Cabeçalhos do serviço do Power BI

| Endereço | Para quê | HTTP | X-Frame-Options | frame-ancestors | Pode ir num iframe |
|---|---|---|---|---|---|
| `app.powerbi.com/view` | link de Publicar na Web (licença Free serve) | 200 | — | — | sim |
| `app.powerbi.com/reportEmbed` | link de incorporação segura (leitor com login e licença Pro ou PPU) | 200 | — | — | sim |
| `app.powerbi.com/home` | página comum do serviço (controle) | 200 | deny | frame-ancestors https://teams.powerbi.com 'self' https://res-sdf.cdn.o… | não |
| `app.powerbi.com/view` | relatório fictício publicado com Publicar na Web (vendas.pbix, conta Free) | 200 | — | — | sim |

## No navegador

A página comparativo/index.html servida em localhost, com o link de Publicar na Web (token fictício): o leitor do Power BI carregou no quadro, com o rodapé e os controles, e o console não registrou erro de incorporação (2026-11-17).

## O relatório publicado (critério de aceite da F7b)

Caminho escolhido pela licença (free): Publicar na Web. Link: <https://app.powerbi.com/view?r=eyJrIjoiYTQ4Y2E5ODctZDMwOC00MWFlLWJlZGItMDZhZTM2YWRlZTU5IiwidCI6IjI2MGZmOWM5LTM4OGYtNDdiYi04NjlhLTc3YTk1N2JmNzA4MiJ9>.

A página de comparação da vitrine (docs/power-bi/), servida em localhost com o link publicado: o relatório do Power BI carregou inteiro no quadro (cartões de faturamento, pedidos e ticket médio, gráficos e o filtro de região), com os mesmos valores que o lado convertido mostra, e o console não registrou erro (2026-11-18). A página de comparação mora na vitrine estática (`docs/power-bi/`), não no Artifact.

## No Artifact do claude.ai

O contrato de página dos Artifacts do claude.ai diz que outros sites não podem ser incorporados (sem iframes de YouTube, mapas ou formulários, e sem `<object>` ou `<embed>`) e que a recusa vale para qualquer leitor; o caminho é linkar para fora. Por isso a página de comparação não é publicada como Artifact: ela é uma pasta estática (`saidas/bi/comparativo/`) para hospedar em qualquer lugar, e o dashboard convertido continua publicável como Artifact.
