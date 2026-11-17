# Fidelidade da conversão — lab1.pbix

Convertido em 2026-11-17T14:34:23-03:00 pelo bi-html (pbix-mcp 0.9.153, pbixray 0.15.5). Modo do arquivo: importacao. Relatório: PBIR.

## Tabelas

| Tabela | Linhas no .pbix | Linhas extraídas | No modelo convertido | Iguais |
|---|---|---|---|---|
| DateTableTemplate_13ccc290-bdc4-44fb-8b9b-86e0efef36c0 | 1 | 1 | tabela de datas automática | sim |
| LocalDateTable_7aff0774-ff3f-4000-85e6-4744fab2780f | 1461 | 1461 | tabela de datas automática | sim |
| dataset | 51290 | 51290 | 51290 | sim |

## Medidas

| Medida | Classe | Métrica | Equivalência | Motivo ou ressalva |
|---|---|---|---|---|
| Média de Desconto | implicita | media_de_desconto | 3 de 3 contextos |  |
| Soma de Total_Vendas | implicita | soma_de_total_vendas | 3 de 3 contextos |  |
| Contagem de ID_Pedido | implicita | contagem_de_id_pedido | 3 de 3 contextos |  |
| Média de Total_Vendas | implicita | media_de_total_vendas | 3 de 3 contextos |  |

## Páginas e visuais

### Lab1

Spec: `dashboard/paginas/lab_um.json`. 4 de 8 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| Total Vendas Global | card | bloco_a | convertido |  |
| (sem título) | slicer | — | nao_convertido | segmentação de data: no bi-html o tempo é o período da spec |
| (sem título) | slicer | segmento | filtro_global |  |
| Total de Vendas Por País e Prioridade | barChart | bloco_b | convertido |  |
| Média de Desconto Por Subcategoria | clusteredBarChart | bloco_c | convertido |  |
| (sem título) | slicer | — | nao_convertido | segmentação com valores demais para filtro global (o cubo cresceria demais) |
| Média de Vendas Por País | azureMap | — | nao_convertido | o mapa usa dataset.Pais, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| Total de Vendas Por Categoria | pieChart | bloco_d | convertido |  |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

## Semântica

- cada métrica filtra a própria tabela de origem na tabela convertida, então somas de fatos diferentes não se misturam
- filtro numa tabela que não se liga ao fato da métrica esvazia a métrica no bi-html; no Power BI, não filtra
- o filtro de um CALCULATE se soma ao filtro do leitor; no Power BI, substitui o filtro da mesma coluna
- métrica com escala (por exemplo, R$ tri) usa a métrica base; o bi-html formata a grandeza
- medida sem validação no teste de equivalência leva "(não validada)" na descrição
