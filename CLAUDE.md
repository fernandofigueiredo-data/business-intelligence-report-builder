# Repositório do plugin bi-html

Marketplace do Claude Code com o plugin `plugins/bi-html/`, os dados fictícios
em `fixtures/` e o plano em `PLANO_DE_CONSTRUCAO.md` (fases, critérios de
aceite e decisões).

- Regra central: nenhum número sai do modelo; tudo vem do servidor MCP
  `bi-dados` (`plugins/bi-html/mcp/servidor.py`). As regras para quem usa o
  plugin estão em `plugins/bi-html/REGRAS.md`.
- A etapa de análise é o plugin `analise-dados`; o contrato entre os dois está
  em `plugins/bi-html/CONTRATO.md`.
- Lógica em `plugins/bi-html/lib/bi_html/` (Python 3.12). Servidor e scripts
  importam dela; não duplique regra em dois lugares.
- Caminhos do plugin em comandos e skills: `${CLAUDE_PLUGIN_ROOT}`.
- Textos para o usuário, nomes e comentários em português do Brasil.
- Antes de concluir uma mudança:
  `uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v`
  e `claude plugin validate --strict plugins/bi-html`.
- Os dados de `fixtures/` são gerados por `fixtures/gerar.py`; não edite os
  arquivos à mão.
- `provas/f6/` é a prova de conceito com .pbix: roda fora do servidor (o
  `pbix-mcp` exige `mcp<2`). `MATRIZ.md`, `resultados.json` e `saidas/` são
  gerados por `provas/f6/executar.py`; não edite à mão.
- A leitura de .pbix do plugin fica em `plugins/bi-html/scripts/pbix_externo.py`,
  chamado em processo à parte por `conversao.py` (via `uv`). `provas/f7/` é
  gerado por `provas/f7/executar.py`. Os .pbix fictícios (`fixtures/vendas.pbix`
  e `vendas_directquery.pbix`) são gerados por `fixtures/gerar_pbix.py`.
