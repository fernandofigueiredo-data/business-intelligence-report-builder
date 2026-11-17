#!/usr/bin/env python3
"""
gerar_pbix.py — gera os .pbix fictícios do teste de conversão (fase F7), a partir de vendas.csv.

    uv run --no-project --python 3.12 --with pbix-mcp==0.9.153 python -I fixtures/gerar_pbix.py

Usa o construtor do pbix-mcp (o mesmo leitor da conversão, então é um teste do caminho, não do
leitor; a leitura de .pbix feitos no Power BI Desktop é conferida em provas/f7 com arquivos reais).

- vendas.pbix: importação; fato Vendas e dimensão Lojas ligadas por relação, medidas que cobrem
  cada padrão traduzível (soma, contagem distinta, razão, CALCULATE com filtro na própria tabela e
  na dimensão, SUMX com expressão, participação com ALLSELECTED, escala) e três que não traduzem
  (REMOVEFILTERS, TOTALYTD, FORMAT); uma página com cartões, barras, rosca, tabela, mapa por UF,
  linha no tempo e segmentação, no layout legado do relatório.
- vendas_directquery.pbix: a mesma tabela em DirectQuery, para a conversão recusar.

Os dados são os de vendas.csv, inventados.
"""
from __future__ import annotations

import csv
import json
import logging
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def ler_vendas() -> tuple[list[dict], list[dict]]:
    vendas, regiao_da_loja = [], {}
    with (AQUI / "vendas.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            num = lambda x: float(x.replace(",", "."))  # noqa: E731
            vendas.append({"data_pedido": datetime.strptime(r["data_pedido"], "%d/%m/%Y").strftime("%Y-%m-%dT00:00:00"),
                           "pedido_id": r["pedido_id"], "loja": r["loja"], "canal": r["canal"],
                           "categoria": r["categoria"], "produto": r["produto"], "quantidade": int(r["quantidade"]),
                           "preco_unitario": num(r["preco_unitario"]), "desconto_pct": num(r["desconto_pct"]),
                           "receita": num(r["receita"])})
            regiao_da_loja.setdefault(r["loja"], Counter())[(r["uf"], r["regiao"] or "")] += 1
    lojas = []
    for loja, cont in sorted(regiao_da_loja.items()):
        (uf, regiao), _ = max(((k, n) for k, n in cont.items() if k[1]), key=lambda x: x[1], default=(("", ""), 0))
        lojas.append({"loja": loja, "uf": uf, "regiao": regiao})
    return vendas, lojas


COLUNAS_VENDAS = [("data_pedido", "DateTime"), ("pedido_id", "String"), ("loja", "String"), ("canal", "String"),
                  ("categoria", "String"), ("produto", "String"), ("quantidade", "Int64"),
                  ("preco_unitario", "Double"), ("desconto_pct", "Double"), ("receita", "Double")]
COLUNAS_LOJAS = [("loja", "String"), ("uf", "String"), ("regiao", "String")]

MEDIDAS = [
    ("Faturamento", "SUM(Vendas[receita])", "R$ #,0.00"),
    ("Pedidos", "DISTINCTCOUNT(Vendas[pedido_id])", "#,0"),
    ("Itens", "SUM(Vendas[quantidade])", "#,0"),
    ("Ticket Médio", "DIVIDE([Faturamento], [Pedidos])", "R$ #,0.00"),
    ("Receita Site", 'CALCULATE([Faturamento], Vendas[canal] = "Site")', "R$ #,0.00"),
    ("Receita Sudeste", 'CALCULATE([Faturamento], Lojas[regiao] = "Sudeste")', "R$ #,0.00"),
    ("Receita Bruta", "SUMX(Vendas, Vendas[quantidade] * Vendas[preco_unitario])", "R$ #,0.00"),
    ("Desconto Médio", "AVERAGE(Vendas[desconto_pct])", "0.00"),
    ("Pedidos com Desconto", "CALCULATE([Pedidos], Vendas[desconto_pct] > 0)", "#,0"),
    ("Participação da UF", "DIVIDE([Faturamento], CALCULATE([Faturamento], ALLSELECTED(Lojas[uf])))", "0.0%"),
    ("Receita (R$ mil)", "DIVIDE([Faturamento], 1000)", "#,0.0"),
    ("Receita de Todas as Lojas", "CALCULATE([Faturamento], REMOVEFILTERS(Lojas))", "R$ #,0.00"),
    ("Receita Acumulada no Ano", "TOTALYTD([Faturamento], Vendas[data_pedido])", "R$ #,0.00"),
    ("Rótulo da Receita", 'FORMAT([Faturamento], "#,0")', ""),
]


def _campo(tipo: str, tabela: str, nome: str, funcao: int | None = None) -> tuple[dict, str]:
    ref = {"Expression": {"SourceRef": {"Source": tabela[0].lower()}}, "Property": nome}
    if tipo == "coluna":
        return {"Column": ref, "Name": f"{tabela}.{nome}"}, f"{tabela}.{nome}"
    if tipo == "medida":
        return {"Measure": ref, "Name": f"{tabela}.{nome}"}, f"{tabela}.{nome}"
    q = f"Sum({tabela}.{nome})"
    return {"Aggregation": {"Expression": {"Column": ref}, "Function": funcao}, "Name": q}, q


def _config(titulo: str | None, papeis: dict[str, list[tuple]]) -> str:
    selecao, projecoes, entidades = [], {}, set()
    for papel, campos in papeis.items():
        for c in campos:
            sel, qref = _campo(*c)
            selecao.append(sel)
            projecoes.setdefault(papel, []).append({"queryRef": qref})
            entidades.add(c[1])
    cfg = {"singleVisual": {"projections": projecoes, "prototypeQuery": {
        "Version": 2, "From": [{"Name": e[0].lower(), "Entity": e, "Type": 0} for e in sorted(entidades)],
        "Select": selecao}}}
    if titulo:
        cfg["singleVisual"]["vcObjects"] = {"title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{titulo}'"}}}}}]}
    return json.dumps(cfg, ensure_ascii=False)


