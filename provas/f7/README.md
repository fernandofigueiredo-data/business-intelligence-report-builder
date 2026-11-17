# F7 — conversão de .pbix com arquivos reais

A F7 implementa o Fluxo 2, via (a): um .pbix em modo de importação vira projeto
do bi-html (`/bi-html:pbix`, ferramenta `converter_pbix`). Aqui a conversão
roda com os seus três arquivos e com os dois .pbix fictícios de
`fixtures/`.

- **Critérios de aceite, medidas, visuais, tempo e memória:** [`RESULTADO.md`](RESULTADO.md)
- **Relatório de cada conversão:** `saidas/<arquivo>/conversao.json` e `fidelidade.md`

## Como rodar

```bash
uv run --no-project --python 3.12 --with duckdb --with pyyaml --with jsonschema python -I provas/f7/executar.py --arquivo ifdata=/caminho/M5_Dashboard_IFdata.pbix --arquivo eleicoes=/caminho/eleicoes-presidenciais-br.pbix --arquivo lab1=/caminho/Lab1_reorganizado.pbix --arquivo vendas_ficticio=fixtures/vendas.pbix --arquivo directquery_ficticio=fixtures/vendas_directquery.pbix
```

Cada conversão roda numa pasta temporária: tabelas, modelo e páginas
renderizadas não entram no repositório. Os arquivos reais foram copiados antes
da execução, porque dois deles mudaram durante a sessão: o de eleições e o Lab1
testados aqui são versões mais novas que as da F6 (os hashes estão em
`RESULTADO.md`).

## Como a conversão funciona

1. **Extração** num processo à parte (`plugins/bi-html/scripts/pbix_externo.py`,
   com pbix-mcp e pbixray): modo de armazenamento, tabelas em parquet com a
   contagem conferida e o modelo. DirectQuery, modo misto e conexão dinâmica
   são recusados com a explicação e a via (b).
2. **Relatório** lido direto do pacote, em PBIR ou no layout legado: páginas,
   visuais, campos, títulos, ordenação e o tema em uso.
3. **Tabela convertida:** o modelo do bi-html tem uma fonte só, então cada
   tabela agregada pelas medidas (os fatos) entra com as colunas das tabelas
   ligadas a ela pelas relações, e as partes são empilhadas com a coluna
   `tabela_de_origem`. Cada métrica filtra a própria parte.
4. **Medidas** (`plugins/bi-html/lib/bi_html/dax.py`): um analisador do DAX
   classifica cada medida como traduzida, texto ou não traduzida (com o
   motivo). As traduzidas viram métricas: soma, média, mínimo, máximo,
   contagens, razão, participação, filtros de `CALCULATE`, iteradores com
   coluna calculada e escala.
5. **Equivalência:** cada medida traduzida é avaliada no motor DAX do pbix-mcp
   (a referência) e na camada de métricas, no total e em contextos com filtro
   (o valor mais frequente de até três dimensões do relatório, sozinhas e em
   par). As agregações implícitas dos visuais, que o pbix-mcp não avalia, são
   conferidas contra SQL sobre a tabela original. Quem não bate leva "(não
   validada)" na descrição.
6. **Specs e fidelidade:** uma spec por página, visual a visual, e o relatório
   de fidelidade com o status e os motivos de cada visual.

## O que a F7 mostrou

1. **Os quatro critérios fecham nos três arquivos reais.** São 12 tabelas com
   linhas idênticas e 74 medidas classificadas. As 30 traduzidas batem com o
   Power BI em 147 contextos, e as 4 agregações implícitas do Lab1, em 12. Os
   115 visuais estão no relatório de fidelidade, cada um com status e motivo.
2. **O teste de equivalência pega divergência real.** No .pbix fictício,
   `Receita Site = CALCULATE([Faturamento], Vendas[canal] = "Site")` não bate
   quando o leitor filtra outro canal. No Power BI, o filtro do `CALCULATE`
   substitui o do leitor; na camada de métricas, os dois se somam. A medida
   fica com o selo "não validada", como manda a regra 8.
3. **O que não traduz é lógica de contexto.** No arquivo de eleições, 29 das
   55 medidas usam `REMOVEFILTERS`, `SELECTEDVALUE`, `TOPN`, `RANKX` ou
   comparação com a eleição anterior, e outras 9 devolvem texto (vencedor,
   cores, títulos). Por isso só 4 das 8 páginas viram spec: três das outras
   dependem dessas medidas, e a quarta é uma página de dica (tooltip).
4. **Os mapas são o maior buraco de visual.** Os mapas do Azure usam nome de
   município ou de estado, e o bi-html só desenha o mapa por sigla de UF.
   Depois deles vêm a dispersão, que não tem bloco, e os filtros de visual, que
   não são convertidos.
5. **A conversão é rápida.** Leva de 1,5 a 7 segundos por arquivo, com pico
   de até cerca de 460 MB, porque as medidas pesadas não passam pelo avaliador.

## O que ficou de fora

- **Pré-cálculo das medidas complexas** (a segunda metade do híbrido da seção
  5.2 do plano): a F6 mediu de 11 a 16 s por medida pesada no avaliador do
  pbix-mcp, e a spec não tem onde guardar uma grade pré-calculada. Medida não
  traduzida fica fora do dashboard, com o motivo no relatório de fidelidade.
- **Filtros de visual** e o **tema base do Power BI**: o tema base não vem
  dentro do .pbix, então nesse caso a conversão usa o estilo claro do bi-html.
- **DirectQuery e conexão dinâmica:** só a recusa foi testada, com um .pbix
  fictício em DirectQuery.
