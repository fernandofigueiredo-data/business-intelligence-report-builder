#!/usr/bin/env bash
# Monta, no espaço de trabalho vazio da execução, o projeto de vendas fictício pronto:
# dados ingeridos, perfil, modelo de métricas validado, estilo e dashboard renderizado.
# Usa o mesmo construir() de exemplos/construir.py, a partir dos arquivos do repositório.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
# O HOME da execução é temporário; um cache fixo evita baixar as dependências a cada execução.
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/bi-html-evals-uv-cache}"
mkdir -p modelo dashboard
cp "$RAIZ/exemplos/vendas/modelo/metricas.yaml" modelo/
cp "$RAIZ/exemplos/vendas/dashboard/spec.json" dashboard/
uv run --quiet --no-project --python 3.12 --with duckdb --with openpyxl --with pyyaml --with jsonschema \
  python -c "import sys; sys.path.insert(0, sys.argv[1]); from construir import construir; construir('vendas', '.')" \
  "$RAIZ/exemplos" > /dev/null
# Tira as saídas que já trazem valores calculados (achados e dashboard renderizado): sem isso, a
# execução sem o plugin acha o número pronto num arquivo e o caso deixa de medir de onde ele vem.
# Ficam a tabela ingerida, o perfil, o modelo validado e o design, que a camada de métricas usa.
rm -f saidas/bi/achados.json saidas/bi/dashboard.html saidas/bi/dashboard.artifact.html
