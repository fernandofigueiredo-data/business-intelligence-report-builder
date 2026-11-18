---
type: llm
weight: 2
---

Em `dados/votacao.csv`, cada linha é um candidato numa zona, e `zona_aptos` repete o eleitorado da
zona em cada linha de candidato. O total certo de eleitores aptos soma cada zona uma vez:
12.000 + 9.500 + 15.300 + 8.100 = 44.900. Somar a coluna inteira dá o triplo (134.700).

PASS se a resposta final apontar que `zona_aptos` se repete por candidato e não pode ser somada
linha a linha, e não apresentar 134.700 como total de eleitores aptos.

FAIL se a resposta apresentar 134.700 (ou outra soma inflada) como total de eleitores aptos, ou
propuser somar `zona_aptos` diretamente sem alertar para a repetição.
