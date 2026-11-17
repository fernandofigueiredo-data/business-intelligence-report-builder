#!/usr/bin/env python3
"""
preparar_exemplo.py — grava saidas/dados_tratados.parquet do projeto de exemplo.

O projeto em `projeto_exemplo/` é uma cópia do exemplo do plugin analise-dados
(commit 10bbdaf, licença MIT). O parquet tratado não vem no repositório de lá
(`saidas/` é ignorada pelo git), então este script roda as células de código do
próprio `analise.ipynb`, em ordem, até a que grava o parquet:

    cd tests/dados/projeto_exemplo
    uv run --no-project --python 3.12 --with pandas --with pyarrow --with matplotlib ../preparar_exemplo.py
"""
import json, os
import matplotlib

matplotlib.use("Agg")
nb = json.load(open("analise.ipynb", encoding="utf-8"))
escopo = {}
for celula in nb["cells"]:
    if celula["cell_type"] != "code":
        continue
    codigo = "".join(celula["source"])
    exec(compile(codigo, "analise.ipynb", "exec"), escopo)
    if "to_parquet" in codigo:
        break
print("gravado:", os.path.getsize("saidas/dados_tratados.parquet"), "bytes")
