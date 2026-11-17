# F7 — conversão de .pbix com arquivos reais

Gerado por `provas/f7/executar.py` a partir de `resultados.json`; não edite à mão.

**Execução:** 2026-11-17T14:34:10-03:00 · Python 3.12.14 · arm64 Darwin

## Critérios de aceite

| Arquivo | Linhas idênticas por tabela | Medidas classificadas | Traduzidas que batem com o Power BI | Contextos testados que batem | Visuais no relatório de fidelidade |
|---|---|---|---|---|---|
| `ifdata` | 2 de 2 | 19 de 19 | 13 de 13 | 62 de 62 | 18 de 18 |
| `eleicoes` | 7 de 7 | 55 de 55 | 17 de 17 | 85 de 85 | 87 de 87 |
| `lab1` | 3 de 3 | 0 de 0 | 0 de 0 | 12 de 12 | 10 de 10 |
| `vendas_ficticio` | 2 de 2 | 14 de 14 | 10 de 11 | 54 de 55 | 11 de 11 |
| `directquery_ficticio` | recusado: a conversão só vale para importação; o arquivo está em DirectQuery: os dados ficam no banco de origem, não no .pbix | — | — | — | — |

## Medidas e visuais

| Arquivo | Traduzidas | Texto | Não traduzidas | Agregações implícitas (validadas) | Visuais por status | Páginas com spec | Relatório | Tema |
|---|---|---|---|---|---|---|---|---|
| `ifdata` | 13 | 2 | 4 | 0 (0) | convertido: 5, decorativo: 4, filtro_global: 4, nao_convertido: 2, parcial: 3 | 2 de 2 | PBIR | importado |
| `eleicoes` | 17 | 9 | 29 | 0 (0) | convertido: 7, decorativo: 37, filtro_global: 8, nao_convertido: 30, parcial: 5 | 4 de 8 | PBIR | importado |
| `lab1` | 0 | 0 | 0 | 4 (4) | convertido: 4, decorativo: 2, filtro_global: 1, nao_convertido: 3 | 1 de 1 | PBIR | importado |
| `vendas_ficticio` | 11 | 1 | 2 | 1 (1) | convertido: 8, decorativo: 1, filtro_global: 1, nao_convertido: 1 | 1 de 1 | legado (Report/Layout) | importado |

**Traduzidas que não bateram** (levam "(não validada)" no modelo; o motivo está no fidelidade.md): `vendas_ficticio` Receita Site.

## Arquivos, tempo e memória

Tempo e pico de memória da conversão inteira (extração, tradução, teste de equivalência e renderização), incluindo os processos de leitura do .pbix.

| Arquivo | Nome | Tamanho | SHA-256 (12) | Tempo (s) | Pico (MB) | Saída |
|---|---|---|---|---|---|---|
| `ifdata` | ifdata.pbix | 0,3 MB | `2823516303e5` | 3,6 | 144 | [conversao.json](saidas/ifdata/conversao.json) · [fidelidade.md](saidas/ifdata/fidelidade.md) |
| `eleicoes` | eleicoes.pbix | 3,1 MB | `8faccd122a5e` | 7,1 | 461 | [conversao.json](saidas/eleicoes/conversao.json) · [fidelidade.md](saidas/eleicoes/fidelidade.md) |
| `lab1` | lab1.pbix | 1,8 MB | `712d47c3b0f7` | 1,5 | 179 | [conversao.json](saidas/lab1/conversao.json) · [fidelidade.md](saidas/lab1/fidelidade.md) |
| `vendas_ficticio` | vendas.pbix | 0,4 MB | `f8ed43229fb5` | 3,2 | 146 | [conversao.json](saidas/vendas_ficticio/conversao.json) · [fidelidade.md](saidas/vendas_ficticio/fidelidade.md) |
| `directquery_ficticio` | vendas_directquery.pbix | 0,3 MB | `d9d311abce6f` | 0,8 | 116 | — |
