# F7b — teste do iframe do Power BI

Gerado por `provas/f7b/executar.py` a partir de `resultados.json`; não edite à mão.

**Execução:** 2026-11-17T17:01:36-03:00. Identificadores fictícios: nenhum dado do usuário vai na requisição.

## Cabeçalhos do serviço do Power BI

| Endereço | Para quê | HTTP | X-Frame-Options | frame-ancestors | Pode ir num iframe |
|---|---|---|---|---|---|
| `app.powerbi.com/view` | link de Publicar na Web (licença Free serve) | 200 | — | — | sim |
| `app.powerbi.com/reportEmbed` | link de incorporação segura (leitor com login e licença Pro ou PPU) | 200 | — | — | sim |
| `app.powerbi.com/home` | página comum do serviço (controle) | 200 | deny | frame-ancestors https://teams.powerbi.com 'self' https://res-sdf.cdn.o… | não |

## No navegador

A página comparativo/index.html servida em localhost, com o link de Publicar na Web (token fictício): o leitor do Power BI carregou no quadro, com o rodapé e os controles, e o console não registrou erro de incorporação (2026-11-17).

## No Artifact do claude.ai

O contrato de página dos Artifacts do claude.ai diz que outros sites não podem ser incorporados (sem iframes de YouTube, mapas ou formulários, e sem `<object>` ou `<embed>`) e que a recusa vale para qualquer leitor; o caminho é linkar para fora. Por isso a página de comparação não é publicada como Artifact: ela é uma pasta estática (`saidas/bi/comparativo/`) para hospedar em qualquer lugar, e o dashboard convertido continua publicável como Artifact.
