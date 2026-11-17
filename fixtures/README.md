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
