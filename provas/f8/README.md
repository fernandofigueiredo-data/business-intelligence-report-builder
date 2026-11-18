# F8 — caso real privado

O fluxo completo do bi-html rodou sobre o projeto de eleições presidenciais do autor, sem publicar
nada.

- **Etapas, estados e contagens:** [`RESULTADO.md`](RESULTADO.md)
- **Problemas encontrados (issues do plugin):** [`ISSUES.md`](ISSUES.md)

## Como o caso foi montado

A pasta de origem do projeto **não foi alterada**: o git dela não registra nenhuma alteração antes
nem depois. Foram copiados para `casos/eleicoes/original/`, que o `.gitignore` deste repositório
exclui:

- `data/eleicoes_presidente.csv` (o conjunto principal) e `data/README.md` (o dicionário);
- `powerbi/tema_eleicoes_br.json` (o tema, usado como design system enviado);
- `powerbi/eleicoes-presidenciais-br.pbix` (convertido em `casos/eleicoes-pbix/`).

Os arquivos brutos do TSE (`data/raw/`) ficaram de fora: as consultas de candidatos trazem dados
pessoais deles, e o fluxo não precisa delas.

Os arquivos que o Claude escreveu no papel de autor também ficam só em `casos/eleicoes/`:
- o modelo revisado (`modelo/metricas.yaml`);
- a spec (`dashboard/spec.json`);
- o documento de decisão (`decisao/documento.md`).

Aqui entram só estados e contagens, nenhum valor do caso.

## Como rodar de novo

Com a cópia em `casos/eleicoes/` e os três arquivos de autoria no lugar:

```bash
uv run --no-project --python 3.12 --with duckdb --with openpyxl --with pyyaml --with jsonschema python provas/f8/executar.py
```
