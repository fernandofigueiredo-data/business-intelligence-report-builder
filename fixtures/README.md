# Conjuntos de dados fictícios

Tudo aqui é inventado: lojas, campanhas, contas, pessoas, CPFs, e-mails e
telefones não correspondem a ninguém. Os arquivos são gerados por `gerar.py`
com semente fixa, então rodar de novo produz exatamente os mesmos bytes:

    uv run --no-project --python 3.12 --with openpyxl fixtures/gerar.py

| Arquivo | Domínio | Linhas | O que exercita |
|---|---|---|---|
| `vendas.csv` | Vendas | 16.254 | Separador `;`, vírgula decimal, datas `dd/mm/aaaa`, região ausente em ~1% dos pedidos, pico em novembro e dezembro |
| `marketing.xlsx` | Marketing | 3.285 | Excel com datas nativas e aba `dicionario`; métricas de mídia (impressões, cliques, investimento, conversões) |
| `financeiro.csv` | Financeiro | 624 | Separador `,`, ponto decimal, competência `aaaa-mm`, DRE com realizado e orçado de 2024 e 2025 |
| `clientes_ficticios.csv` | — | 200 | CPF, e-mail e telefone fictícios: o perfil precisa sinalizar dados pessoais e a publicação precisa ser bloqueada |
| `malformado.csv` | — | 5 | Linhas com número de colunas diferente, valor com letra e um trecho em latin-1: a ingestão precisa devolver erro legível |

Os três primeiros cobrem os domínios que a inferência de design reconhece
(seção 7 do plano). Os dois últimos são casos de teste da fase F1.

## Relatórios do Power BI (`*.pbix`)

Usados nos testes da fase F7 (conversão de .pbix). Gerados a partir de
`vendas.csv` pelo construtor do pbix-mcp (os bytes mudam a cada geração):

    uv run --no-project --python 3.12 --with pbix-mcp==0.9.153 python -I fixtures/gerar_pbix.py

| Arquivo | O que exercita |
|---|---|
| `vendas.pbix` | Importação; fato `Vendas` e dimensão `Lojas` ligadas por relação; medidas de cada padrão traduzível e três que não traduzem (`REMOVEFILTERS`, `TOTALYTD`, `FORMAT`); uma medida com `CALCULATE` cujo filtro diverge do Power BI quando o leitor filtra a mesma coluna; página no layout legado com cartões, barras, rosca, tabela, mapa por UF, linha e segmentação |
| `vendas_directquery.pbix` | DirectQuery: a conversão precisa recusar com a explicação e a via (b) |

## Design systems de exemplo (`design/`)

Usados nos testes da fase F3. Também são fictícios.

| Arquivo | Formato | O que exercita |
|---|---|---|
| `design/DESIGN.md` | DESIGN.md (formato aberto do Google Labs, versão alpha) | Mapeamento de nomes (`surface`, `on-surface`, `outline`, `error`), uma cor em `oklch()`, tipografia e cantos; um cinza claro demais para texto, que o validador precisa ajustar |
| `design/tema_powerbi.json` | Tema JSON do Power BI | `dataColors`, `tableAccent`, `good`/`bad`; texto rosa-claro sobre branco, abaixo do AA, que precisa ser ajustado |
| `design/tokens.css` | Variáveis CSS no padrão shadcn/ui, em `oklch()` | Leitura de CSS e conversão de oklch para hex |
