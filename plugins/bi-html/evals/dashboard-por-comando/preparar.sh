#!/usr/bin/env bash
# Projeto pronto, mas sem a spec e sem o dashboard: o comando precisa escrever os dois.
set -euo pipefail
bash "$(dirname "${BASH_SOURCE[0]}")/../_comum/projeto_vendas.sh"
rm -f dashboard/spec.json saidas/bi/dashboard.html saidas/bi/dashboard.artifact.html
