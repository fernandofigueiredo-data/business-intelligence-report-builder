#!/usr/bin/env bash
# Votação fictícia no grão candidato × zona, com o eleitorado da zona repetido em cada linha:
# a forma do problema da issue #1. Somar zona_aptos conta cada zona uma vez por candidato.
set -euo pipefail
mkdir -p dados
{
  echo "nr_zona;candidato;votos;zona_aptos"
  for z in 1:12000 2:9500 3:15300 4:8100; do
    zona=${z%%:*}; aptos=${z##*:}
    for c in A:41 B:33 C:26; do
      cand=${c%%:*}; pct=${c##*:}
      echo "$zona;Candidato $cand;$(( aptos * 8 / 10 * pct / 100 ));$aptos"
    done
  done
} > dados/votacao.csv
