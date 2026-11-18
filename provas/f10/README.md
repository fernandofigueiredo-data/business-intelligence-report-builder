# F10 — assistente do dashboard contra perguntas de resposta conhecida

O assistente (`/bi-html:assistente`, ferramenta `renderizar_assistente`) responde
perguntas dentro do dashboard publicado como Artifact, pela capacidade `sample`,
na conta de quem pergunta.

## Os controles

- **O que o Claude enxerga:** só o cubo do dashboard, por uma ferramenta da
  página (`consultar_bloco`) que devolve os valores já formatados.
- **O verificador:** confere cada número da resposta contra os blocos que o
  Claude consultou para aquela pergunta, arredondado como foi escrito (a mesma
  regra de `numeros.py`). Resposta com número de fora é retida, com o motivo na
  tela. Valer só o que foi consultado, e não o cubo inteiro, pega também os
  números pequenos que algum valor do cubo arredondaria por acaso.
- **Dados não são instrução:** nomes vindos dos dados são dado, e o prompt diz
  isso.
- **As 30 perguntas de controle:**
  - 23 pedem um número, 4 pedem uma categoria e 3 pedem algo que não está no
    dashboard;
  - são tiradas do cubo que a camada de métricas calculou;
  - a página as corrige em JavaScript, e `tests/test_f10.py` confere, com o
    Node, que essa correção dá exatamente o mesmo resultado que a correção em
    Python.

## Resultado

A bateria rodou em 18/11/2026, na conta do autor, no Artifact privado com o exemplo de vendas fictício:

- **30 de 30 corretas**, incluindo as 3 perguntas sem resposta no dashboard, que o assistente recusou sem escrever número;
- **nenhuma resposta com número fora** do que o assistente consultou;
- **as duas correções concordam**: a refeita em Python dá o mesmo resultado que a da página em todas as perguntas.

Detalhes, pergunta a pergunta, em [`RESULTADO.md`](RESULTADO.md).

**Limite que ficou à vista:** o assistente escreveu datas e anos (o período do dashboard) em várias respostas. O verificador não confere ano nem data, só números de valor. Aqui eles vieram do período que a página informa no prompt e estão certos, mas não passaram pela conferência.

## Como rodar de novo

Depois de clicar em "Testar o assistente" no Artifact:

1. ler a coleção `avaliacoes` com a ferramenta ArtifactData (`list`, com `out_dir`);
2. rodar o registro:

```bash
uv run --no-project --python 3.12 --with duckdb --with pyyaml --with jsonschema python provas/f10/registrar.py CAMINHO/avaliacoes/<id>.json
```
