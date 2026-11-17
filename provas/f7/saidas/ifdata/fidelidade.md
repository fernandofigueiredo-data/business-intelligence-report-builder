# Fidelidade da conversão — ifdata.pbix

Convertido em 2026-11-17T14:34:14-03:00 pelo bi-html (pbix-mcp 0.9.153, pbixray 0.15.5). Modo do arquivo: importacao. Relatório: PBIR.

## Tabelas

| Tabela | Linhas no .pbix | Linhas extraídas | No modelo convertido | Iguais |
|---|---|---|---|---|
| Medidas | 0 | 0 | fora (nenhuma medida a usa) | sim |
| ifdata | 1622 | 1622 | 1622 | sim |

## Medidas

| Medida | Classe | Métrica | Equivalência | Motivo ou ressalva |
|---|---|---|---|---|
| Ativo Total | traduzida | ativo_total | 5 de 5 contextos |  |
| Ativo Total (R$ tri) | traduzida | ativo_total | 5 de 5 contextos |  |
| Ativo Total (R$ bi) | traduzida | ativo_total | 5 de 5 contextos |  |
| Carteira de Crédito | traduzida | carteira_de_credito | 5 de 5 contextos |  |
| Patrimônio Líquido | traduzida | patrimonio_liquido | 5 de 5 contextos |  |
| Lucro Líquido | traduzida | lucro_liquido | 5 de 5 contextos |  |
| Qtd Instituições | traduzida | qtd_instituicoes | 5 de 5 contextos |  |
| ROE Agregado | traduzida | roe_agregado | 5 de 5 contextos |  |
| ROE Médio Simples | traduzida | roe_medio_simples | 5 de 5 contextos |  |
| Índice Crédito/Ativo | traduzida | indice_credito_ativo | 5 de 5 contextos |  |
| Qtd sem Agência | traduzida | qtd_sem_agencia | 5 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Qtd Digitais | traduzida | qtd_digitais | 5 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Ativo % do Total | traduzida | ativo_pct_do_total | 2 de 2 contextos | participação: equivale quando o bloco agrupa pela coluna do ALLSELECTED |
| Rank Ativo | nao_traduzida | — | — | usa RANKX, sem equivalente na camada de métricas |
| Cor Barra Top 10 | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Concentração Top 5 | nao_traduzida | — | — | usa TOPN, sem equivalente na camada de métricas |
| Qtd Instituições (txt) | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| ROE Sistema | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |
| Índice Sistema | nao_traduzida | — | — | CALCULATE com ALLSELECTED (remove filtros do leitor) fora do padrão de participação |

## Páginas e visuais

### Dados do Sistema Financeiro Brasileiro

Spec: `dashboard/paginas/dados_do_sistema_financeiro_brasileiro.json`. 7 de 10 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| Cinco instituições concentram 52% do ativo do sistema financeiro brasileiro | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | segmento | filtro_global |  |
| 52% do ativo em 5 instituições | cardVisual | bloco_a | convertido |  |
| Dois terços têm menos de R$ 1 bi | cardVisual | — | nao_convertido | [Qtd Instituições (txt)] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| A média simples (0,8%) engana | cardVisual | bloco_b | convertido |  |
| São cooperativas, não digitais | cardVisual | bloco_c | convertido |  |
| Pesam só 5% do ativo | cardVisual | bloco_d | convertido |  |
| As dez maiores somam 67% do ativo; o Banco do Brasil sozinho, 13% | barChart | bloco_e | parcial | 1 filtro(s) do visual não foram convertidos |
| Privadas nacionais detêm metade do ativo; as públicas, um terço | donutChart | bloco_f | convertido |  |
| (sem título) | slicer | uf | filtro_global |  |
| Mais de mil instituições somam apenas 1% do ativo | tableEx | bloco_g | parcial | o bloco usa uma dimensão; ficaram de fora 3 |
| Valores originais em R$ mil (junho/2026); exibidos em R$ bi e R$ tri. Segmento aproximado por ativo ÷ PIB (R$ 13 tri). Digitais*: TCB n1, n2 e n4 com até 1 agência. Instituições individuais: pode haver sobreposição entre holding e controladas. | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

### Rentabilidade e crédito

Spec: `dashboard/paginas/rentabilidade_e_credito.json`. 1 de 4 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| Rentabilidade e crédito: o segmento S2 rende mais e o porte não define o crédito | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | segmento | filtro_global |  |
| S2 é o segmento mais rentável (8,8%); S4 e S5 rendem 3 pontos a menos | columnChart | bloco_a | parcial | 1 filtro(s) do visual não foram convertidos |
| O porte não define o crédito: grandes e pequenas emprestam 37% a 39% do ativo | scatterChart | — | nao_convertido | dispersão não tem bloco equivalente no bi-html |
| (sem título) | slicer | uf | filtro_global |  |
|   Valores em R$ mil, junho/2026. Segmento aproximado por ativo ÷ PIB (R$ 13 tri). Digitais*: TCB n1, n2 e n4 com até 1 agência. Instituições individuais: pode haver sobreposição entre holding e controladas. | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

## Semântica

- cada métrica filtra a própria tabela de origem na tabela convertida, então somas de fatos diferentes não se misturam
- filtro numa tabela que não se liga ao fato da métrica esvazia a métrica no bi-html; no Power BI, não filtra
- o filtro de um CALCULATE se soma ao filtro do leitor; no Power BI, substitui o filtro da mesma coluna
- métrica com escala (por exemplo, R$ tri) usa a métrica base; o bi-html formata a grandeza
- medida sem validação no teste de equivalência leva "(não validada)" na descrição
