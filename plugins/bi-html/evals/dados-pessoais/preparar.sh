#!/usr/bin/env bash
# Projeto só com a planilha de clientes fictícios: CPF, e-mail e telefone.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
mkdir -p dados
cp "$RAIZ/fixtures/clientes_ficticios.csv" dados/