VISUAIS = [
    ("card", 20, 20, 280, 120, "Faturamento", {"Values": [("medida", "Vendas", "Faturamento")]}),
    ("card", 320, 20, 280, 120, "Pedidos", {"Values": [("medida", "Vendas", "Pedidos")]}),
    ("card", 620, 20, 280, 120, "Ticket médio", {"Values": [("medida", "Vendas", "Ticket Médio")]}),
    ("slicer", 920, 20, 340, 120, None, {"Values": [("coluna", "Lojas", "regiao")]}),
    ("clusteredBarChart", 20, 160, 600, 300, "Receita por loja",
     {"Category": [("coluna", "Vendas", "loja")], "Y": [("medida", "Vendas", "Faturamento")]}),
    ("donutChart", 640, 160, 300, 300, "Receita por canal",
     {"Category": [("coluna", "Vendas", "canal")], "Y": [("medida", "Vendas", "Faturamento")]}),
    ("filledMap", 960, 160, 300, 300, "Receita por UF",
     {"Category": [("coluna", "Lojas", "uf")], "Values": [("medida", "Vendas", "Faturamento")]}),
    ("tableEx", 20, 480, 600, 220, "Categorias",
     {"Values": [("coluna", "Vendas", "categoria"), ("medida", "Vendas", "Faturamento"),
                 ("medida", "Vendas", "Itens"), ("agregacao", "Vendas", "desconto_pct", 1)]}),
    ("clusteredColumnChart", 640, 480, 620, 220, "Participação por UF",
     {"Category": [("coluna", "Lojas", "uf")], "Y": [("medida", "Vendas", "Participação da UF")]}),
    ("lineChart", 20, 720, 1240, 220, "Receita acumulada",
     {"Category": [("coluna", "Vendas", "data_pedido")], "Y": [("medida", "Vendas", "Receita Acumulada no Ano")]}),
    ("textbox", 20, 960, 600, 40, None, {}),
]


def gerar(destino: Path, modo: str) -> Path:
    import pbix_mcp.server as s

    vendas, lojas = ler_vendas()
    with tempfile.TemporaryDirectory() as tmp:
        linhas = Path(tmp) / "vendas.ndjson"
        linhas.write_text("\n".join(json.dumps(v, ensure_ascii=False) for v in vendas), encoding="utf-8")
        tabelas = [{"name": "Vendas", "columns": [{"name": n, "data_type": t} for n, t in COLUNAS_VENDAS],
                    "rows_path": str(linhas)}]
        if modo == "directquery":
            tabelas[0].update({"mode": "directquery", "source_db": {"type": "sqlserver", "server": "servidor-ficticio",
                                                                    "database": "vendas", "table": "vendas"}})
        else:
            tabelas.append({"name": "Lojas", "columns": [{"name": n, "data_type": t} for n, t in COLUNAS_LOJAS],
                            "rows": lojas})
        medidas = [{"table": "Vendas", "name": n, "expression": e, "format_string": f} for n, e, f in MEDIDAS]
        relacoes = [] if modo == "directquery" else [
            {"from_table": "Vendas", "from_column": "loja", "to_table": "Lojas", "to_column": "loja"}]
        r = json.loads(s.pbix_create(str(destino), "f", json.dumps(tabelas, ensure_ascii=False),
                                     json.dumps(medidas if modo != "directquery" else medidas[:1], ensure_ascii=False),
                                     json.dumps(relacoes)))
        if not r.get("success"):
            raise SystemExit(f"pbix_create falhou: {r.get('message')}")
    if modo != "directquery":
        paginas = json.loads(s.pbix_get_pages("f")).get("message", "")
        if "Visão geral" not in paginas:
            s.pbix_rename_page("f", 0, "Visão geral")
        for tipo, x, y, w, h, titulo, papeis in VISUAIS:
            cfg = _config(titulo, papeis) if papeis else ""
            r = json.loads(s.pbix_add_visual("f", 0, tipo, x, y, w, h, cfg))
            if not r.get("success"):
                raise SystemExit(f"pbix_add_visual falhou: {r.get('message')}")
    r = json.loads(s.pbix_save("f", str(destino)))
    if not r.get("success"):
        raise SystemExit(f"pbix_save falhou: {r.get('message')}")
    s.pbix_close("f", force=True)
    destino.with_name(destino.name + ".bak").unlink(missing_ok=True)  # cópia que o pbix_save deixa ao sobrescrever
    return destino


def main() -> None:
    logging.disable(logging.WARNING)
    for nome, modo in (("vendas.pbix", "importacao"), ("vendas_directquery.pbix", "directquery")):
        caminho = gerar(AQUI / nome, modo)
        print(f"gravado: {caminho.relative_to(AQUI.parent)} ({caminho.stat().st_size:,} bytes)".replace(",", "."))


if __name__ == "__main__":
    main()
