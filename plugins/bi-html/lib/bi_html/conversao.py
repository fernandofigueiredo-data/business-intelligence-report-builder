"""
conversao.py — Fluxo 2, via (a): um .pbix em modo de importação vira projeto do bi-html.

Etapas (ferramenta `converter_pbix`, comando /bi-html:pbix):

1. **Extração**, num processo à parte (scripts/pbix_externo.py, com pbix-mcp e pbixray): modo de
   armazenamento, tabelas em parquet com a contagem conferida e o modelo (relações, medidas).
   DirectQuery e conexão dinâmica param aqui, com a explicação e a via (b).
2. **Relatório**, lido do pacote sem bibliotecas de terceiros: páginas, visuais (tipo, posição,
   campos, título), filtros e o tema em uso (formato PBIR).
3. **Tabela convertida** (`saidas/bi/pbix/plano.parquet`): o modelo do bi-html tem uma fonte só,
   então cada tabela agregada pelas medidas (os fatos) entra com as colunas das tabelas ligadas a
   ela pelas relações (lado "um", em cadeia), e as partes são empilhadas com a coluna
   `tabela_de_origem`. Cada métrica filtra a própria parte, então não há dupla contagem; colunas
   viram `Tabela.Coluna`.
4. **Medidas**: `dax.py` classifica cada medida (traduzida, texto ou não traduzida); as traduzidas e
   as agregações implícitas dos visuais viram `modelo/metricas.yaml`.
5. **Specs**: uma por página (`dashboard/paginas/<pagina>.json`), visual a visual, com o bloco
   equivalente; a primeira página com blocos vira `dashboard/spec.json`.
6. **Equivalência**: cada medida traduzida é avaliada pelo motor DAX do pbix-mcp (a referência) e
   pela camada de métricas numa amostra de contextos de filtro; agregações implícitas, que o
   pbix-mcp não avalia, são conferidas contra SQL sobre a tabela original. Métrica que não passa
   leva o selo "não validada" na descrição.
7. **Fidelidade**: `saidas/bi/pbix/conversao.json` e `fidelidade.md`, com cada tabela, medida,
   página e visual, e as páginas renderizadas em `saidas/bi/paginas/`.

Diferenças de semântica conhecidas (aparecem como ressalva no relatório): filtro em tabela que
não se liga ao fato esvazia a métrica no bi-html (no Power BI, não filtra); o filtro de um
CALCULATE se soma ao do leitor (no Power BI, substitui o da mesma coluna).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from . import dax
from .ingestao import PASTA_BI, ErroDeLeitura, ler_manifesto
from .modelo import ARQUIVO_MODELO, VERSAO, literal, q

PASTA = PASTA_BI / "pbix"
PLANO = PASTA / "plano.parquet"
RELATORIO = PASTA / "conversao.json"
FIDELIDADE = PASTA / "fidelidade.md"
PAGINAS_SPEC = Path("dashboard") / "paginas"
PAGINAS_HTML = PASTA_BI / "paginas"
ORIGEM = "tabela_de_origem"
DATAS_AUTO = ("LocalDateTable", "DateTableTemplate")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pbix_externo.py"
DEPENDENCIAS = ("pbix-mcp==0.9.153", "pbixray==0.15.5", "duckdb")
MARCA = "# Modelo convertido de um .pbix pelo bi-html"
SELO = " (não validada)"
MAX_VALORES_FILTRO = 30
TOLERANCIA = 1e-9

# Função da agregação implícita de um visual (Power BI) → tipo de métrica.
IMPLICITAS = {0: ("soma", "Soma"), 1: ("media", "Média"), 2: ("contagem_distinta", "Contagem distinta"),
              3: ("minimo", "Mínimo"), 4: ("maximo", "Máximo"), 5: ("contagem", "Contagem")}
NIVEIS = {"ano": "ano", "year": "ano", "trimestre": "trimestre", "quarter": "trimestre", "mês": "mes",
          "mes": "mes", "month": "mes", "dia": "dia", "day": "dia"}
DECORATIVOS = {"textbox", "shape", "basicShape", "image", "actionButton", "pageNavigator", "bookmarkNavigator", "grupo"}
SEGMENTACOES = {"slicer", "advancedSlicerVisual"}
PAPEIS_IGNORADOS = {"Tooltips"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
       "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
NUMERICOS = ("int", "float", "uint")


class ErroDeConversao(ErroDeLeitura):
    pass


# ---------------------------------------------------------------- nomes e textos sem algarismos

UNIDADES = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
            "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
DEZENAS = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos",
            "oitocentos", "novecentos"]
ORDINAIS = ["", "primeiro", "segundo", "terceiro", "quarto", "quinto", "sexto", "sétimo", "oitavo", "nono", "décimo"]


def por_extenso(n: int) -> str:
    """Número inteiro por extenso em português (até 999.999)."""
    if n < 20:
        return UNIDADES[n]
    if n < 100:
        d, u = divmod(n, 10)
        return DEZENAS[d] + (f" e {UNIDADES[u]}" if u else "")
    if n < 1000:
        c, r = divmod(n, 100)
        if n == 100:
            return "cem"
        return CENTENAS[c] + (f" e {por_extenso(r)}" if r else "")
    if n < 1_000_000:
        m, r = divmod(n, 1000)
        cabeca = "mil" if m == 1 else f"{por_extenso(m)} mil"
        return cabeca + ((" e " if r < 100 or r % 100 == 0 else " ") + por_extenso(r) if r else "")
    return " ".join(UNIDADES[int(c)] for c in str(n))


def sem_algarismos(texto: str) -> str:
    """Texto para a spec, que não aceita algarismos: '1º turno' → 'primeiro turno', 'Top 10' → 'Top dez'."""
    def ordinal(m):
        n = int(m.group(1))
        palavra = ORDINAIS[n] if 0 < n < len(ORDINAIS) else por_extenso(n)
        return palavra[:-1] + "a" if m.group(2) == "ª" else palavra

    texto = re.sub(r"(\d+)\s*([ºª°])", ordinal, texto or "")
    texto = re.sub(r"\d+", lambda m: f" {por_extenso(int(m.group(0)))} ", texto)
    texto = re.sub(r"\s+([,.;:!?)])", r"\1", texto)
    return re.sub(r"\s+", " ", texto).strip()[:120] or "Sem título"


def ident(texto: str) -> str:
    """Id do bi-html (minúsculas e sublinhado, sem algarismos) a partir de um nome do Power BI."""
    base = sem_algarismos(str(texto).replace("%", " pct "))
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z]+", "_", base).strip("_")[:44].strip("_")
    return base if base and base[0].isalpha() else ("m_" + base).strip("_")


class Nomes:
    """Ids únicos para métricas, dimensões e blocos."""

    def __init__(self):
        self.usados: set[str] = set()

    def novo(self, texto: str) -> str:
        base = ident(texto) or "campo"
        nome, i = base, 0
        while nome in self.usados:
            i += 1
            nome = f"{base}_{'abcdefghijklmnopqrstuvwxyz'[i % 26] * (i // 26 + 1)}"
        self.usados.add(nome)
        return nome


# ---------------------------------------------------------------- processo externo

def executar_externo(*args: str, timeout: int = 900) -> str:
    """Roda scripts/pbix_externo.py no ambiente próprio (pbix-mcp exige mcp<2)."""
    if not shutil.which("uv"):
        raise ErroDeConversao("a leitura de .pbix precisa do uv", ["instale o uv: https://docs.astral.sh/uv/"])
    cmd = ["uv", "run", "--quiet", "--no-project", "--python", "3.12"]
    for d in DEPENDENCIAS:
        cmd += ["--with", d]
    cmd += ["python", "-I", str(SCRIPT), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode:
        ultimas = [l for l in proc.stderr.strip().splitlines() if l.strip()][-3:]
        raise ErroDeConversao("a leitura do .pbix falhou", ultimas or ["sem mensagem do processo"])
    return proc.stdout


def extrair(projeto: Path, caminho: Path) -> dict:
    destino = Path(projeto) / PASTA
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    executar_externo("extrair", str(caminho), str(destino))
    return json.loads((destino / "extracao.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- relatório (PBIR)

def _literal_pbi(valor) -> str | None:
    if not isinstance(valor, str):
        return None
    return valor[1:-1].replace("''", "'") if valor.startswith("'") and valor.endswith("'") else valor


def _titulo(visual: dict) -> str | None:
    for chave in ("visualContainerObjects", "vcObjects", "objects"):
        for item in (visual.get(chave) or {}).get("title") or []:
            texto = (((item.get("properties") or {}).get("text") or {}).get("expr") or {}).get("Literal", {}).get("Value")
            if texto:
                return _literal_pbi(texto)
    return None


def _entidade(expr: dict, apelidos: dict | None = None) -> str | None:
    ref = (expr or {}).get("SourceRef") or {}
    return ref.get("Entity") or (apelidos or {}).get(ref.get("Source"))


def _campo(f: dict, apelidos: dict | None = None) -> dict:
    """Campo de um visual: coluna, medida, agregação implícita ou nível de hierarquia de data.
    No PBIR a tabela vem em `Entity`; no layout legado, por apelido (`Source`) do prototypeQuery."""
    if "Column" in f:
        return {"tipo": "coluna", "tabela": _entidade(f["Column"].get("Expression"), apelidos),
                "coluna": f["Column"].get("Property")}
    if "Measure" in f:
        return {"tipo": "medida", "tabela": _entidade(f["Measure"].get("Expression"), apelidos),
                "nome": f["Measure"].get("Property")}
    if "Aggregation" in f:
        col = (f["Aggregation"].get("Expression") or {}).get("Column") or {}
        return {"tipo": "agregacao", "tabela": _entidade(col.get("Expression"), apelidos), "coluna": col.get("Property"),
                "funcao": f["Aggregation"].get("Function")}
    if "HierarchyLevel" in f:
        h = (f["HierarchyLevel"].get("Expression") or {}).get("Hierarchy") or {}
        fonte = (h.get("Expression") or {}).get("PropertyVariationSource")
        if fonte:
            return {"tipo": "nivel", "tabela": _entidade(fonte.get("Expression"), apelidos), "coluna": fonte.get("Property"),
                    "nivel": f["HierarchyLevel"].get("Level")}
        return {"tipo": "hierarquia", "nome": h.get("Hierarchy"), "nivel": f["HierarchyLevel"].get("Level")}
    return {"tipo": "outro"}


def _ordem(campo: dict, descendente: bool) -> dict | None:
    if campo["tipo"] in ("coluna", "nivel"):
        return {"por": "eixo", "descendente": descendente}
    if campo["tipo"] in ("medida", "agregacao"):
        return {"por": "valor", "descendente": descendente}
    return None


def _visual(d: dict) -> dict:
    v = d.get("visual") or {}
    campos = []
    for papel, estado in ((v.get("query") or {}).get("queryState") or {}).items():
        for proj in estado.get("projections") or []:
            campos.append({"papel": papel, **_campo(proj.get("field") or {})})
    ordem = None
    for item in ((v.get("query") or {}).get("sortDefinition") or {}).get("sort") or []:
        ordem = _ordem(_campo(item.get("field") or {}), item.get("direction") == "Descending")
        break
    return {"id": d.get("name"), "tipo": v.get("visualType") or ("grupo" if "visualGroup" in d else "desconhecido"),
            "posicao": d.get("position") or {}, "oculto": bool(d.get("isHidden")), "titulo": _titulo(v),
            "campos": campos, "ordem": ordem, "filtros": len((d.get("filterConfig") or {}).get("filters") or [])}


def _visual_legado(vc: dict) -> dict:
    c = json.loads(vc.get("config") or "{}")
    sv = c.get("singleVisual") or {}
    consulta = sv.get("prototypeQuery") or {}
    apelidos = {f.get("Name"): f.get("Entity") for f in consulta.get("From") or []}
    por_nome = {sel.get("Name"): sel for sel in consulta.get("Select") or []}
    campos = []
    for papel, projecoes in (sv.get("projections") or {}).items():
        for proj in projecoes or []:
            sel = por_nome.get(proj.get("queryRef"))
            if sel:
                campos.append({"papel": papel, **_campo(sel, apelidos)})
    try:
        filtros = len(json.loads(vc.get("filters") or "[]"))
    except json.JSONDecodeError:
        filtros = 0
    tipo = sv.get("visualType") or ("grupo" if "singleVisualGroup" in c else "desconhecido")
    ordem = None
    for item in consulta.get("OrderBy") or []:
        ordem = _ordem(_campo(item.get("Expression") or {}, apelidos), item.get("Direction") == 2)
        break
    return {"id": c.get("name"), "tipo": tipo, "oculto": bool(sv.get("display", {}).get("mode") == "hidden"),
            "posicao": {k: vc.get(k) for k in ("x", "y", "width", "height")}, "titulo": _titulo(sv),
            "campos": campos, "ordem": ordem, "filtros": filtros}


def _chave_tema(nome: str | None) -> str:
    return re.sub(r"\.json$", "", Path(nome or "").name)


def _layout_legado(z: zipfile.ZipFile) -> dict:
    bruto = z.read("Report/Layout")
    for codificacao in ("utf-16-le", "utf-8-sig"):
        try:
            texto = bruto.decode(codificacao)
            if texto.lstrip().startswith("{"):
                return json.loads(texto)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ErroDeConversao("o layout legado do relatório (Report/Layout) não pôde ser lido")


def ler_relatorio(caminho: Path) -> dict:
    """Páginas, visuais e tema em uso, direto do pacote: PBIR (Report/definition) ou layout legado
    (Report/Layout), sem bibliotecas de terceiros."""
    z = zipfile.ZipFile(caminho)
    nomes = set(z.namelist())
    ler = lambda n: json.loads(z.read(n).decode("utf-8-sig"))  # noqa: E731
    pbir = "Report/definition/pages/pages.json" in nomes
    legado = _layout_legado(z) if not pbir and "Report/Layout" in nomes else None
    if pbir:
        relatorio = ler("Report/definition/report.json") if "Report/definition/report.json" in nomes else {}
    else:
        relatorio = json.loads((legado or {}).get("config") or "{}")
    colecao = relatorio.get("themeCollection") or {}
    em_uso = colecao.get("customTheme") or colecao.get("baseTheme") or {}
    arquivo_tema = next((n for n in sorted(nomes) if n.startswith("Report/StaticResources/")
                         and _chave_tema(n) == _chave_tema(em_uso.get("name"))), None)
    tema = {"nome": em_uso.get("name"), "tipo": em_uso.get("type"), "arquivo": arquivo_tema,
            "json": z.read(arquivo_tema).decode("utf-8-sig") if arquivo_tema else None}
    paginas = []
    if pbir:
        for pid in ler("Report/definition/pages/pages.json").get("pageOrder", []):
            base = f"Report/definition/pages/{pid}/"
            p = ler(base + "page.json")
            visuais = [_visual(ler(n)) for n in sorted(nomes) if n.startswith(base + "visuals/") and n.endswith("/visual.json")]
            paginas.append({"id": pid, "nome": p.get("displayName") or pid, "largura": p.get("width") or 1280,
                            "altura": p.get("height") or 720, "tipo": p.get("type"),
                            "oculta": p.get("visibility") == "HiddenInViewMode" or p.get("type") == "Tooltip",
                            "filtros": len((p.get("filterConfig") or {}).get("filters") or []), "visuais": visuais})
        formato = "PBIR"
    elif legado is not None:
        for sec in sorted(legado.get("sections") or [], key=lambda x: x.get("ordinal", 0)):
            cfg = json.loads(sec.get("config") or "{}")
            try:
                filtros = len(json.loads(sec.get("filters") or "[]"))
            except json.JSONDecodeError:
                filtros = 0
            paginas.append({"id": sec.get("name"), "nome": sec.get("displayName") or sec.get("name"),
                            "largura": sec.get("width") or 1280, "altura": sec.get("height") or 720,
                            "tipo": cfg.get("type"), "oculta": cfg.get("visibility") == 1 or sec.get("displayOption") == 3,
                            "filtros": filtros,
                            "visuais": [_visual_legado(vc) for vc in sec.get("visualContainers") or []]})
        formato = "legado (Report/Layout)"
    else:
        formato = "sem relatório"
    return {"formato": formato, "paginas": paginas, "tema": tema}


# ---------------------------------------------------------------- relações e tabela convertida

def _alcance(relacoes: list[dict]):
    """Função tabela → tabelas que a filtram: ela mesma e o lado "um" das relações, em cadeia."""
    ativas = [r for r in relacoes if r["ativa"] and (r.get("cardinalidade") or "M:1") in ("M:1", "1:1")
              and not r["para_tabela"].startswith(DATAS_AUTO)]

    def alcance(t: str) -> set[str]:
        vistos, fila = {t}, [t]
        while fila:
            x = fila.pop()
            for r in ativas:
                if r["de_tabela"] == x and r["para_tabela"] not in vistos:
                    vistos.add(r["para_tabela"])
                    fila.append(r["para_tabela"])
        return vistos
    return alcance, ativas


def _bases(no: dict):
    if no["no"] == "base":
        yield no
    for k in ("num", "den", "base"):
        if isinstance(no.get(k), dict):
            yield from _bases(no[k])


def montar_plano(projeto: Path, extracao: dict, fatos: list[str], calculadas: dict[str, dict[str, str]],
                 relacoes: list[dict]) -> dict:
    """Grava plano.parquet: uma parte por fato, com as colunas das tabelas ligadas, empilhadas."""
    import duckdb

    projeto = Path(projeto)
    tabelas = {t["nome"]: t for t in extracao["tabelas"]}
    arq = lambda t: literal((projeto / PASTA / tabelas[t]["parquet"]).as_posix())  # noqa: E731
    partes, contagem = [], {}
    for fato in fatos:
        apelidos, juncoes, ordem = {fato: "t0"}, [], [fato]
        fila = [fato]
        while fila:
            x = fila.pop(0)
            for r in relacoes:
                y = r["para_tabela"]
                if r["de_tabela"] == x and y not in apelidos and tabelas.get(y, {}).get("parquet"):
                    apelidos[y] = f"t{len(apelidos)}"
                    ordem.append(y)
                    fila.append(y)
                    tipo_a = tabelas[x]["colunas"].get(r["de_coluna"])
                    tipo_b = tabelas[y]["colunas"].get(r["para_coluna"])
                    a, b = f"{apelidos[x]}.{q(r['de_coluna'])}", f"{apelidos[y]}.{q(r['para_coluna'])}"
                    cond = f"{a} = {b}" if tipo_a == tipo_b else f"CAST({a} AS VARCHAR) = CAST({b} AS VARCHAR)"
                    juncoes.append(f"LEFT JOIN read_parquet({arq(y)}) {apelidos[y]} ON {cond}")
        selecao = [f"{literal(fato)} AS {q(ORIGEM)}"]
        for t in ordem:
            selecao += [f"{apelidos[t]}.{q(c)} AS {q(f'{t}.{c}')}" for c in tabelas[t]["colunas"]]
        interno = f"SELECT {', '.join(selecao)} FROM read_parquet({arq(fato)}) t0 " + " ".join(juncoes)
        extras = "".join(f", {sql} AS {q(nome)}" for nome, sql in (calculadas.get(fato) or {}).items())
        partes.append(f"SELECT *{extras} FROM ({interno})")
        contagem[fato] = {"linhas_tabela": tabelas[fato]["linhas_extraidas"], "tabelas_ligadas": ordem[1:]}
    destino = projeto / PLANO
    con = duckdb.connect()
    try:
        uniao = " UNION ALL BY NAME ".join(f"({p})" for p in partes)
        con.execute(f"COPY ({uniao}) TO {literal(destino.as_posix())} (FORMAT PARQUET)")
        for fato, n in con.execute(f"SELECT {q(ORIGEM)}, count(*) FROM read_parquet({literal(destino.as_posix())}) "
                                   f"GROUP BY 1").fetchall():
            contagem[fato]["linhas_no_plano"] = n
        tipos = {c: t for c, t, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet({literal(destino.as_posix())})").fetchall()}
    finally:
        con.close()
    for fato, c in contagem.items():
        c["iguais"] = c.get("linhas_no_plano") == c["linhas_tabela"]
    return {"partes": contagem, "colunas": tipos}


# ---------------------------------------------------------------- medidas → métricas

def _formato(formato_pbi: str | None, tipo: str, coluna_tipo: str | None = None) -> str:
    f = formato_pbi or ""
    if "%" in f:
        return "percentual"
    if "R$" in f or "$" in f or "€" in f:
        return "moeda"
    if tipo in ("contagem", "contagem_distinta"):
        return "inteiro"
    if tipo == "participacao":
        return "percentual"
    if re.search(r"[0#]\.0", f) or re.search(r"[0#],0\.0", f):
        return "decimal"
    if f.strip() in ("0", "#,0", "#,##0", "#,0;-#,0;#,0"):
        return "inteiro"
    if tipo == "soma" and coluna_tipo and coluna_tipo.upper().startswith(("BIGINT", "INTEGER", "HUGEINT", "SMALLINT")):
        return "inteiro"
    return "decimal"


class Materializador:
    """Dá ids às árvores traduzidas e escreve as definições de métrica do modelo."""

    def __init__(self, tradutor: dax.Tradutor, medidas: dict[str, dict], nomes: Nomes, tipos_plano: dict[str, str]):
        self.tr, self.medidas, self.nomes, self.tipos = tradutor, medidas, nomes, tipos_plano
        self.metricas: dict[str, dict] = {}
        self.calculadas: dict[str, dict[str, str]] = {}
        self.de_medida: dict[str, dict] = {}

    def medida(self, nome: str) -> dict | None:
        """{'metrica': id, 'escala': fator} da medida traduzida, ou None."""
        if nome in self.de_medida:
            return self.de_medida[nome]
        r = self.tr.traduzir(nome)
        if r["classe"] != "traduzida":
            return None
        no, fator = r["no"], 1.0
        if no["no"] == "escala":
            no, fator = no["base"], no["fator"]
        alvo = None
        if no.get("ref") and no["ref"] != nome:
            dep = self.medida(no["ref"])
            if dep and dep["escala"] == 1.0:
                alvo = dep["metrica"]
        if alvo is None:
            alvo = self._no(no, nome, self.medidas[nome].get("formato") if fator == 1.0 else None, topo=True)
        self.de_medida[nome] = {"metrica": alvo, "escala": fator}
        return self.de_medida[nome]

    def _no(self, no: dict, nome: str, formato_pbi: str | None, topo=False) -> str:
        if not topo and no.get("ref"):
            dep = self.medida(no["ref"])
            if dep and dep["escala"] == 1.0:
                return dep["metrica"]
        mid = self.nomes.novo(nome)
        if no["no"] == "base":
            d = {"descricao": nome, "tipo": no["tipo"]}
            if no["calc"]:
                coluna = f"calc.{mid}"
                self.calculadas.setdefault(no["fato"], {})[coluna] = no["calc"]
                d["coluna"] = coluna
            elif no["coluna"]:
                d["coluna"] = no["coluna"]
            d["filtro"] = [{"coluna": ORIGEM, "operador": "igual", "valor": no["fato"]}] + no["filtro"]
            d["formato"] = _formato(formato_pbi, no["tipo"], self.tipos.get(no.get("coluna") or ""))
            d["_fato"] = no["fato"]
        elif no["no"] == "razao":
            num = self._no(no["num"], f"{nome} numerador", None)
            den = self._no(no["den"], f"{nome} denominador", None)
            d = {"descricao": nome, "tipo": "razao", "numerador": num, "denominador": den,
                 "formato": _formato(formato_pbi, "razao"), "_fato": self.metricas[num]["_fato"]}
        elif no["no"] == "participacao":
            base = self._no(no["base"], f"{nome} base", None)
            d = {"descricao": nome, "tipo": "participacao", "metrica": base, "formato": "percentual",
                 "_fato": self.metricas[base]["_fato"], "_eixo": no.get("eixo") or []}
        else:
            raise dax.NaoTraduzivel("escala dentro de outra expressão")
        self.metricas[mid] = d
        return mid

    def implicita(self, tabela: str, coluna: str, funcao: int) -> str | None:
        chave = f"__implicita__{tabela}.{coluna}.{funcao}"
        if chave in self.de_medida:
            return self.de_medida[chave]["metrica"]
        if funcao not in IMPLICITAS:
            return None
        tipo, rotulo = IMPLICITAS[funcao]
        tipo_pandas = str((self.tr.colunas.get(tabela) or {}).get(coluna) or "")
        if tipo in ("soma", "media", "minimo", "maximo") and not tipo_pandas.lower().startswith(NUMERICOS):
            return None  # primeiro/último texto de uma tabela: não é número
        mid = self.nomes.novo(f"{rotulo} de {coluna}")
        self.metricas[mid] = {"descricao": f"{rotulo} de {coluna}", "tipo": tipo, "coluna": f"{tabela}.{coluna}",
                              "filtro": [{"coluna": ORIGEM, "operador": "igual", "valor": tabela}],
                              "formato": _formato(None, tipo, self.tipos.get(f"{tabela}.{coluna}")), "_fato": tabela,
                              "_implicita": {"tabela": tabela, "coluna": coluna, "funcao": funcao}}
        self.de_medida[chave] = {"metrica": mid, "escala": 1.0}
        return mid


# ---------------------------------------------------------------- dimensões, blocos e specs

def _granularidade(nivel: str | None) -> str | None:
    return NIVEIS.get((nivel or "").strip().lower())


def _colunas_de_dimensao(relatorio: dict) -> list[tuple[str, str, str | None]]:
    vistas = []
    for p in relatorio["paginas"]:
        for v in p["visuais"]:
            for c in v["campos"]:
                if c["papel"] in PAPEIS_IGNORADOS:
                    continue
                if c["tipo"] == "coluna":
                    chave = (c["tabela"], c["coluna"], None)
                elif c["tipo"] == "nivel":
                    chave = (c["tabela"], c["coluna"], _granularidade(c["nivel"]))
                else:
                    continue
                if chave not in vistas:
                    vistas.append(chave)
    return vistas


def _largura(posicao: dict, largura_pagina: float) -> str:
    r = (posicao.get("width") or 0) / (largura_pagina or 1280)
    return "um_terco" if r <= 0.4 else "metade" if r <= 0.6 else "dois_tercos" if r <= 0.8 else "inteira"


def _tipo_bloco(tipo_pbi: str, n_dims: int, n_mets: int, tempo: bool) -> tuple[str | None, str | None]:
    """Bloco do bi-html para o tipo de visual; o segundo valor é a ressalva da troca, se houver."""
    if tipo_pbi in ("card", "kpi", "gauge"):
        return "numero_destaque", ("o medidor virou número em destaque" if tipo_pbi == "gauge" else None)
    if tipo_pbi in ("cardVisual", "multiRowCard"):
        return ("faixa_kpis" if n_mets > 1 else "numero_destaque"), None
    if tipo_pbi in ("lineChart", "areaChart"):
        return ("linha_tempo", None) if tempo else ("barras_agrupadas", "a linha virou barras: o eixo não é data")
    if tipo_pbi == "stackedAreaChart":
        return ("area_empilhada", None) if tempo and n_dims == 2 else ("barras_agrupadas", "a área virou barras")
    if tipo_pbi in ("barChart", "clusteredBarChart", "stackedBarChart", "hundredPercentStackedBarChart"):
        return ("barras_agrupadas", None) if n_dims == 2 else ("barras_ranking", None)
    if tipo_pbi in ("columnChart", "clusteredColumnChart", "stackedColumnChart", "hundredPercentStackedColumnChart",
                    "ribbonChart"):
        return "barras_agrupadas", None
    if tipo_pbi in ("donutChart", "pieChart"):
        return "rosca", None
    if tipo_pbi in ("tableEx", "pivotTable", "table"):
        return "tabela", None
    if tipo_pbi == "waterfallChart":
        return "cascata", None
    if tipo_pbi == "funnel":
        return "funil", None
    if tipo_pbi in ("filledMap", "shapeMap", "azureMap", "map"):
        return "mapa_uf", None
    return None, None


LIMITE_METRICAS = {"numero_destaque": 1, "rosca": 1, "barras_ranking": 1, "mapa_uf": 1, "cascata": 1,
                   "barras_agrupadas": 3, "linha_tempo": 3, "area_empilhada": 1, "faixa_kpis": 6, "tabela": 6, "funil": 6}
SEM_DIMENSAO = {"numero_destaque", "faixa_kpis", "funil"}
UMA_DIMENSAO = {"linha_tempo", "barras_ranking", "rosca", "tabela", "cascata", "mapa_uf"}


class Conversor:
    def __init__(self, projeto: Path, caminho: Path, extracao: dict, relatorio: dict):
        self.projeto, self.caminho, self.ext, self.rel = Path(projeto), Path(caminho), extracao, relatorio
        self.colunas = {t["nome"]: t["colunas"] for t in extracao["tabelas"] if t.get("parquet")}
        self.alcance, self.relacoes = _alcance(extracao["relacoes"])
        self.medidas = {m["nome"]: m for m in extracao["medidas"]}
        self.tr = dax.Tradutor({n: m["expressao"] for n, m in self.medidas.items()}, self.colunas, self.alcance)
        self.nomes = Nomes()
        self.dims: dict[str, dict] = {}
        self.dim_de: dict[tuple, str] = {}

    # -- medidas e fatos

    def classificar(self) -> dict[str, dict]:
        return {n: self.tr.traduzir(n) for n in self.medidas}

    def fatos(self, classes: dict) -> list[str]:
        fatos = {b["fato"] for r in classes.values() if r["classe"] == "traduzida" for b in _bases(r["no"])}
        for p in self.rel["paginas"]:
            for v in p["visuais"]:
                fatos |= {c["tabela"] for c in v["campos"] if c["tipo"] == "agregacao" and c["tabela"] in self.colunas}
        if not fatos:
            maior = max((t for t in self.ext["tabelas"] if t.get("parquet") and not t["datas_automaticas"]),
                        key=lambda t: t["linhas_extraidas"], default=None)
            fatos = {maior["nome"]} if maior else set()
        return sorted(fatos)

    # -- dimensões

    def dimensao(self, tabela: str, coluna: str, gran: str | None, tipos: dict) -> str | None:
        chave = (tabela, coluna, gran)
        if chave in self.dim_de:
            return self.dim_de[chave]
        col = f"{tabela}.{coluna}"
        if col not in tipos or (gran and not tipos[col].startswith(("DATE", "TIMESTAMP"))):
            return None
        if gran is None and tipos[col].startswith(("DATE", "TIMESTAMP")):
            gran = "dia"  # coluna de data no eixo, sem hierarquia: o Power BI mostra a própria data
            chave = (tabela, coluna, gran)
            if chave in self.dim_de:
                self.dim_de[(tabela, coluna, None)] = self.dim_de[chave]
                return self.dim_de[chave]
        mid = self.nomes.novo(coluna if not gran else f"{coluna} {gran}")
        self.dims[mid] = {"coluna": col, "descricao": coluna if not gran else f"{coluna} ({gran})",
                          **({"granularidade": gran} if gran else {})}
        self.dim_de[chave] = mid
        self.dim_de[(tabela, coluna, None if gran == "dia" else gran)] = mid
        return mid

    def tabela_da_dim(self, did: str) -> str:
        return self.dims[did]["coluna"].split(".", 1)[0]


def _valores_distintos(con, arquivo: str, coluna: str) -> int:
    return con.execute(f"SELECT count(DISTINCT {q(coluna)}) FROM read_parquet({literal(arquivo)})").fetchone()[0]


def _blocos_da_pagina(conv: Conversor, mat: Materializador, pagina: dict, classes: dict, con, arquivo: str) -> tuple:
    """Blocos, filtros globais e o relatório de fidelidade de cada visual da página."""
    fidelidade, candidatos, filtros = [], [], []
    tipos = conv.tipos_plano
    visuais = sorted(pagina["visuais"], key=lambda v: ((v["posicao"].get("y") or 0), (v["posicao"].get("x") or 0)))
    for v in visuais:
        item = {"visual": v["id"], "tipo_power_bi": v["tipo"], "titulo": v["titulo"], "bloco": None,
                "status": None, "motivos": [], "medidas": []}
        fidelidade.append(item)
        if v["oculto"]:
            item.update(status="decorativo", motivos=["visual oculto"])
            continue
        if v["tipo"] in DECORATIVOS:
            item.update(status="decorativo", motivos=["texto, forma ou navegação: o bi-html desenha o próprio cabeçalho"])
            continue
        dims_campos = [c for c in v["campos"] if c["tipo"] in ("coluna", "nivel") and c["papel"] not in PAPEIS_IGNORADOS]
        if v["tipo"] in SEGMENTACOES:
            c = dims_campos[0] if dims_campos else None
            gran = _granularidade(c.get("nivel")) if c and c["tipo"] == "nivel" else None
            did = conv.dimensao(c["tabela"], c["coluna"], gran, tipos) if c else None
            if not did:
                item.update(status="nao_convertido", motivos=["segmentação sem coluna na tabela convertida"])
            elif gran:
                item.update(status="nao_convertido", motivos=["segmentação de data: no bi-html o tempo é o período da spec"])
            elif _valores_distintos(con, arquivo, conv.dims[did]["coluna"]) > MAX_VALORES_FILTRO:
                item.update(status="nao_convertido",
                            motivos=["segmentação com valores demais para filtro global (o cubo cresceria demais)"])
            elif len(filtros) >= 4 and did not in filtros:
                item.update(status="nao_convertido", motivos=["a spec aceita até quatro filtros globais"])
            else:
                if did not in filtros:
                    filtros.append(did)
                item.update(status="filtro_global", bloco=did)
            continue
        if v["tipo"] == "scatterChart":
            item.update(status="nao_convertido", motivos=["dispersão não tem bloco equivalente no bi-html"])
            continue
        # medidas do visual
        mets, fora = [], []
        for c in v["campos"]:
            if c["papel"] in PAPEIS_IGNORADOS:
                continue
            if c["tipo"] == "medida":
                r = classes.get(c["nome"])
                info = mat.medida(c["nome"]) if r and r["classe"] == "traduzida" else None
                item["medidas"].append({"medida": c["nome"], "classe": r["classe"] if r else "desconhecida",
                                        "metrica": info["metrica"] if info else None})
                if info and info["metrica"] not in mets:
                    mets.append(info["metrica"])
                elif not info:
                    fora.append(f"[{c['nome']}] {('não traduzida: ' + r['motivo']) if r and r.get('motivo') else 'não traduzida'}")
            elif c["tipo"] == "agregacao":
                mid = mat.implicita(c["tabela"], c["coluna"], c["funcao"]) if c["tabela"] in conv.colunas else None
                item["medidas"].append({"medida": f"{IMPLICITAS.get(c['funcao'], ('?', 'Agregação'))[1]} de {c['coluna']}",
                                        "classe": "implicita" if mid else "nao_traduzida", "metrica": mid})
                if mid and mid not in mets:
                    mets.append(mid)
                elif not mid:
                    fora.append(f"{IMPLICITAS.get(c['funcao'], ('?', 'agregação'))[1].lower()} de {c['coluna']} "
                                "não é número (texto mostrado na tabela)")
        dims = []
        for c in dims_campos:
            gran = _granularidade(c.get("nivel")) if c["tipo"] == "nivel" else None
            did = conv.dimensao(c["tabela"], c["coluna"], gran, tipos)
            if did and did not in dims:
                dims.append(did)
            elif not did:
                item["motivos"].append(f"coluna {c['tabela']}[{c['coluna']}] fora da tabela convertida")
        tempo = bool(dims) and bool(conv.dims[dims[0]].get("granularidade"))
        tipo, troca = _tipo_bloco(v["tipo"], len(dims), len(mets), tempo)
        if not tipo:
            item.update(status="nao_convertido", motivos=item["motivos"] + [f"{v['tipo']} não tem bloco equivalente"])
            continue
        if troca:
            item["motivos"].append(troca)
        # dimensões: cada métrica precisa alcançar todas as dimensões do bloco
        if tipo in SEM_DIMENSAO:
            if dims:
                item["motivos"].append("o bloco não leva dimensões: o eixo do visual ficou de fora")
            dims = []
        elif tipo in UMA_DIMENSAO:
            if len(dims) > 1:
                item["motivos"].append(f"o bloco usa uma dimensão; ficaram de fora {len(dims) - 1}")
            dims = dims[:1]
        elif tipo == "barras_agrupadas":
            dims = dims[:2]
        if tipo == "mapa_uf" and dims:
            valores = {r[0] for r in con.execute(f"SELECT DISTINCT CAST({q(conv.dims[dims[0]]['coluna'])} AS VARCHAR) "
                                                 f"FROM read_parquet({literal(arquivo)}) LIMIT 200").fetchall()} - {None}
            if not valores or not valores <= UFS:
                item.update(status="nao_convertido", motivos=item["motivos"] + [
                    f"o mapa usa {conv.dims[dims[0]]['coluna']}, que não traz siglas de UF; o bi-html só desenha "
                    "o mapa das unidades da federação"])
                continue
            if v["tipo"] == "azureMap":
                item["motivos"].append("o mapa do Azure virou o mapa por UF do bi-html")
        if (tipo in UMA_DIMENSAO and not dims) or (tipo == "barras_agrupadas" and not dims) or \
                (tipo == "area_empilhada" and len(dims) != 2):
            item.update(status="nao_convertido", motivos=item["motivos"] + ["o visual não tem a dimensão que o bloco exige"])
            continue
        validas = []
        for mid in mets:
            fato = mat.metricas[mid]["_fato"]
            soltas = [d for d in dims if conv.tabela_da_dim(d) not in conv.alcance(fato)]
            eixo = mat.metricas[mid].get("_eixo")
            if soltas:
                fora.append(f"{mid}: a dimensão {', '.join(soltas)} não filtra {fato}")
            elif eixo and not any(conv.dims[d]["coluna"] in eixo for d in dims):
                fora.append(f"{mid}: participação calculada sobre {', '.join(eixo)}, outro eixo que o do bloco")
            else:
                validas.append(mid)
        limite = LIMITE_METRICAS[tipo]
        if len(validas) > limite:
            item["motivos"].append(f"o bloco mostra até {limite} métrica(s); ficaram de fora {len(validas) - limite}")
            validas = validas[:limite]
        if tipo == "funil" and len(validas) < 2:
            tipo = "faixa_kpis" if len(validas) > 1 else "numero_destaque"
        if not validas:
            item.update(status="nao_convertido", motivos=item["motivos"] + (fora or ["o visual não tem medida"]))
            continue
        item["motivos"] += fora
        if v["filtros"]:
            item["motivos"].append(f"{v['filtros']} filtro(s) do visual não foram convertidos")
        titulo = v["titulo"] or " e ".join(mat.metricas[m]["descricao"] for m in validas)
        bloco = {"tipo": tipo, "titulo": sem_algarismos(titulo), "metricas": validas,
                 "largura": _largura(v["posicao"], pagina["largura"])}
        if dims:
            bloco["dimensoes"] = dims
        if tipo in ("barras_ranking", "tabela", "barras_agrupadas", "rosca") and not tempo:
            ordem = v.get("ordem") or {"por": "valor", "descendente": True}
            bloco["ordenacao"] = ("alfabetica" if ordem["por"] == "eixo" else
                                  "maior_primeiro" if ordem["descendente"] else "menor_primeiro")
            if ordem["por"] == "eixo" and ordem["descendente"]:
                item["motivos"].append("o eixo em ordem decrescente virou ordem alfabética crescente")
            if tipo != "rosca":
                bloco["limite_itens"] = "todos" if tipo == "tabela" else "medio"
        if tempo:
            bloco["ordenacao"] = "cronologica"
        item.update(status="parcial" if item["motivos"] else "convertido", bloco=tipo)
        candidatos.append((item, bloco))
    if len(candidatos) > 16:
        for item, _ in candidatos[16:]:
            item.update(status="nao_convertido", bloco=None, motivos=item["motivos"] + ["a spec aceita até dezesseis blocos"])
        candidatos = candidatos[:16]
    # filtro global que não alcança o fato de uma métrica do bloco esvazia a métrica no bi-html
    for item, bloco in candidatos:
        for f in filtros:
            soltas = [m for m in bloco["metricas"] if conv.tabela_da_dim(f) not in conv.alcance(mat.metricas[m]["_fato"])]
            if soltas:
                item["motivos"].append(f"o filtro global {f} não filtra {', '.join(soltas)}: com ele ativo, a métrica fica vazia "
                                       "(no Power BI, ela ignora o filtro)")
                item["status"] = "parcial"
    letras = "abcdefghijklmnopqrstuvwxyz"
    blocos = []
    for i, (item, bloco) in enumerate(candidatos):
        bloco = {"id": "bloco_" + letras[i % 26] * (i // 26 + 1), **bloco}
        item["bloco_id"] = bloco["id"]
        blocos.append(bloco)
    return blocos, filtros, fidelidade


# ---------------------------------------------------------------- equivalência

def _igual(obtido, esperado, tipo: str) -> tuple[bool, str | None]:
    if obtido is None and esperado is None:
        return True, None
    if tipo in ("contagem", "contagem_distinta") and {obtido, esperado} <= {None, 0}:
        return True, "vazio no Power BI, zero no bi-html"
    if obtido is None or esperado is None:
        return False, None
    if isinstance(obtido, str) or isinstance(esperado, str):
        return str(obtido) == str(esperado), None
    a, b = float(obtido), float(esperado)
    return abs(a - b) <= TOLERANCIA * max(1.0, abs(b)), None


def _contextos(conv: Conversor, con, arquivo: str, fato: str, dims_relatorio: list[str],
               por_dimensao: int = 1) -> list[tuple[str, str, object]]:
    """Até três (dimensão, coluna, valor, valor em texto) para testar: as dimensões do relatório que
    filtram o fato, com os valores mais frequentes dentro da parte do fato."""
    escolhidas = []
    for did in dims_relatorio:
        d = conv.dims[did]
        if d.get("granularidade") or conv.tabela_da_dim(did) not in conv.alcance(fato):
            continue
        tipo = conv.tipos_plano.get(d["coluna"], "")
        if not (tipo == "VARCHAR" or tipo.startswith(("BIGINT", "INTEGER", "SMALLINT", "TINYINT"))):
            continue
        linhas = con.execute(f"SELECT {q(d['coluna'])}, CAST({q(d['coluna'])} AS VARCHAR) FROM read_parquet({literal(arquivo)}) "
                             f"WHERE {q(ORIGEM)} = ? AND {q(d['coluna'])} IS NOT NULL GROUP BY 1, 2 "
                             f"ORDER BY count(*) DESC, 2 LIMIT {int(por_dimensao)}", [fato]).fetchall()
        escolhidas += [(did, d["coluna"], valor, texto) for valor, texto in linhas]
        if len({e[0] for e in escolhidas}) == 3:
            break
    return escolhidas


def testar_equivalencia(conv: Conversor, mat: Materializador, classes: dict, dims_relatorio: list[str]) -> dict:
    """Medidas traduzidas: pbix-mcp (referência) × camada de métricas, numa amostra de contextos."""
    import duckdb

    from .consulta import consultar

    projeto = conv.projeto
    arquivo = (projeto / PLANO).as_posix()
    con = duckdb.connect()
    pedidos, casos = [], []
    try:
        for nome, r in classes.items():
            if r["classe"] != "traduzida":
                continue
            info = mat.medida(nome)
            met = mat.metricas[info["metrica"]]
            ctxs = _contextos(conv, con, arquivo, met["_fato"], dims_relatorio)
            if met["tipo"] == "participacao":
                if met["_eixo"]:  # agrupa pela coluna do ALLSELECTED, onde a participação equivale
                    eixos = [conv.dimensao(*col.split(".", 1), None, conv.tipos_plano) for col in met["_eixo"]]
                    ctxs = _contextos(conv, con, arquivo, met["_fato"], [e for e in eixos if e], por_dimensao=2)
                variantes = [{"filtros": [(c[0], c[1], c[2], c[3])], "agrupar": True} for c in ctxs[:2]]
            else:
                variantes = [{"filtros": [], "agrupar": False}]
                variantes += [{"filtros": [c], "agrupar": False} for c in ctxs]
                if len(ctxs) >= 2:
                    variantes.append({"filtros": ctxs[:2], "agrupar": False})
            for v in variantes:
                pid = f"p{len(pedidos)}"
                contexto = {col: [valor] for _, col, valor, _ in v["filtros"]}
                pedidos.append({"id": pid, "medida": nome, "contexto": contexto,
                                "agrupar": [v["filtros"][0][1]] if v["agrupar"] else None})
                casos.append({"id": pid, "medida": nome, "metrica": info["metrica"], "escala": info["escala"],
                              "tipo": met["tipo"], "filtros": v["filtros"], "agrupar": v["agrupar"],
                              "referencia": "pbix-mcp"})
        # agregações implícitas: o pbix-mcp não avalia; a referência é SQL sobre a tabela original
        tabelas = {t["nome"]: t for t in conv.ext["tabelas"]}
        for mid, m in mat.metricas.items():
            imp = m.get("_implicita")
            if not imp:
                continue
            ctxs = [c for c in _contextos(conv, con, arquivo, imp["tabela"], dims_relatorio)
                    if conv.tabela_da_dim(c[0]) == imp["tabela"]][:2]
            original = literal((projeto / PASTA / tabelas[imp["tabela"]]["parquet"]).as_posix())
            sql_agg = {"soma": "sum", "media": "avg", "minimo": "min", "maximo": "max"}.get(m["tipo"])
            expr = (f"{sql_agg}({q(imp['coluna'])})" if sql_agg else f"count(DISTINCT {q(imp['coluna'])})"
                    if m["tipo"] == "contagem_distinta" else f"count({q(imp['coluna'])})")
            for filtros in [[]] + [[c] for c in ctxs]:
                onde = " AND ".join(f"CAST({q(c[1].split('.', 1)[1])} AS VARCHAR) = {literal(c[3])}" for c in filtros)
                valor = con.execute(f"SELECT {expr} FROM read_parquet({original})" + (f" WHERE {onde}" if onde else "")).fetchone()[0]
                casos.append({"id": None, "medida": m["descricao"], "metrica": mid, "escala": 1.0, "tipo": m["tipo"],
                              "filtros": filtros, "agrupar": False, "referencia": "sql_tabela_original",
                              "valor_referencia": float(valor) if isinstance(valor, Decimal) else valor})
    finally:
        con.close()
    respostas = {}
    if pedidos:
        with tempfile.TemporaryDirectory() as tmp:
            entrada, saida = Path(tmp) / "pedidos.json", Path(tmp) / "respostas.json"
            entrada.write_text(json.dumps(pedidos, ensure_ascii=False, default=str), encoding="utf-8")
            executar_externo("avaliar", str(conv.caminho), str(entrada), str(saida))
            respostas = {r["id"]: r for r in json.loads(saida.read_text(encoding="utf-8"))}
    resultados = []
    for c in casos:
        filtros_bi = [{"dimensao": f[0], "operador": "em", "valores": [f[3]]} for f in c["filtros"]]
        if c["agrupar"]:
            r = consultar(projeto, [c["metrica"]], dimensoes=[c["filtros"][0][0]])
            linha = next((l for l in r["linhas"] if str(l[c["filtros"][0][0]]) == c["filtros"][0][3]), {})
        else:
            linha = consultar(projeto, [c["metrica"]], filtros=filtros_bi)["linhas"][0]
        bi = linha.get(c["metrica"])
        bi = float(bi) if isinstance(bi, Decimal) else bi
        bi_escalado = bi * c["escala"] if isinstance(bi, (int, float)) and c["escala"] != 1.0 else bi
        if c["referencia"] == "pbix-mcp":
            resp = respostas.get(c["id"], {})
            ref, status_ref, tempo = resp.get("valor"), resp.get("status"), resp.get("tempo_s")
        else:
            ref, status_ref, tempo = c["valor_referencia"], "ok", None
        if status_ref == "blank":  # o Power BI devolveu vazio: é um resultado, não um erro
            ref, status_ref = None, "ok"
        bate, nota = _igual(bi_escalado, ref, c["tipo"]) if status_ref == "ok" else (False, f"referência: {status_ref}")
        resultados.append({"medida": c["medida"], "metrica": c["metrica"], "referencia": c["referencia"],
                           "contexto": {f[1]: f[3] for f in c["filtros"]}, "agrupado_por": c["filtros"][0][1] if c["agrupar"] else None,
                           "escala": c["escala"], "valor_referencia": ref, "valor_bi_html": bi_escalado,
                           "bate": bate, "nota": nota, "tempo_referencia_s": tempo})
    por_medida: dict[str, dict] = {}
    for r in resultados:
        p = por_medida.setdefault(r["medida"], {"contextos": 0, "batem": 0, "metrica": r["metrica"],
                                                "referencia": r["referencia"]})
        p["contextos"] += 1
        p["batem"] += r["bate"]
    for p in por_medida.values():
        p["validada"] = p["contextos"] > 0 and p["batem"] == p["contextos"]
    return {"casos": resultados, "por_medida": por_medida}


# ---------------------------------------------------------------- modelo, specs e relatório

def _gravar_modelo(projeto: Path, metricas: dict, dims: dict, coluna_data: str | None, cabecalho: str) -> None:
    import yaml

    fonte = {"arquivo": PLANO.as_posix()}
    if coluna_data:
        fonte["coluna_data"] = coluna_data
    limpas = {k: {c: v for c, v in m.items() if not c.startswith("_")} for k, m in metricas.items()}
    modelo = {"versao": VERSAO, "fonte": fonte, "dimensoes": dims, "metricas": limpas}
    destino = Path(projeto) / ARQUIVO_MODELO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(cabecalho + yaml.safe_dump(modelo, allow_unicode=True, sort_keys=False, width=110),
                       encoding="utf-8")


def dados_pessoais(projeto: Path) -> list[dict]:
    """Colunas de texto da tabela convertida com CPF, e-mail, telefone e afins (mesma regra do perfil)."""
    import duckdb

    from .perfil import _detectar_pessoal

    arquivo = literal((Path(projeto) / PLANO).as_posix())
    con = duckdb.connect()
    try:
        achados = []
        for col, tipo, *_ in con.execute(f"DESCRIBE SELECT * FROM read_parquet({arquivo})").fetchall():
            if col == ORIGEM or tipo != "VARCHAR":
                continue
            amostra = [r[0] for r in con.execute(f"SELECT DISTINCT {q(col)} FROM read_parquet({arquivo}) "
                                                 f"WHERE {q(col)} IS NOT NULL LIMIT 2000").fetchall()]
            achado = _detectar_pessoal(ident(col.split(".", 1)[-1]), amostra)
            if achado:
                achados.append({"coluna": col, **achado})
    finally:
        con.close()
    return achados


def _tema(projeto: Path, relatorio: dict) -> dict:
    from .design import importar

    tema = relatorio["tema"]
    if not tema.get("json"):
        # Tema base do Power BI não vem dentro do .pbix: o dashboard usa o estilo claro do bi-html.
        from .design import aplicar_estilo

        r = aplicar_estilo(projeto, "claro")
        return {"importado": True, "nome": "claro (estilo base do bi-html)", "aa": r["aa"],
                "ajustes_de_contraste": len(r["ajustes_de_contraste"]),
                "motivo": f"o tema em uso ({tema.get('nome') or 'sem nome'}) não vem dentro do arquivo"}
    arquivo = Path(projeto) / PASTA / "tema.json"
    arquivo.write_text(tema["json"], encoding="utf-8")
    try:
        r = importar(projeto, str(arquivo))
    except ErroDeLeitura as e:
        return {"importado": False, "motivo": e.mensagem, "detalhes": e.detalhes}
    return {"importado": True, "nome": tema["nome"], "aa": r["aa"], "ajustes_de_contraste": len(r["ajustes_de_contraste"])}


def _md(relatorio: dict) -> str:
    """fidelidade.md: o relatório de conversão em texto corrido para quem revisa."""
    r = relatorio
    L = [f"# Fidelidade da conversão — {r['arquivo']['nome']}", "",
         f"Convertido em {r['convertido_em']} pelo bi-html (pbix-mcp {r['ferramentas']['pbix-mcp']}, "
         f"pbixray {r['ferramentas']['pbixray']}). Modo do arquivo: {r['modo']}. Relatório: {r['formato_relatorio']}.", "",
         "## Tabelas", "", "| Tabela | Linhas no .pbix | Linhas extraídas | No modelo convertido | Iguais |", "|---|---|---|---|---|"]
    for t in r["tabelas"]:
        no_plano = (t["linhas_no_plano"] if t["fato"] else "dimensão dos fatos" if t.get("ligada") else
                    "tabela de datas automática" if t["datas_automaticas"] else "fora (nenhuma medida a usa)")
        L.append(f"| {t['tabela']} | {t['linhas_metadados']} | {t['linhas_extraidas']} | {no_plano} | "
                 f"{'sim' if t['iguais'] else 'não'} |")
    L += ["", "## Medidas", "", "| Medida | Classe | Métrica | Equivalência | Motivo ou ressalva |", "|---|---|---|---|---|"]
    for m in r["medidas"]:
        eq = m.get("equivalencia")
        teste = f"{eq['batem']} de {eq['contextos']} contextos" if eq else "—"
        nota = m.get("motivo") or "; ".join(m.get("ressalvas") or [])
        L.append(f"| {m['medida']} | {m['classe']} | {m.get('metrica') or '—'} | {teste} | {nota} |")
    L += ["", "## Páginas e visuais", ""]
    for p in r["paginas"]:
        L += [f"### {p['nome']}", "", f"Spec: `{p['spec'] or '—'}`. {p['resumo']}", "",
              "| Visual | Tipo no Power BI | Bloco | Status | Motivos |", "|---|---|---|---|---|"]
        for v in p["visuais"]:
            L.append(f"| {v['titulo'] or '(sem título)'} | {v['tipo_power_bi']} | {v.get('bloco_id') or v['bloco'] or '—'} | "
                     f"{v['status']} | {'; '.join(v['motivos'])} |")
        L.append("")
    L += ["## Semântica", ""] + [f"- {s}" for s in r["semantica"]] + [""]
    return "\n".join(L)


def converter(projeto: Path, caminho: str | Path, testar: bool = True, sobrescrever: bool = False) -> dict:
    """Converte um .pbix em importação: dados, modelo, specs por página, equivalência e fidelidade."""
    import duckdb

    from .modelo import carregar, registrar_linhagem
    from .dashboard import checar_spec
    from .render import renderizar

    projeto = Path(projeto)
    caminho = Path(caminho).expanduser()
    if not caminho.is_absolute():
        caminho = projeto / caminho
    if not caminho.is_file() or caminho.suffix.lower() != ".pbix":
        raise ErroDeConversao(f"arquivo .pbix não encontrado: {caminho.name}")
    modelo_atual = projeto / ARQUIVO_MODELO
    if modelo_atual.is_file() and not modelo_atual.read_text(encoding="utf-8").startswith(MARCA) and not sobrescrever:
        raise ErroDeConversao(f"{ARQUIVO_MODELO} já existe e não veio de uma conversão",
                              ["use outra pasta de projeto ou peça para sobrescrever"])
    extracao = extrair(projeto, caminho)
    if extracao["modo"] != "importacao":
        explicacao = {
            "directquery": "o arquivo está em DirectQuery: os dados ficam no banco de origem, não no .pbix",
            "misto": "o arquivo mistura importação e DirectQuery: parte dos dados não está no .pbix",
            "conexao_dinamica": "o arquivo está em conexão dinâmica: o modelo fica num conjunto de dados do serviço",
        }.get(extracao["modo"], "o arquivo não tem modelo de dados")
        raise ErroDeConversao(f"a conversão só vale para importação; {explicacao}",
                              ["a via (b) do plano incorpora o relatório original pelo Power BI (Publicar na Web "
                               "ou incorporação segura), conforme a licença da conta",
                               "ou salve uma cópia do relatório em modo de importação e converta essa cópia"])
    relatorio = ler_relatorio(caminho)
    conv = Conversor(projeto, caminho, extracao, relatorio)
    classes = conv.classificar()
    fatos = conv.fatos(classes)
    if not fatos:
        raise ErroDeConversao("o .pbix não tem tabela com dados para converter")

    # 1ª passada: materializa as métricas para saber as colunas calculadas de cada fato
    conv.tipos_plano = {}
    mat = Materializador(conv.tr, conv.medidas, conv.nomes, {})
    for nome in classes:
        mat.medida(nome)
    for p in relatorio["paginas"]:
        for v in p["visuais"]:
            for c in v["campos"]:
                if c["tipo"] == "agregacao" and c["tabela"] in fatos:
                    mat.implicita(c["tabela"], c["coluna"], c["funcao"])
    plano = montar_plano(projeto, extracao, fatos, mat.calculadas, conv.relacoes)
    conv.tipos_plano = plano["colunas"]
    for m in mat.metricas.values():
        if m["tipo"] == "soma" and m.get("coluna") in plano["colunas"]:
            m["formato"] = m["formato"] if m["formato"] != "decimal" else _formato(None, "soma", plano["colunas"][m["coluna"]])

    # dimensões do relatório e coluna de data
    for tabela, coluna, gran in _colunas_de_dimensao(relatorio):
        conv.dimensao(tabela, coluna, gran, conv.tipos_plano)
    for m in mat.metricas.values():  # a coluna do ALLSELECTED de uma participação vira dimensão (eixo do teste)
        for col in m.get("_eixo") or []:
            conv.dimensao(*col.split(".", 1), None, conv.tipos_plano)
    dims_relatorio = [d for d in conv.dims]
    datas = [conv.dims[d]["coluna"] for d in conv.dims if conv.dims[d].get("granularidade")]
    coluna_data = datas[0] if datas else None

    # specs por página
    con = duckdb.connect()
    paginas, specs = [], []
    try:
        for p in relatorio["paginas"]:
            if p["oculta"]:
                paginas.append({"nome": p["nome"], "spec": None, "resumo": "página de dica ou oculta: não convertida",
                                "visuais": []})
                continue
            blocos, filtros, fidelidade = _blocos_da_pagina(conv, mat, p, classes, con, (projeto / PLANO).as_posix())
            paginas.append({"nome": p["nome"], "spec": None, "visuais": fidelidade, "blocos": blocos, "filtros": filtros})
            specs.append(p)
    finally:
        con.close()

    cabecalho = (f"{MARCA} em {datetime.now().strftime('%d/%m/%Y')} ({caminho.name}).\n"
                 "# Medidas traduzidas do DAX e agregações implícitas dos visuais; veja saidas/bi/pbix/fidelidade.md.\n"
                 "# Métrica com \"(não validada)\" na descrição não bateu com o Power BI no teste de equivalência.\n")
    _gravar_modelo(projeto, mat.metricas, conv.dims, coluna_data, cabecalho)
    carregar(projeto)  # valida o modelo contra a tabela convertida
    tema = _tema(projeto, relatorio)

    equivalencia = testar_equivalencia(conv, mat, classes, dims_relatorio) if testar else {"casos": [], "por_medida": {}}
    nao_validadas = set()
    for nome, r in classes.items():
        if r["classe"] == "traduzida":
            eq = equivalencia["por_medida"].get(nome)
            if not eq or not eq["validada"]:
                nao_validadas.add(mat.medida(nome)["metrica"])
    for mid, m in mat.metricas.items():
        if m.get("_implicita"):
            eq = equivalencia["por_medida"].get(m["descricao"])
            if not eq or not eq["validada"]:
                nao_validadas.add(mid)
    for mid in nao_validadas:
        if not mat.metricas[mid]["descricao"].endswith(SELO):
            mat.metricas[mid]["descricao"] += SELO
    _gravar_modelo(projeto, mat.metricas, conv.dims, coluna_data, cabecalho)
    modelo, arquivo_fonte, _ = carregar(projeto)
    registrar_linhagem(projeto, modelo, arquivo_fonte)

    # specs e páginas renderizadas
    (projeto / PAGINAS_SPEC).mkdir(parents=True, exist_ok=True)
    renderizadas, principal = [], None
    nome_relatorio = sem_algarismos(Path(caminho.name).stem.replace("_", " ").replace("-", " "))
    usados = Nomes()
    for pag in paginas:
        if not pag.get("blocos"):
            if pag.get("visuais") is not None and "resumo" not in pag:
                pag["resumo"] = "nenhum visual convertido"
            continue
        spec = {"versao_spec": "0.1", "titulo": sem_algarismos(pag["nome"]),
                "subtitulo": sem_algarismos(f"Convertido do Power BI: {nome_relatorio}"),
                "pergunta_negocio": sem_algarismos(f"O que a página {pag['nome']} do relatório {nome_relatorio} mostra, "
                                                   "recalculado pela camada de métricas do bi-html."),
                "origem": "pbix", "estilo": {"fonte": "enviado", "tokens": "design/tokens.json"},
                "layout": "duas_colunas", "periodo": "tudo", "filtros_globais": pag["filtros"], "blocos": pag["blocos"],
                "notas": "Medidas sem tradução para a camada de métricas ficaram de fora; o relatório de fidelidade "
                         "da conversão lista cada uma com o motivo."}
        problemas = checar_spec(spec, modelo)
        if problemas:
            pag["resumo"] = "spec inválida: " + "; ".join(problemas[:3])
            continue
        slug = usados.novo(pag["nome"])
        rel_spec = PAGINAS_SPEC / f"{slug}.json"
        (projeto / rel_spec).write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pag["spec"] = rel_spec.as_posix()
        if principal is None:
            principal = rel_spec
            (projeto / "dashboard" / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                                                             encoding="utf-8")
        if tema.get("importado"):
            r = renderizar(projeto, rel_spec, PAGINAS_HTML / slug)
            pag["html"] = r["html"]
            renderizadas.append({"pagina": pag["nome"], **{k: r[k] for k in ("html", "artifact", "bytes", "dentro_da_meta",
                                                                               "avisos")}})
        conv_ = sum(v["status"] in ("convertido", "parcial") for v in pag["visuais"])
        dados = sum(v["status"] not in ("decorativo",) for v in pag["visuais"])
        pag["resumo"] = f"{conv_} de {dados} visuais com dado viraram bloco ou filtro"
    if principal and tema.get("importado"):
        renderizar(projeto)

    # relatório
    tabelas = []
    for t in extracao["tabelas"]:
        parte = plano["partes"].get(t["nome"], {})
        tabelas.append({"tabela": t["nome"], "linhas_metadados": t["linhas_metadados"],
                        "linhas_extraidas": t["linhas_extraidas"], "linhas_no_plano": parte.get("linhas_no_plano"),
                        "fato": t["nome"] in fatos, "datas_automaticas": t["datas_automaticas"],
                        "ligada": any(t["nome"] in p["tabelas_ligadas"] for p in plano["partes"].values()),
                        "iguais": t["linhas_metadados"] == t["linhas_extraidas"] and
                        (t["nome"] not in fatos or parte.get("iguais", False))})
    medidas = []
    for nome, r in classes.items():
        item = {"medida": nome, "classe": r["classe"], "motivo": r.get("motivo"), "ressalvas": r.get("ressalvas") or []}
        if r["classe"] == "traduzida":
            info = mat.medida(nome)
            item.update(metrica=info["metrica"], escala=info["escala"], equivalencia=equivalencia["por_medida"].get(nome))
        medidas.append(item)
    implicitas = [{"medida": m["descricao"].removesuffix(SELO), "classe": "implicita", "metrica": mid,
                   "motivo": None, "ressalvas": [], "equivalencia": equivalencia["por_medida"].get(m["descricao"].removesuffix(SELO))}
                  for mid, m in mat.metricas.items() if m.get("_implicita")]
    visuais = [v for p in paginas for v in p.get("visuais") or []]
    contagem = lambda chave, lista: {k: sum(1 for x in lista if x[chave] == k) for k in sorted({x[chave] for x in lista})}  # noqa: E731
    relatorio_final = {
        "arquivo": extracao["arquivo"], "ferramentas": extracao["ferramentas"], "modo": extracao["modo"],
        "formato_relatorio": relatorio["formato"],
        "convertido_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tabelas": tabelas, "fatos": fatos, "plano": {"arquivo": PLANO.as_posix(), "partes": plano["partes"]},
        "medidas": medidas + implicitas,
        "resumo_medidas": contagem("classe", medidas + implicitas),
        "paginas": [{k: v for k, v in p.items() if k not in ("blocos", "filtros")} for p in paginas],
        "resumo_visuais": contagem("status", visuais),
        "equivalencia": equivalencia, "tema": tema, "renderizadas": renderizadas,
        "dados_pessoais": dados_pessoais(projeto),
        "semantica": [
            "cada métrica filtra a própria tabela de origem na tabela convertida, então somas de fatos diferentes "
            "não se misturam",
            "filtro numa tabela que não se liga ao fato da métrica esvazia a métrica no bi-html; no Power BI, não filtra",
            "o filtro de um CALCULATE se soma ao filtro do leitor; no Power BI, substitui o filtro da mesma coluna",
            "métrica com escala (por exemplo, R$ tri) usa a métrica base; o bi-html formata a grandeza",
            "medida sem validação no teste de equivalência leva \"(não validada)\" na descrição",
        ],
    }
    (projeto / RELATORIO).write_text(json.dumps(relatorio_final, ensure_ascii=False, indent=2, default=str) + "\n",
                                     encoding="utf-8")
    (projeto / FIDELIDADE).write_text(_md(relatorio_final), encoding="utf-8")
    manifesto = ler_manifesto(projeto)
    manifesto["pbix"] = {"arquivo": extracao["arquivo"], "modo": extracao["modo"], "fatos": fatos,
                         "dados_pessoais": relatorio_final["dados_pessoais"],
                         "relatorio": RELATORIO.as_posix(), "convertido_em": relatorio_final["convertido_em"]}
    manifesto["eventos"].append({"quando": relatorio_final["convertido_em"], "evento": "pbix_convertido",
                                 "sha256": extracao["arquivo"]["sha256"]})
    (projeto / PASTA_BI / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str) + "\n",
                                                       encoding="utf-8")
    return {
        "arquivo": extracao["arquivo"]["nome"], "modo": extracao["modo"],
        "tabelas_iguais": all(t["iguais"] for t in tabelas), "medidas": relatorio_final["resumo_medidas"],
        "equivalencia": {n: f"{p['batem']} de {p['contextos']}" for n, p in equivalencia["por_medida"].items()},
        "visuais": relatorio_final["resumo_visuais"], "paginas": [p["spec"] for p in paginas if p.get("spec")],
        "dashboard": "saidas/bi/dashboard.html" if principal and tema.get("importado") else None,
        "relatorio": RELATORIO.as_posix(), "fidelidade": FIDELIDADE.as_posix(), "tema": tema,
        "publicacao_bloqueada": [f"a coluna {d['coluna']} parece ter dado pessoal ({d['tipo']})"
                                 for d in relatorio_final["dados_pessoais"]],
    }
