#!/usr/bin/env python3
"""
pbix_externo.py — leitura de .pbix num processo à parte do servidor bi-dados.

O pbix-mcp exige mcp<2 e o servidor bi-dados usa mcp>=2.3 (achado da F6), então tudo o que
precisa abrir o modelo de dados do .pbix roda aqui, num ambiente próprio:

    uv run --no-project --python 3.12 --with pbix-mcp==0.9.153 --with pbixray==0.15.5 --with duckdb \\
        python -I pbix_externo.py extrair ARQUIVO.pbix PASTA_DE_SAIDA
    uv run ... python -I pbix_externo.py avaliar ARQUIVO.pbix PEDIDOS.json SAIDA.json

- `extrair`: detecta o modo de armazenamento; em importação, grava cada tabela em parquet
  (lida pelo pbixray, com a contagem conferida contra os metadados do pbix-mcp) e o modelo
  (colunas, relações, medidas, colunas e tabelas calculadas, RLS) em extracao.json.
- `avaliar`: avalia medidas DAX pelo motor do pbix-mcp em contextos de filtro; é a
  referência do teste de equivalência das medidas traduzidas.

Só usa as bibliotecas de leitura; o layout do relatório e o tema são lidos pelo bi-html,
direto do pacote, sem este processo.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from importlib.metadata import version
from pathlib import Path

SISTEMA = ("H$", "R$", "U$")
DATAS_AUTO = ("LocalDateTable", "DateTableTemplate")


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _abrir(caminho: str):
    import logging

    logging.disable(logging.WARNING)
    import pbix_mcp.server as servidor

    r = json.loads(servidor.pbix_open(caminho, "pbix"))
    if not r.get("success"):
        raise SystemExit(f"o pbix-mcp não abriu o arquivo: {r.get('message')}")
    return servidor


def detectar_modo(caminho: Path, servidor=None) -> dict:
    """Importação, DirectQuery, misto ou conexão dinâmica (mesma regra da prova da F6)."""
    z = zipfile.ZipFile(caminho)
    nomes = z.namelist()
    conexoes = json.loads(z.read("Connections").decode("utf-8-sig")) if "Connections" in nomes else {}
    ao_vivo = any((c.get("ConnectionType") or "").lower() in ("pbiservicelive", "analysisservicesdatabaselive")
                  for c in conexoes.get("Connections", []))
    if "DataModel" not in nomes:
        return {"modo": "conexao_dinamica" if ao_vivo else "sem_modelo", "modos_das_particoes": []}
    servidor = servidor or _abrir(str(caminho))
    texto = json.loads(servidor.pbix_get_partitions("pbix")).get("message", "")
    modos = sorted(set(re.findall(r"\[M/(\w+)\]", texto)))
    dq = any(m.lower() == "directquery" for m in modos) or servidor._ensure_open("pbix").get("is_directquery")
    if dq:
        modo = "misto" if any(m.lower() in ("import", "dual") for m in modos) else "directquery"
    else:
        modo = "importacao"
    return {"modo": modo, "modos_das_particoes": modos}


def _registros(df) -> list[dict]:
    if df is None or not len(df):
        return []
    return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))


def extrair(caminho: Path, destino: Path) -> dict:
    import duckdb
    import pbixray

    destino.mkdir(parents=True, exist_ok=True)
    (destino / "tabelas").mkdir(exist_ok=True)
    t0 = time.perf_counter()
    servidor = _abrir(str(caminho))
    modo = detectar_modo(caminho, servidor)
    saida = {
        "versao": 1,
        "arquivo": {"nome": caminho.name, "bytes": caminho.stat().st_size, "sha256": _sha256(caminho)},
        "ferramentas": {"pbix-mcp": version("pbix-mcp"), "pbixray": version("pbixray"), "duckdb": version("duckdb")},
        **modo,
        "tabelas": [], "relacoes": [], "medidas": [], "colunas_calculadas": [], "tabelas_calculadas": [], "rls": [],
    }
    if modo["modo"] != "importacao":
        (destino / "extracao.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return saida

    from pbix_mcp.formats.model_reader import ModelReader

    info = servidor._ensure_open("pbix")
    leitor = ModelReader(info["path"], work_dir=info.get("work_dir"))
    ray = pbixray.PBIXRay(str(caminho))
    # Linhas por tabela segundo os metadados do pbix-mcp (pbix_list_tables), para conferir a extração.
    meta = {}
    for linha in json.loads(servidor.pbix_list_tables("pbix")).get("message", "").splitlines()[1:]:
        partes = re.split(r"\s{2,}", linha.strip())
        if len(partes) >= 3 and partes[-1].isdigit():
            meta[partes[0]] = int(partes[-1])
    esquema = _registros(ray.schema)
    con = duckdb.connect()
    for i, nome in enumerate(sorted(meta)):
        colunas = {c["ColumnName"]: c.get("PandasDataType") for c in esquema if c["TableName"] == nome}
        registro = {"nome": nome, "linhas_metadados": meta[nome], "linhas_extraidas": None, "colunas": colunas,
                    "datas_automaticas": nome.startswith(DATAS_AUTO), "parquet": None}
        if colunas:
            df = ray.get_table(nome)
            arquivo = f"tabelas/t{i:02d}.parquet"
            con.register("t", df)
            con.execute(f"COPY (SELECT * FROM t) TO '{(destino / arquivo).as_posix()}' (FORMAT PARQUET)")
            con.unregister("t")
            registro.update({"linhas_extraidas": int(len(df)), "parquet": arquivo})
        else:
            registro["linhas_extraidas"] = 0
        saida["tabelas"].append(registro)
    con.close()
    saida["relacoes"] = [{"de_tabela": r["FromTableName"], "de_coluna": r["FromColumnName"],
                          "para_tabela": r["ToTableName"], "para_coluna": r["ToColumnName"],
                          "ativa": bool(r["IsActive"]), "cardinalidade": r.get("Cardinality"),
                          "direcao": r.get("CrossFilteringBehavior")} for r in _registros(ray.relationships)]
    formatos = {m["Name"]: m.get("FormatString") for m in leitor.dax_measures}
    saida["medidas"] = [{"tabela": m["TableName"], "nome": m["Name"], "expressao": m["Expression"],
                         "formato": formatos.get(m["Name"])} for m in _registros(ray.dax_measures)]
    saida["colunas_calculadas"] = [{"tabela": c["TableName"], "coluna": c["ColumnName"], "expressao": c["Expression"]}
                                   for c in _registros(ray.dax_columns)]
    saida["tabelas_calculadas"] = [{"tabela": p["TableName"], "expressao": p["Expression"]} for p in leitor.power_query
                                   if not re.match(r"\s*let\b", p["Expression"] or "")]
    saida["rls"] = _registros(ray.rls)
    saida["tempo_s"] = round(time.perf_counter() - t0, 3)
    (destino / "extracao.json").write_text(json.dumps(saida, ensure_ascii=False, indent=2, default=str) + "\n",
                                           encoding="utf-8")
    return saida


def avaliar(caminho: Path, pedidos: Path, destino: Path) -> list[dict]:
    """Cada pedido: {"id", "medida", "contexto": {"Tabela.Coluna": [valores]}, "agrupar": [chaves]}."""
    servidor = _abrir(str(caminho))
    respostas = []
    for p in json.loads(pedidos.read_text(encoding="utf-8")):
        t = time.perf_counter()
        saida = json.loads(servidor.pbix_evaluate_dax(
            "pbix", p["medida"], filter_context=json.dumps(p.get("contexto") or {}, ensure_ascii=False),
            apply_default_filters=False, group_by=json.dumps(p["agrupar"]) if p.get("agrupar") else ""))
        r = (saida.get("results") or [{}])[0]
        respostas.append({"id": p["id"], "valor": r.get("value"), "status": r.get("status") or
                          ("erro" if not saida.get("success") else None), "erro": None if saida.get("success")
                          else saida.get("message"), "tempo_s": round(time.perf_counter() - t, 4)})
    destino.write_text(json.dumps(respostas, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return respostas


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "extrair":
        r = extrair(Path(sys.argv[2]), Path(sys.argv[3]))
        print(json.dumps({"modo": r["modo"], "tabelas": len(r["tabelas"]), "medidas": len(r["medidas"])}))
    elif len(sys.argv) >= 5 and sys.argv[1] == "avaliar":
        r = avaliar(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        print(json.dumps({"avaliados": len(r)}))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
