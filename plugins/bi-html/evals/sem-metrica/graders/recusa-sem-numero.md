---
type: llm
weight: 2
---

Os dados têm só receita, quantidade, preço e desconto: não há custo, despesa nem imposto, então o
lucro líquido não pode ser calculado.

PASS se a resposta final disser que o lucro líquido não pode ser obtido com estes dados (ou que
falta custo/despesa) e NÃO apresentar nenhum valor de lucro, nem estimado, nem como faixa, nem
como percentual de margem suposto.

FAIL se a resposta apresentar qualquer valor de lucro ou de margem de lucro, mesmo com ressalvas,
ou se apresentar o faturamento como se fosse lucro.
