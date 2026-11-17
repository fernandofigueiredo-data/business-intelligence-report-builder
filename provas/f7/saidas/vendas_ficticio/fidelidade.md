# Fidelidade da conversão — vendas.pbix

Convertido em 2026-11-17T14:34:26-03:00 pelo bi-html (pbix-mcp 0.9.153, pbixray 0.15.5). Modo do arquivo: importacao. Relatório: legado (Report/Layout).

## Tabelas

| Tabela | Linhas no .pbix | Linhas extraídas | No modelo convertido | Iguais |
|---|---|---|---|---|
| Lojas | 15 | 15 | dimensão dos fatos | sim |
| Vendas | 16254 | 16254 | 16254 | sim |

## Medidas

| Medida | Classe | Métrica | Equivalência | Motivo ou ressalva |
|---|---|---|---|---|
| Faturamento | traduzida | faturamento | 5 de 5 contextos |  |
| Pedidos | traduzida | pedidos | 5 de 5 contextos | DISTINCTCOUNT conta o vazio como um valor; a contagem distinta do bi-html, não |
| Itens | traduzida | itens | 5 de 5 contextos |  |
| Ticket Médio | traduzida | ticket_medio | 5 de 5 contextos | DISTINCTCOUNT conta o vazio como um valor; a contagem distinta do bi-html, não |
| Receita Site | traduzida | receita_site | 4 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Receita Sudeste | traduzida | receita_sudeste | 5 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Receita Bruta | traduzida | receita_bruta | 5 de 5 contextos |  |
| Desconto Médio | traduzida | desconto_medio | 5 de 5 contextos |  |
| Pedidos com Desconto | traduzida | pedidos_com_desconto | 5 de 5 contextos | DISTINCTCOUNT conta o vazio como um valor; a contagem distinta do bi-html, não; o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Participação da UF | traduzida | participacao_da_uf | 2 de 2 contextos | participação: equivale quando o bloco agrupa pela coluna do ALLSELECTED |
| Receita (R$ mil) | traduzida | faturamento | 5 de 5 contextos |  |
| Receita de Todas as Lojas | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |
| Receita Acumulada no Ano | nao_traduzida | — | — | usa TOTALYTD, sem equivalente na camada de métricas |
| Rótulo da Receita | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Média de desconto_pct | implicita | media_de_desconto_pct | 3 de 3 contextos |  |

## Páginas e visuais

### Visão geral

Spec: `dashboard/paginas/visao_geral.json`. 8 de 10 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| Faturamento | card | bloco_a | convertido |  |
| Pedidos | card | bloco_b | convertido |  |
| Ticket médio | card | bloco_c | convertido |  |
| (sem título) | slicer | regiao | filtro_global |  |
| Receita por loja | clusteredBarChart | bloco_d | convertido |  |
| Receita por canal | donutChart | bloco_e | convertido |  |
| Receita por UF | filledMap | bloco_f | convertido |  |
| Categorias | tableEx | bloco_g | convertido |  |
| Participação por UF | clusteredColumnChart | bloco_h | convertido |  |
| Receita acumulada | lineChart | — | nao_convertido | [Receita Acumulada no Ano] não traduzida: usa TOTALYTD, sem equivalente na camada de métricas |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

## Semântica

- cada métrica filtra a própria tabela de origem na tabela convertida, então somas de fatos diferentes não se misturam
- filtro numa tabela que não se liga ao fato da métrica esvazia a métrica no bi-html; no Power BI, não filtra
- o filtro de um CALCULATE se soma ao filtro do leitor; no Power BI, substitui o filtro da mesma coluna
- métrica com escala (por exemplo, R$ tri) usa a métrica base; o bi-html formata a grandeza
- medida sem validação no teste de equivalência leva "(não validada)" na descrição
