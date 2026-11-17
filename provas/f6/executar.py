#!/usr/bin/env python3
"""
executar.py — prova de conceito da F6: a matriz 5.1 do plano testada com arquivos .pbix reais.

    uv run --no-project --python 3.12 --with pbix-mcp==0.9.153 --with pbixray==0.15.5 \\
        --with duckdb --with pyyaml python -I provas/f6/executar.py \\
        --arquivo ifdata=/caminho/M5_Dashboard_IFdata.pbix --arquivo eleicoes=... --arquivo lab1=...

Sem --arquivo, só regenera MATRIZ.md a partir de resultados.json (precisa apenas da
biblioteca padrão).

Para cada arquivo e cada elemento da matriz, um processo separado abre o .pbix com o
pbix-mcp, chama as ferramentas do elemento (as mesmas funções que o servidor MCP expõe),
confere o que saiu com um segundo leitor (pbixray) ou com o próprio JSON do relatório, e
registra o tempo e o pico de memória do processo. A saída de cada ferramenta fica anexada em
saidas/<apelido>/, sem dados das tabelas: caminhos de origem são encurtados para o nome do
arquivo, dados embutidos em base64 nas consultas M são omitidos e as tabelas entram só como
contagens e hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SAIDAS = AQUI / "saidas"
RESULTADOS = AQUI / "resultados.json"
MATRIZ = AQUI / "MATRIZ.md"
REFERENCIAS = AQUI / "referencias.yaml"

ELEMENTOS = [
    ("dados", "Dados das tabelas"),
    ("modelo", "Modelo e relacionamentos"),
    ("dax_texto", "Medidas DAX (texto)"),
    ("dax_calculo", "Medidas DAX (cálculo)"),
    ("m", "Consultas Power Query (M)"),
    ("layout", "Layout de páginas e visuais"),
    ("filtros", "Filtros e segmentações"),
    ("tema", "Temas"),
    ("visuais_personalizados", "Visuais personalizados"),
    ("rls", "Segurança por linha (RLS)"),
]
MODOS = [("importacao", "Importação"), ("directquery", "DirectQuery"), ("conexao_dinamica", "Conexão dinâmica")]

# Classificação documental da matriz 5.1 (antes da F6), mantida para os modos sem arquivo.
DOCUMENTAL = {
    "dados": ("I", "N", "N"), "modelo": ("I", "I", "N"), "dax_texto": ("I", "I", "P"),
    "dax_calculo": ("P", "N", "N"), "m": ("P", "P", "N"), "layout": ("P", "P", "P"),
    "filtros": ("P", "P", "P"), "tema": ("I/P", "I/P", "I/P"), "visuais_personalizados": ("N", "N", "N"),
    "rls": ("P", "P", "N"),
}

# Visual do Power BI → bloco equivalente do bi-html (schemas/dashboard-spec.schema.json).
# "filtro" vira filtro global da spec; "decorativo" não carrega dado.
BLOCOS = {
    "card": "numero_destaque", "cardVisual": "faixa_kpis", "multiRowCard": "faixa_kpis", "kpi": "numero_destaque",
    "lineChart": "linha_tempo", "areaChart": "linha_tempo", "stackedAreaChart": "area_empilhada",
    "barChart": "barras_ranking", "clusteredBarChart": "barras_ranking", "columnChart": "barras_agrupadas",
    "clusteredColumnChart": "barras_agrupadas", "stackedColumnChart": "barras_agrupadas",
    "stackedBarChart": "barras_ranking", "donutChart": "rosca", "pieChart": "rosca", "tableEx": "tabela",
    "pivotTable": "tabela", "waterfallChart": "cascata", "funnel": "funil", "filledMap": "mapa_uf",
    "shapeMap": "mapa_uf", "slicer": "filtro", "advancedSlicerVisual": "filtro",
    "textbox": "decorativo", "shape": "decorativo", "basicShape": "decorativo", "image": "decorativo",
    "actionButton": "decorativo", "pageNavigator": "decorativo", "bookmarkNavigator": "decorativo",
}
# Visuais nativos sem bloco equivalente hoje (aparecem como lacuna, não como visual personalizado).
NATIVOS_SEM_BLOCO = {"scatterChart", "azureMap", "map", "gauge", "treemap", "ribbonChart", "decompositionTreeVisual",
                     "keyDriversVisual", "qnaVisual", "lineClusteredColumnComboChart", "lineStackedColumnComboChart",
                     "scriptVisual", "pythonVisual", "aiNarratives", "hundredPercentStackedBarChart",
                     "hundredPercentStackedColumnChart"}
SISTEMA = ("H$", "R$", "U$")
DATAS_AUTO = ("LocalDateTable", "DateTableTemplate")


# ----------------------------------------------------------------------------------------
# Anexos sem dados pessoais nem dados das tabelas
# ----------------------------------------------------------------------------------------

# Caminho do Windows em texto já serializado em JSON, com a barra invertida dobrada (C:\\pasta\\arquivo).
# Todo anexo é JSON serializado, então "\n" (quebra de linha escapada) não confunde com caminho.
_WIN = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:(?:\\\\[^\\\"'\n\r,]+)+")
_B64 = re.compile(r'(Binary\.FromText\(\\?")([A-Za-z0-9+/=]{80,})')
_GUID_REMOTO = re.compile(r'("(?:DatasetId|ReportId|ModelId)"\s*:\s*")[0-9a-fA-F-]{36}')


def ocultar(texto: str, caminhos: list[str] = ()) -> str:
    """Encurta caminhos absolutos para o nome do arquivo e omite dados embutidos em base64."""
    for c in sorted(caminhos, key=len, reverse=True):
        texto = texto.replace(c, "<caminho omitido>/" + Path(c).name)
    texto = _WIN.sub(lambda m: "<caminho omitido>\\\\" + re.split(r"\\+", m.group(0))[-1], texto)
    texto = _B64.sub(lambda m: f"{m.group(1)}<base64 omitido: {len(m.group(2))} caracteres>", texto)
    texto = _GUID_REMOTO.sub(lambda m: m.group(1) + "<id omitido>", texto)
    home = str(Path.home())
    return texto.replace(home, "~")


def pl(n: int, singular: str, plural: str | None = None) -> str:
    """Quantidade com o substantivo no número certo: 1 tabela, 2 tabelas."""
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def _num(v):
    f = float(v)
    if f != f:  # NaN
        return None
    return str(int(f)) if f.is_integer() else format(f, ".12g")


def normalizar(v) -> str | None:
    """Valor de célula em forma canônica, para comparar dois leitores sem depender do tipo."""
    if v is None:
        return None
    try:
        import pandas as pd
        if v is pd.NA or v is pd.NaT:
            return None
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
    except ImportError:  # pragma: no cover
        pass
    if isinstance(v, bool):
        return "true" if v else "false"
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):  # escalares do numpy
        v = v.item()
        if isinstance(v, bool):
            return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, datetime):
        return v.replace(tzinfo=None).isoformat()
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day).isoformat()
    try:
        from decimal import Decimal
        if isinstance(v, Decimal):
            return _num(v)
    except ImportError:  # pragma: no cover
        pass
    return str(v)


def hash_de_colunas(colunas: list[str], linhas) -> dict:
    """Hash por coluna (multiconjunto de valores, sem depender da ordem das linhas)."""
    por_coluna = {c: [] for c in colunas}
    n = 0
    for linha in linhas:
        n += 1
        for c, v in zip(colunas, linha):
            por_coluna[c].append(normalizar(v))
    saida = {}
    for c, valores in por_coluna.items():
        h = hashlib.sha256()
        for x in sorted(valores, key=lambda x: (x is None, x or "")):
            h.update(b"\x00" if x is None else x.encode("utf-8") + b"\x01")
        saida[c] = h.hexdigest()[:16]
    return {"linhas": n, "colunas": saida}


# ----------------------------------------------------------------------------------------
# Processo filho: um elemento de um arquivo
# ----------------------------------------------------------------------------------------

def pico_rss_mb() -> float:
    import resource
    pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(pico / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)


class Contexto:
    def __init__(self, apelido: str, caminho: str, elemento: str):
        import pbix_mcp.server as servidor
        self.s, self.apelido, self.caminho, self.elemento = servidor, apelido, caminho, elemento
        self.zip = zipfile.ZipFile(caminho)
        self.nomes = self.zip.namelist()
        self.anexos: list[str] = []
        self.tempos: dict[str, float] = {}
        self._ray = None
        (SAIDAS / apelido).mkdir(parents=True, exist_ok=True)

    @contextmanager
    def medir(self, nome: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.tempos[nome] = round(self.tempos.get(nome, 0) + time.perf_counter() - t, 3)

    def ferramenta(self, funcao: str, *args, **kwargs) -> str:
        """Chama uma ferramenta do pbix-mcp e soma o tempo em tempo_ferramenta_s."""
        with self.medir("tempo_ferramenta_s"):
            return getattr(self.s, funcao)(self.apelido, *args, **kwargs)

    def anexar(self, nome: str, conteudo) -> str:
        if not isinstance(conteudo, str):
            conteudo = json.dumps(conteudo, ensure_ascii=False, indent=2, default=str)
        rel = f"saidas/{self.apelido}/{self.elemento}__{nome}"
        (AQUI / rel).write_text(ocultar(conteudo, [self.caminho]) + "\n", encoding="utf-8")
        self.anexos.append(rel)
        return rel

    def ray(self):
        if self._ray is None:
            import pbixray
            with self.medir("tempo_conferencia_s"):
                self._ray = pbixray.PBIXRay(self.caminho)
        return self._ray

    def leitor(self):
        """O leitor do modelo que as ferramentas do pbix-mcp usam por baixo (texto integral, sem formatação)."""
        from pbix_mcp.formats.model_reader import ModelReader
        info = self.s._ensure_open(self.apelido)
        with self.medir("tempo_ferramenta_s"):
            return ModelReader(info["path"], work_dir=info.get("work_dir"))

    def json_zip(self, nome: str):
        return json.loads(self.zip.read(nome).decode("utf-8-sig"))

    def paginas(self) -> list[dict]:
        """Páginas e visuais lidos direto do JSON do relatório (PBIR), para conferir as ferramentas."""
        if "Report/definition/pages/pages.json" not in self.nomes:
            return []
        ordem = self.json_zip("Report/definition/pages/pages.json").get("pageOrder", [])
        saida = []
        for pid in ordem:
            base = f"Report/definition/pages/{pid}/"
            pagina = self.json_zip(base + "page.json")
            visuais = [self.json_zip(n) for n in self.nomes if n.startswith(base + "visuals/") and n.endswith("/visual.json")]
            saida.append({"id": pid, "pagina": pagina, "visuais": visuais})
        return saida


def _mensagem(saida: str) -> dict:
    try:
        return json.loads(saida)
    except json.JSONDecodeError:
        return {"success": False, "message": saida}


def _tabelas_do_modelo(ctx) -> list[dict]:
    """Tabelas de pbix_list_tables (nome, colunas, linhas)."""
    msg = _mensagem(ctx.ferramenta("pbix_list_tables"))
    linhas = msg.get("message", "").splitlines()[1:]
    tabelas = []
    for linha in linhas:
        partes = re.split(r"\s{2,}", linha.strip())
        if len(partes) >= 3 and partes[-1].isdigit():
            tabelas.append({"tabela": partes[0], "colunas": int(partes[1]), "linhas": int(partes[2])})
    return tabelas


def modo(ctx) -> dict:
    """Modo de armazenamento: importação, DirectQuery, misto ou conexão dinâmica."""
    tem_modelo = "DataModel" in ctx.nomes
    conexoes = ctx.json_zip("Connections") if "Connections" in ctx.nomes else {}
    ao_vivo = any((c.get("ConnectionType") or "").lower() in ("pbiservicelive", "analysisservicesdatabaselive")
                  for c in conexoes.get("Connections", []))
    evid = {"DataModel no arquivo": tem_modelo,
            "Connections": {k: ("presente (ids omitidos)" if k == "RemoteArtifacts" else v) for k, v in conexoes.items()},
            "conexão dinâmica declarada": ao_vivo}
    if not tem_modelo:
        return {"modo": "conexao_dinamica" if ao_vivo else "sem_modelo", "evidencia": evid}
    particoes = ctx.ferramenta("pbix_get_partitions")
    ctx.anexar("particoes.txt", particoes)
    modos = re.findall(r"\[M/(\w+)\]", _mensagem(particoes).get("message", ""))
    info = ctx.s._ensure_open(ctx.apelido)
    evid.update({"modos das partições": sorted(set(modos)), "is_directquery (pbix-mcp)": info.get("is_directquery")})
    if any(m.lower() == "directquery" for m in modos) or info.get("is_directquery"):
        m = "misto" if any(m.lower() in ("import", "dual") for m in modos) else "directquery"
    else:
        m = "importacao"
    return {"modo": m, "evidencia": evid}


def dados(ctx) -> dict:
    tabelas = _tabelas_do_modelo(ctx)
    ctx.anexar("pbix_list_tables.txt", ctx.s.pbix_list_tables(ctx.apelido))
    leitor = ctx.leitor()
    ray = ctx.ray()
    comparacao, iguais = [], True
    for t in tabelas:
        with ctx.medir("tempo_ferramenta_s"):
            bruto = leitor.get_table(t["tabela"], max_rows=0)
        a = hash_de_colunas(bruto["columns"], bruto["rows"])
        with ctx.medir("tempo_conferencia_s"):
            try:
                df = ray.get_table(t["tabela"])
                b = hash_de_colunas(list(df.columns), df.itertuples(index=False, name=None))
            except Exception as e:  # noqa: BLE001
                b = {"linhas": None, "colunas": {}, "erro": str(e)}
        divergentes = sorted(c for c in set(a["colunas"]) | set(b["colunas"])
                             if a["colunas"].get(c) != b["colunas"].get(c))
        ok = t["linhas"] == a["linhas"] == b["linhas"] and not divergentes
        iguais &= ok
        comparacao.append({"tabela": t["tabela"], "linhas_metadados": t["linhas"], "linhas_pbix_mcp": a["linhas"],
                           "linhas_pbixray": b["linhas"], "colunas": len(a["colunas"]),
                           "colunas_divergentes": divergentes, "erro_pbixray": b.get("erro"), "iguais": ok})
    ctx.anexar("comparacao.json", comparacao)
    total = sum(c["linhas_pbix_mcp"] for c in comparacao)
    return {
        "status": "testada", "classificacao": "I" if iguais else "P",
        "resumo": (f"{pl(len(comparacao), 'tabela')} e {total:,} linhas lidas por inteiro; contagem e conteúdo de cada coluna "
                   "iguais nos dois leitores" if iguais else
                   f"divergência em {sum(not c['iguais'] for c in comparacao)} de {len(comparacao)} tabelas").replace(",", "."),
        "medidas": {"tabelas": len(comparacao), "linhas": total},
    }


def modelo(ctx) -> dict:
    ctx.anexar("pbix_get_model_schema.txt", ctx.ferramenta("pbix_get_model_schema"))
    ctx.anexar("pbix_get_model_relationships.txt", ctx.ferramenta("pbix_get_model_relationships"))
    leitor = ctx.leitor()
    with ctx.medir("tempo_ferramenta_s"):
        col_a = {(c["TableName"], c["ColumnName"]) for c in leitor.schema
                 if not c["TableName"].startswith(SISTEMA) and c["ColumnName"] != "RowNumber-2662979B-1795-4F74-8F37-6A1BA8059B61"}
        rel_a = {(r["FromTableName"], r["FromColumnName"], r["ToTableName"], r["ToColumnName"], bool(r["IsActive"]))
                 for r in leitor.relationships}
    ray = ctx.ray()
    with ctx.medir("tempo_conferencia_s"):
        col_b = {(r["TableName"], r["ColumnName"]) for r in ray.schema.to_dict("records")}
        rel_b = {(r["FromTableName"], r["FromColumnName"], r["ToTableName"], r["ToColumnName"], bool(r["IsActive"]))
                 for r in ray.relationships.to_dict("records")} if len(ray.relationships) else set()
    so_a, so_b = sorted(col_a - col_b), sorted(col_b - col_a)
    # Relações com a tabela de datas automática do Power BI (data/hora automática) ficam à parte:
    # o pbix-mcp as lista e o pbixray não; nenhuma delas é parte do modelo que o autor desenhou.
    auto = {r for r in rel_a | rel_b if r[2].startswith(DATAS_AUTO) or r[0].startswith(DATAS_AUTO)}
    rel_a, rel_b = rel_a - auto, rel_b - auto
    ok = not so_a and not so_b and rel_a == rel_b and col_a
    ctx.anexar("comparacao.json", {"colunas_pbix_mcp": len(col_a), "colunas_pbixray": len(col_b),
                                   "so_no_pbix_mcp": so_a, "so_no_pbixray": so_b,
                                   "relacoes_pbix_mcp": sorted(rel_a), "relacoes_pbixray": sorted(rel_b),
                                   "relacoes_com_datas_automaticas": sorted(auto)})
    resumo = (f"{pl(len(col_a), 'coluna')} e {pl(len(rel_a), 'relação', 'relações')}; iguais nos dois leitores" if ok else
              f"divergência: {len(so_a)} colunas só no pbix-mcp, {len(so_b)} só no pbixray, "
              f"relações {'iguais' if rel_a == rel_b else 'diferentes'}")
    if auto:
        resumo += f"; {len(auto)} relação com a tabela de datas automática, que só o pbix-mcp lista"
    return {"status": "testada", "classificacao": "I" if ok else "P", "resumo": resumo,
            "medidas": {"colunas": len(col_a), "relacoes": len(rel_a), "relacoes_datas_automaticas": len(auto)}}


def _sem_espaco(texto: str | None) -> str:
    return " ".join((texto or "").split())


def dax_texto(ctx) -> dict:
    ctx.anexar("pbix_get_model_measures.txt", ctx.ferramenta("pbix_get_model_measures"))
    leitor = ctx.leitor()
    autor = lambda t: not t.startswith(DATAS_AUTO)  # noqa: E731  (fora as tabelas de datas automáticas)
    with ctx.medir("tempo_ferramenta_s"):
        med_a = {m["Name"]: m["Expression"] for m in leitor.dax_measures}
        colc_a = {(c["TableName"], c["ColumnName"]): c["Expression"] for c in (leitor.dax_columns or []) if autor(c["TableName"])}
        tabc_a = {p["TableName"]: p["Expression"] for p in leitor.power_query if not _e_m(p["Expression"]) and autor(p["TableName"])}
    ray = ctx.ray()
    with ctx.medir("tempo_conferencia_s"):
        med_b = {m["Name"]: m["Expression"] for m in ray.dax_measures.to_dict("records")}
        colc_b = {(c["TableName"], c["ColumnName"]): c["Expression"] for c in ray.dax_columns.to_dict("records") if autor(c["TableName"])}
        tabc_b = {t["TableName"]: t["Expression"] for t in ray.dax_tables.to_dict("records") if autor(t["TableName"])} \
            if len(ray.dax_tables) else {}
    ctx.anexar("medidas.json", [{"medida": k, "expressao": v} for k, v in sorted(med_a.items())])
    if colc_a or tabc_a:
        ctx.anexar("colunas_e_tabelas_calculadas.json",
                   {"colunas": [{"tabela": t, "coluna": c, "expressao": e} for (t, c), e in sorted(colc_a.items())],
                    "tabelas": [{"tabela": t, "expressao": e} for t, e in sorted(tabc_a.items())]})
    if not med_a and not med_b and not colc_a and not tabc_a:
        return {"status": "sem_elemento", "classificacao": None,
                "resumo": "o arquivo não tem medidas, colunas nem tabelas calculadas em DAX do autor "
                          "(os visuais usam agregação implícita; só há a tabela de datas automática)"}
    mesmo = lambda a, b: set(a) == set(b) and all(_sem_espaco(a[k]) == _sem_espaco(b[k]) for k in a)  # noqa: E731
    exatas = sum(1 for k in med_a if med_b.get(k) == med_a[k])
    iguais = mesmo(med_a, med_b) and mesmo(colc_a, colc_b) and mesmo(tabc_a, tabc_b)
    corta = "..." in _mensagem(ctx.s.pbix_get_model_measures(ctx.apelido)).get("message", "")
    resumo = (f"{pl(len(med_a), 'medida')}, {pl(len(colc_a), 'coluna calculada', 'colunas calculadas')} e "
              f"{pl(len(tabc_a), 'tabela calculada', 'tabelas calculadas')}; texto integral "
              f"igual nos dois leitores ({exatas} medidas idênticas caractere a caractere)" if iguais else
              "texto diferente entre os leitores: " + ", ".join(
                  n for n, a, b in (("medidas", med_a, med_b), ("colunas", colc_a, colc_b), ("tabelas", tabc_a, tabc_b))
                  if not mesmo(a, b)))
    if corta:
        resumo += "; a saída formatada de pbix_get_model_measures corta expressões longas, o texto integral vem do leitor do pacote"
    return {"status": "testada", "classificacao": "I" if iguais else "P", "resumo": resumo,
            "medidas": {"medidas": len(med_a), "colunas_calculadas": len(colc_a), "tabelas_calculadas": len(tabc_a)}}


def _comparar(obtido, esperado) -> bool:
    if obtido is None or esperado is None:
        return obtido is None and esperado is None
    if isinstance(esperado, str) or isinstance(obtido, str):
        return str(obtido) == str(esperado)
    a, b = float(obtido), float(esperado)
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def dax_calculo(ctx) -> dict:
    import yaml
    refs = (yaml.safe_load(REFERENCIAS.read_text(encoding="utf-8")) or {}).get(ctx.apelido) or {}
    leitor = ctx.leitor()
    nomes = [m["Name"] for m in leitor.dax_measures]
    if not nomes:
        ctx.anexar("pbix_get_model_measures.txt", ctx.ferramenta("pbix_get_model_measures"))
        return {"status": "sem_elemento", "classificacao": None,
                "resumo": "o arquivo não tem medidas DAX para avaliar (os visuais usam agregação implícita)"}
    # 1) cobertura: todas as medidas num mesmo contexto, contando erros
    cobertura = refs.get("cobertura") or {}
    t0 = time.perf_counter()
    bruto = ctx.ferramenta("pbix_evaluate_dax", ",".join(n for n in nomes if "," not in n),
                           filter_context=json.dumps(cobertura, ensure_ascii=False) if cobertura else "",
                           apply_default_filters=False)
    tempo_cobertura = round(time.perf_counter() - t0, 3)
    ctx.anexar("cobertura.json", {"contexto": cobertura, "tempo_s": tempo_cobertura, "saida": _mensagem(bruto)})
    resultados = _mensagem(bruto).get("results", [])
    erros = [r for r in resultados if r.get("status") != "ok"]
    # 2) paridade: amostra de contextos contra SQL independente no DuckDB
    import duckdb
    ray = ctx.ray()
    con = duckdb.connect()
    with ctx.medir("tempo_conferencia_s"):
        for t in ray.tables:
            if not str(t).startswith(SISTEMA) and not str(t).startswith(("LocalDateTable", "DateTableTemplate")):
                try:
                    con.register(str(t), ray.get_table(t))
                except Exception:  # noqa: BLE001
                    pass
    conferencias = []
    for c in refs.get("conferencias") or []:
        t0 = time.perf_counter()
        saida = _mensagem(ctx.ferramenta(
            "pbix_evaluate_dax", c["medida"], filter_context=json.dumps(c.get("contexto") or {}, ensure_ascii=False),
            apply_default_filters=False, group_by=json.dumps(c["agrupar"]) if c.get("agrupar") else ""))
        r = (saida.get("results") or [{}])[0]
        tempo = round(time.perf_counter() - t0, 3)
        with ctx.medir("tempo_conferencia_s"):
            linha = con.execute(c["sql"]).fetchone()
        esperado = linha[0] if linha else None
        if hasattr(esperado, "item"):
            esperado = esperado.item()
        conferencias.append({"medida": c["medida"], "contexto": c.get("contexto") or {}, "agrupar": c.get("agrupar"),
                             "pbix_mcp": r.get("value"), "status_pbix_mcp": r.get("status"),
                             "referencia_sql": esperado if not hasattr(esperado, "__float__") else float(esperado),
                             "bate": r.get("status") == "ok" and _comparar(r.get("value"), esperado),
                             "tempo_pbix_mcp_s": tempo})
    ctx.anexar("paridade.json", conferencias)
    batem = sum(c["bate"] for c in conferencias)
    lentas = sorted(conferencias, key=lambda c: -c["tempo_pbix_mcp_s"])[:2]
    ok = not erros and conferencias and batem == len(conferencias)
    resumo = (f"{len(resultados) - len(erros)} de {len(resultados)} medidas avaliadas sem erro; "
              f"{batem} de {len(conferencias)} conferências contra SQL independente batem")
    if erros:
        resumo += f"; erros em: {', '.join(e['name'] for e in erros[:6])}"
    resumo += (f"; todas as medidas juntas em {tempo_cobertura:.1f} s".replace(".", ",")
               + (f", a conferência mais lenta ({lentas[0]['medida']}) em {lentas[0]['tempo_pbix_mcp_s']:.1f} s".replace(".", ",")
                  if lentas else ""))
    return {"status": "testada", "classificacao": "I" if ok else "P", "resumo": resumo,
            "medidas": {"avaliadas": len(resultados), "erros": len(erros), "conferencias": len(conferencias), "batem": batem,
                        "tempo_cobertura_s": tempo_cobertura}}


def _e_m(expr: str) -> bool:
    """Partição em M (let ... in) e não tabela calculada em DAX (DATATABLE, CALENDAR...)."""
    return bool(re.match(r"\s*let\b", expr or "")) or "#shared" in (expr or "")


def _compartilhadas(ctx) -> dict[str, str]:
    """Consultas compartilhadas e parâmetros (tabela Expression dos metadados), pelo pbix-mcp."""
    # Uma linha por consulta, com um separador que não aparece em nomes (" | " aparece).
    sql = "SELECT Name || ' ⟧⟦ ' || replace(replace(Expression, char(13), ' '), char(10), ' ') AS c FROM Expression"
    saida = _mensagem(ctx.ferramenta("pbix_datamodel_query_metadata", sql))
    ctx.anexar("pbix_datamodel_query_metadata_Expression.txt", saida)
    linhas = saida.get("message", "").splitlines()[2:]
    return dict(linha.split(" ⟧⟦ ", 1) for linha in linhas if " ⟧⟦ " in linha)


def m(ctx) -> dict:
    ctx.anexar("pbix_get_model_power_query.txt", ctx.ferramenta("pbix_get_model_power_query"))
    ctx.anexar("pbix_get_m_code.txt", ctx.ferramenta("pbix_get_m_code"))
    fontes_txt = ctx.ferramenta("pbix_list_data_sources")
    ctx.anexar("pbix_list_data_sources.txt", fontes_txt)
    leitor = ctx.leitor()
    with ctx.medir("tempo_ferramenta_s"):
        particoes = {p["TableName"]: p["Expression"] for p in leitor.power_query}
    exp_a = {t: e for t, e in particoes.items() if _e_m(e)}
    dax = sorted(t for t, e in particoes.items() if not _e_m(e))
    comp_a = _compartilhadas(ctx)
    ray = ctx.ray()
    with ctx.medir("tempo_conferencia_s"):
        exp_b = {p["TableName"]: p["Expression"] for p in ray.power_query.to_dict("records")}
        comp_b = {p["ParameterName"]: " ".join(str(p.get("Expression") or "").replace("\r", " ").split("\n"))
                  for p in ray.m_parameters.to_dict("records")} if len(ray.m_parameters) else {}
    tabelas = [t["tabela"] for t in _tabelas_do_modelo(ctx) if t["tabela"] not in dax and not t["tabela"].startswith(DATAS_AUTO)]
    sem_m = sorted(t for t in tabelas if t not in exp_a)

    def origem(expr: str, vistos=()) -> list[str]:
        """Arquivos lidos pela consulta, seguindo as referências a consultas compartilhadas."""
        arquivos = re.findall(r'File\.Contents\("([^"]+)"', expr)
        for nome, corpo in comp_a.items():
            if nome not in vistos and re.search(rf"(?<![\w#\"]){re.escape(nome)}(?![\w\"])", expr):
                arquivos += origem(corpo, (*vistos, nome))
        return arquivos

    fontes = []
    for tabela, expr in sorted(exp_a.items()):
        arquivos = origem(expr)
        tipo = ("arquivo" if arquivos else "web" if "Web.Contents(" in expr else
                "banco" if re.search(r"Sql\.Database\(|PostgreSQL\.Database\(|Odbc\.", expr) else
                "dados embutidos" if "Binary.FromText(" in expr else "outra")
        rotulo = re.search(rf"^\s*{re.escape(tabela)}: ([^\n(]+)", _mensagem(fontes_txt).get("message", ""), re.M)
        fontes.append({"tabela": tabela, "tipo": tipo, "via_consulta_compartilhada": origem(expr) != re.findall(r'File\.Contents\("([^"]+)"', expr),
                       "rotulo_em_pbix_list_data_sources": rotulo.group(1).strip() if rotulo else None,
                       "arquivo_de_origem": sorted({re.split(r"[\\/]", a)[-1] for a in arquivos}),
                       "origem_existe_nesta_maquina": all(Path(a).exists() for a in arquivos) if arquivos else None})
    ctx.anexar("fontes.json", {"tabelas_calculadas_em_dax": dax, "consultas_compartilhadas": sorted(comp_a), "fontes": fontes})
    iguais = exp_a == exp_b and {k: _sem_espaco(v) for k, v in comp_a.items()} == {k: _sem_espaco(v) for k, v in comp_b.items()}
    executaveis = sum(1 for f in fontes if f["tipo"] == "dados embutidos" or f["origem_existe_nesta_maquina"])
    errado = [f["tabela"] for f in fontes if f["via_consulta_compartilhada"] and f["rotulo_em_pbix_list_data_sources"] == "Embedded"]
    resumo = (f"texto M de {len(exp_a)} de {pl(len(tabelas), 'tabela')} e de {pl(len(comp_a), 'consulta compartilhada', 'consultas compartilhadas')} lido "
              f"({'igual' if iguais else 'diferente'} no pbixray)"
              + (f", mais {pl(len(dax), 'tabela calculada', 'tabelas calculadas')} em DAX" if dax else "")
              + f"; execução não tentada: {executaveis} de {pl(len(fontes), 'consulta')} com a origem disponível aqui "
              "(dados embutidos); as demais leem arquivos de outra máquina")
    if comp_a:
        resumo += "; as consultas compartilhadas só aparecem nos metadados (pbix_datamodel_query_metadata), não em pbix_get_model_power_query"
    if errado:
        resumo += f"; pbix_list_data_sources rotula como Embedded {pl(len(errado), 'tabela')} cuja origem é um arquivo lido por consulta compartilhada"
    if sem_m:
        resumo += f"; sem M: {', '.join(sem_m)}"
    return {"status": "testada", "classificacao": "P", "resumo": resumo,
            "medidas": {"consultas": len(exp_a), "compartilhadas": len(comp_a), "tabelas_dax": len(dax),
                        "tabelas": len(tabelas), "origem_disponivel": executaveis, "rotulo_errado": len(errado)}}


def _tipo(v: dict) -> str:
    return (v.get("visual") or {}).get("visualType") or ("grupo" if "visualGroup" in v else "desconhecido")


def layout(ctx) -> dict:
    formato = "PBIR" if any(n.startswith("Report/definition/") for n in ctx.nomes) else (
        "legado (Report/Layout)" if "Report/Layout" in ctx.nomes else "sem relatório")
    paginas_msg = ctx.ferramenta("pbix_get_pages")
    ctx.anexar("pbix_get_pages.txt", paginas_msg)
    por_ferramenta = [int(n) for n in re.findall(r"— (\d+) visuals", _mensagem(paginas_msg).get("message", ""))]
    visuais_txt = [_mensagem(ctx.ferramenta("pbix_get_page_visuals", i)) for i in range(len(por_ferramenta))]
    ctx.anexar("pbix_get_page_visuals.json", visuais_txt)
    with ctx.medir("tempo_conferencia_s"):
        paginas = ctx.paginas()
        no_json = [len(p["visuais"]) for p in paginas]
        tipos: dict[str, int] = {}
        for p in paginas:
            for v in p["visuais"]:
                tipos[_tipo(v)] = tipos.get(_tipo(v), 0) + 1
        com_posicao = sum(1 for p in paginas for v in p["visuais"] if v.get("position"))
    de_dados = {t: n for t, n in tipos.items() if BLOCOS.get(t) not in ("decorativo", "filtro") and t != "grupo"}
    com_bloco = {t: n for t, n in de_dados.items() if t in BLOCOS}
    sem_bloco = {t: n for t, n in de_dados.items() if t not in BLOCOS}
    leitura_ok = por_ferramenta == no_json and com_posicao == sum(no_json)
    mapa = {t: BLOCOS.get(t, "sem bloco equivalente") for t in sorted(tipos)}
    ctx.anexar("visuais_por_tipo.json", {"formato": formato, "visuais_por_pagina_ferramenta": por_ferramenta,
                                        "visuais_por_pagina_json": no_json, "tipos": tipos, "bloco_bi_html": mapa})
    n_dados, n_bloco = sum(de_dados.values()), sum(com_bloco.values())
    return {
        "status": "testada", "classificacao": "P",
        "resumo": (f"{formato}: {pl(len(paginas), 'página')} e {pl(sum(no_json), 'visual', 'visuais')} lidos com tipo e posição "
                   f"({'iguais' if leitura_ok else 'diferentes'} no JSON do relatório); {n_bloco} de {n_dados} visuais de "
                   f"dados têm bloco equivalente no bi-html"
                   + (f"; sem bloco: {', '.join(f'{t} ({n})' for t, n in sorted(sem_bloco.items()))}" if sem_bloco else "")),
        "medidas": {"paginas": len(paginas), "visuais": sum(no_json), "visuais_de_dados": n_dados,
                    "com_bloco": n_bloco, "leitura_confere": leitura_ok},
    }


def filtros(ctx) -> dict:
    paginas = ctx.paginas()
    saidas, por_ferramenta, padroes = [], 0, 0
    rel = _mensagem(ctx.ferramenta("pbix_get_filters", -1))
    saidas.append(rel)
    for i in range(len(paginas)):
        f = _mensagem(ctx.ferramenta("pbix_get_filters", i))
        d = _mensagem(ctx.ferramenta("pbix_get_default_filters", i))
        saidas += [f, d]
        corpo = f.get("message", "").split("\n", 1)[-1]
        try:
            por_ferramenta += len(json.loads(corpo))
        except json.JSONDecodeError:
            pass
        padroes += len(((d.get("data") or {}).get("filters")) or {})
    ctx.anexar("pbix_get_filters_e_default_filters.json", saidas)
    with ctx.medir("tempo_conferencia_s"):
        relatorio = ctx.json_zip("Report/definition/report.json") if "Report/definition/report.json" in ctx.nomes else {}
        f_rel = len((relatorio.get("filterConfig") or {}).get("filters", []))
        f_pag = sum(len((p["pagina"].get("filterConfig") or {}).get("filters", [])) for p in paginas)
        f_vis = sum(len((v.get("filterConfig") or {}).get("filters", [])) for p in paginas for v in p["visuais"])
        segm = sum(1 for p in paginas for v in p["visuais"] if BLOCOS.get(_tipo(v)) == "filtro")
        interacoes = sum(len(p["pagina"].get("visualInteractions") or []) for p in paginas)
    ctx.anexar("contagem_no_json.json", {"filtros_relatorio": f_rel, "filtros_pagina": f_pag, "filtros_visual": f_vis,
                                         "segmentacoes": segm, "interacoes_editadas": interacoes,
                                         "filtros_pagina_pela_ferramenta": por_ferramenta,
                                         "selecoes_padrao_pela_ferramenta": padroes})
    confere = por_ferramenta == f_pag
    return {
        "status": "testada", "classificacao": "P",
        "resumo": (f"{pl(segm, 'segmentação', 'segmentações')}, {pl(f_pag, 'filtro')} de página ({'conferem' if confere else 'não conferem'} com o JSON), "
                   f"{pl(f_vis, 'filtro')} de visual, {pl(padroes, 'seleção padrão', 'seleções padrão')} de segmentação e "
                   f"{pl(interacoes, 'interação editada', 'interações editadas')}; "
                   "filtros de visual e interações só aparecem no JSON do visual (não há ferramenta própria)"),
        "medidas": {"segmentacoes": segm, "filtros_pagina": f_pag, "filtros_visual": f_vis,
                    "selecoes_padrao": padroes, "interacoes": interacoes, "confere": confere},
    }


def tema(ctx) -> dict:
    saida = ctx.ferramenta("pbix_get_theme")
    ctx.anexar("pbix_get_theme.txt", saida)
    mensagem = _mensagem(saida).get("message", "")
    # A ferramenta devolve um ou mais temas, cada um como "Theme file: nome.json" seguido do JSON.
    secoes = {}
    for bloco in re.split(r"(?:^|\n\n)Theme file: ", mensagem):
        if bloco.strip():
            nome, _, corpo = bloco.partition("\n")
            secoes[nome.strip()] = corpo
    colecao = (ctx.json_zip("Report/definition/report.json") if "Report/definition/report.json" in ctx.nomes else {}
               ).get("themeCollection") or {}
    em_uso = colecao.get("customTheme") or colecao.get("baseTheme") or {}
    chave = lambda n: re.sub(r"\.json$", "", n or "")  # noqa: E731
    da_ferramenta = next((c for n, c in secoes.items() if chave(n) == chave(em_uso.get("name"))), None)
    corpo, origem = da_ferramenta, "pbix_get_theme"
    if corpo is None:  # o tema em uso não veio da ferramenta: lê do pacote para ainda conferir a importação
        arquivo = next((n for n in ctx.nomes if n.startswith("Report/StaticResources/")
                        and chave(Path(n).name) == chave(em_uso.get("name"))), None)
        corpo, origem = (ctx.zip.read(arquivo).decode("utf-8-sig"), f"lido do pacote, {Path(arquivo).name}") if arquivo else (None, None)
    # O tema extraído vira design system de entrada do bi-html (seção 7 do plano).
    sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
    from bi_html.design import importar
    importacao = {"ok": False, "erro": "tema em uso não encontrado"}
    if corpo is not None:
        with tempfile.TemporaryDirectory() as tmp, ctx.medir("tempo_conferencia_s"):
            arq = Path(tmp) / "tema.json"
            arq.write_text(corpo, encoding="utf-8")
            try:
                r = importar(Path(tmp), str(arq))
                importacao = {"ok": bool(r["aa"]), "origem": origem, "nome": r["nome"], "aa": r["aa"],
                              "ajustes_de_contraste": r["ajustes_de_contraste"], "claro": r["claro"],
                              "tipografia": r["tipografia"]}
            except Exception as e:  # noqa: BLE001
                importacao = {"ok": False, "origem": origem, "erro": str(e)}
    ctx.anexar("importacao_bi_html.json", {"tema_em_uso": em_uso, "temas_da_ferramenta": sorted(secoes),
                                          "importacao": importacao})
    certo = da_ferramenta is not None
    ajustes = len(importacao.get("ajustes_de_contraste") or [])
    resumo = (f"{pl(len(secoes), 'tema devolvido', 'temas devolvidos')} por pbix_get_theme; "
              + (f"o tema em uso ({em_uso.get('name')}) está entre eles" if certo else
                 f"o tema em uso ({em_uso.get('name')}, {em_uso.get('type')}) não está entre eles")
              + (f"; importado ({origem}) como design system do bi-html com contraste AA e {pl(ajustes, 'ajuste')} de cor"
                 if importacao["ok"] else f"; importação no bi-html falhou: {importacao.get('erro')}"))
    return {"status": "testada", "classificacao": "I" if certo and importacao["ok"] else "P", "resumo": resumo,
            "medidas": {"temas": len(secoes), "tema_em_uso_na_ferramenta": certo, "importado": importacao["ok"],
                        "ajustes": ajustes}}


def visuais_personalizados(ctx) -> dict:
    ctx.anexar("pbix_list_resources.txt", ctx.ferramenta("pbix_list_resources"))
    with ctx.medir("tempo_conferencia_s"):
        relatorio = ctx.json_zip("Report/definition/report.json") if "Report/definition/report.json" in ctx.nomes else {}
        pacotes = [i for p in relatorio.get("resourcePackages", []) for i in p.get("items", [])
                   if "customvisual" in (i.get("type") or "").lower()]
        pastas = sorted({n.split("/")[2] for n in ctx.nomes if n.startswith("Report/CustomVisuals/")})
        tipos = {_tipo(v) for p in ctx.paginas() for v in p["visuais"]}
        fora = sorted(t for t in tipos if t not in BLOCOS and t not in NATIVOS_SEM_BLOCO and t != "grupo")
    ctx.anexar("deteccao.json", {"pacotes_custom_visual": pacotes, "pastas_CustomVisuals": pastas,
                                 "tipos_fora_da_lista_nativa": fora, "tipos": sorted(tipos)})
    if not pacotes and not pastas and not fora:
        return {"status": "sem_elemento", "classificacao": None,
                "resumo": f"nenhum visual personalizado ({len(tipos)} tipos de visual, todos nativos)"}
    return {"status": "testada", "classificacao": "N",
            "resumo": f"{len(pacotes) or len(fora)} visuais personalizados detectados; viram bloco equivalente ou espaço reservado",
            "medidas": {"personalizados": len(pacotes) or len(fora)}}


def rls(ctx) -> dict:
    saida = ctx.ferramenta("pbix_get_rls_roles")
    ctx.anexar("pbix_get_rls_roles.txt", saida)
    ray = ctx.ray()
    with ctx.medir("tempo_conferencia_s"):
        papeis = ray.rls.to_dict("records") if len(ray.rls) else []
    sem = "No RLS roles" in _mensagem(saida).get("message", "")
    if sem and not papeis:
        return {"status": "sem_elemento", "classificacao": None,
                "resumo": "nenhum papel de RLS no arquivo (pbix-mcp e pbixray concordam)"}
    return {"status": "testada", "classificacao": "P",
            "resumo": f"{len(papeis)} regras de RLS lidas; a atribuição de pessoas a papéis fica no serviço"}


FUNCOES = {"modo": modo, "dados": dados, "modelo": modelo, "dax_texto": dax_texto, "dax_calculo": dax_calculo,
           "m": m, "layout": layout, "filtros": filtros, "tema": tema,
           "visuais_personalizados": visuais_personalizados, "rls": rls}


def filho(elemento: str, apelido: str, caminho: str, destino: str) -> None:
    import logging
    logging.disable(logging.WARNING)
    t = time.perf_counter()
    import pbix_mcp.server as servidor
    aberto = servidor.pbix_open(caminho, apelido)
    tempo_abrir = round(time.perf_counter() - t, 3)
    ctx = Contexto(apelido, caminho, elemento)
    if elemento == "modo":
        ctx.anexar("pbix_open.txt", aberto)
    r = {"status": "erro", "resumo": ""}
    try:
        r = FUNCOES[elemento](ctx)
    except Exception as e:  # noqa: BLE001
        r = {"status": "erro", "classificacao": None, "resumo": f"{type(e).__name__}: {e}"}
    r.update(ctx.tempos)
    r.update({"tempo_abrir_s": tempo_abrir, "pico_rss_mb": pico_rss_mb(), "anexos": ctx.anexos})
    Path(destino).write_text(json.dumps(r, ensure_ascii=False, default=str), encoding="utf-8")


# ----------------------------------------------------------------------------------------
# Processo pai: roda tudo e consolida a matriz
# ----------------------------------------------------------------------------------------

def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _maquina() -> str:
    cpu = platform.processor() or platform.machine()
    memoria = None
    try:
        cpu = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip() or cpu
        memoria = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip())
    except (OSError, ValueError):
        pass
    return f"{cpu}, {round(memoria / 2**30)} GB, {platform.system()} {platform.release()}" if memoria else cpu


def executar(arquivos: dict[str, Path]) -> dict:
    from importlib.metadata import version
    if SAIDAS.exists():
        shutil.rmtree(SAIDAS)
    SAIDAS.mkdir()
    resultado = {
        "executado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "ambiente": {"python": platform.python_version(), "pbix-mcp": version("pbix-mcp"),
                     "pbixray": version("pbixray"), "duckdb": version("duckdb"), "maquina": _maquina()},
        "arquivos": {},
    }
    for apelido, caminho in arquivos.items():
        info = {"nome": caminho.name, "tamanho_bytes": caminho.stat().st_size, "sha256": _sha256(caminho), "elementos": {}}
        for elemento in ["modo"] + [e for e, _ in ELEMENTOS]:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
                destino = tmp.name
            t = time.perf_counter()
            proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--filho", elemento, apelido,
                                   str(caminho), destino], capture_output=True, text=True)
            total = round(time.perf_counter() - t, 3)
            try:
                r = json.loads(Path(destino).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                r = {"status": "erro", "classificacao": None, "resumo": ocultar(proc.stderr[-800:], [str(caminho)])}
            Path(destino).unlink(missing_ok=True)
            r["tempo_processo_s"] = total
            print(f"{apelido:10} {elemento:24} {str(r.get('status') or r.get('modo')):12} {total:7.2f}s {r.get('pico_rss_mb', 0):7.1f} MB  "
                  f"{r.get('resumo') or r.get('modo')}", flush=True)
            if elemento == "modo":
                info["modo"] = r.get("modo")
                info["deteccao_do_modo"] = r
            else:
                info["elementos"][elemento] = r
        resultado["arquivos"][apelido] = info
    resultado["matriz"] = consolidar(resultado)
    RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    MATRIZ.write_text(gerar_matriz(resultado), encoding="utf-8")
    return resultado


ORDEM = {"N": 0, "P": 1, "I": 2}


def consolidar(resultado: dict) -> dict:
    """Uma célula por elemento × modo: testada (com a pior classificação entre os arquivos) ou não."""
    matriz = {}
    for elemento, _ in ELEMENTOS:
        linha = {}
        for i, (modo_id, _) in enumerate(MODOS):
            arquivos = {a: info for a, info in resultado["arquivos"].items() if info.get("modo") == modo_id}
            celula = {"documental": DOCUMENTAL[elemento][i], "arquivos": sorted(arquivos)}
            if not arquivos:
                celula.update({"status": "nao_testada",
                               "motivo": "nenhum dos arquivos enviados está neste modo"})
            else:
                rs = {a: info["elementos"][elemento] for a, info in arquivos.items()}
                testados = {a: r for a, r in rs.items() if r.get("status") == "testada"}
                erros = {a: r for a, r in rs.items() if r.get("status") == "erro"}
                if testados:
                    classe = min((r["classificacao"] for r in testados.values()), key=lambda c: ORDEM[c])
                    celula.update({"status": "testada", "classificacao": classe, "testada_em": sorted(testados),
                                   "sem_elemento_em": sorted(a for a in rs if rs[a].get("status") == "sem_elemento")})
                elif erros:
                    celula.update({"status": "erro", "motivo": "; ".join(f"{a}: {r['resumo']}" for a, r in erros.items())})
                else:
                    celula.update({"status": "sem_elemento",
                                   "motivo": "nenhum dos arquivos tem este elemento; a detecção rodou e voltou vazia"})
            linha[modo_id] = celula
        matriz[elemento] = linha
    return matriz


def _celula(c: dict) -> str:
    if c["status"] == "testada":
        return f"**{c['classificacao']}** · testada ({len(c['testada_em'])} de {len(c['arquivos'])})"
    if c["status"] == "sem_elemento":
        return f"— · sem o elemento nos {len(c['arquivos'])} arquivos (documental: {c['documental']})"
    if c["status"] == "erro":
        return "erro na ferramenta"
    return f"não testada (documental: {c['documental']})"


def br(x: float, casas: int = 2) -> str:
    """Número com vírgula decimal e ponto de milhar."""
    return f"{x:,.{casas}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def gerar_matriz(resultado: dict) -> str:
    """MATRIZ.md a partir de resultados.json (determinístico: o teste regenera e compara)."""
    amb, arqs, matriz = resultado["ambiente"], resultado["arquivos"], resultado["matriz"]
    L = ["# F6 — prova de conceito .pbix: matriz 5.1 testada", "",
         "Gerado por `provas/f6/executar.py` a partir de `resultados.json`; não edite à mão.", "",
         f"**Execução:** {resultado['executado_em']} · Python {amb['python']} · pbix-mcp {amb['pbix-mcp']} · "
         f"pbixray {amb['pbixray']} · DuckDB {amb['duckdb']} · {amb['maquina']}", "",
         "**Escala:** **I** = integral, **P** = parcial, **N** = não extraível. Uma célula testada leva a pior "
         "classificação entre os arquivos daquele modo; o detalhe por arquivo e a saída das ferramentas estão abaixo. "
         "Célula não testada mantém a classificação documental do plano, entre parênteses.", "",
         "## Arquivos", "", "| Apelido | Arquivo | Tamanho | SHA-256 (12) | Modo detectado |", "|---|---|---|---|---|"]
    for a, info in arqs.items():
        L.append(f"| `{a}` | {info['nome']} | {br(info['tamanho_bytes'] / 2**20, 1)} MB | `{info['sha256'][:12]}` | "
                 f"{dict(MODOS).get(info['modo'], info['modo'])} |")
    L += ["", "## Matriz", "", "| Elemento | " + " | ".join(n for _, n in MODOS) + " |", "|---|---|---|---|"]
    for e, nome in ELEMENTOS:
        L.append(f"| {nome} | " + " | ".join(_celula(matriz[e][m]) for m, _ in MODOS) + " |")
    sem_modo = [n for m, n in MODOS if matriz[ELEMENTOS[0][0]][m]["status"] == "nao_testada"]
    if sem_modo:
        L += ["", f"**{' e '.join(sem_modo)}:** nenhum dos arquivos enviados está nesse modo, então essas colunas "
              "continuam com a base documental. Para testá-las, basta rodar o script de novo com um .pbix em cada modo."]
    L += ["", "## Resultado por arquivo", ""]
    for e, nome in ELEMENTOS:
        L += [f"### {nome}", "", "| Arquivo | Resultado | Classificação | Saída anexada |", "|---|---|---|---|"]
        for a, info in arqs.items():
            r = info["elementos"][e]
            anexos = " · ".join(f"[{Path(x).name.split('__', 1)[-1]}]({x})" for x in r.get("anexos", []))
            L.append(f"| `{a}` | {r.get('resumo', '')} | {r.get('classificacao') or '—'} | {anexos} |")
        L.append("")
    L += ["## Tempo e memória", "",
          "Cada célula roda num processo próprio. *Abrir* é o `pbix_open`; *ferramenta* soma as chamadas do pbix-mcp "
          "do elemento; *conferência* soma o segundo leitor (pbixray), o DuckDB e a leitura do JSON do relatório; "
          "*pico* é o pico de memória residente do processo inteiro (abrir + ferramenta + conferência).", "",
          "| Arquivo | Elemento | Abrir (s) | Ferramenta (s) | Conferência (s) | Processo (s) | Pico (MB) |",
          "|---|---|---|---|---|---|---|"]
    for a, info in arqs.items():
        linhas = [("Detecção do modo", info["deteccao_do_modo"])] + [(n, info["elementos"][e]) for e, n in ELEMENTOS]
        for nome, r in linhas:
            L.append(f"| `{a}` | {nome} | {br(r.get('tempo_abrir_s', 0))} | {br(r.get('tempo_ferramenta_s', 0))} | "
                     f"{br(r.get('tempo_conferencia_s', 0))} | {br(r.get('tempo_processo_s', 0))} | "
                     f"{br(r.get('pico_rss_mb', 0), 0)} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--filho":
        filho(*sys.argv[2:6])
        return
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--arquivo", action="append", default=[], metavar="APELIDO=CAMINHO",
                    help="arquivo .pbix a testar (repita para vários)")
    args = ap.parse_args()
    if not args.arquivo:
        MATRIZ.write_text(gerar_matriz(json.loads(RESULTADOS.read_text(encoding="utf-8"))), encoding="utf-8")
        print(f"regenerado: {MATRIZ.relative_to(RAIZ)}")
        return
    arquivos = {}
    for item in args.arquivo:
        apelido, _, caminho = item.partition("=")
        p = Path(caminho).expanduser()
        if not apelido or not p.is_file():
            ap.error(f"arquivo inválido: {item}")
        arquivos[apelido] = p
    executar(arquivos)
    print(f"gravado: {RESULTADOS.relative_to(RAIZ)} e {MATRIZ.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
