"""
Dashboard: da spec aos dados prontos para desenhar.

A spec (`dashboard/spec.json`, escrita pelo Claude) diz quais blocos existem e
quais métricas cada um mostra. Este módulo calcula, no DuckDB, tudo o que o
navegador vai exibir, de forma que o HTML não faça conta nenhuma:

- cada bloco vira uma tabela de consulta por combinação de filtros globais
  (GROUPING SETS: cada filtro com cada valor e com "todos"), então qualquer
  escolha do leitor nos filtros é uma busca direta, inclusive para métricas que
  não se reagregam (contagem distinta, por dia, participação);
- comparações com o período anterior e as variações são calculadas aqui;
- totais de rosca, tabela e cascata saem de um grouping set sem as dimensões
  do bloco, não de soma no navegador.

O renderizador (`render.py`) só formata e desenha.
"""
from __future__ import annotations

import itertools
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from .consulta import _data_max, expressao, expressao_dimensao, periodo_de_comparacao, resolver_periodo
from .design import ErroDeDesign
from .ingestao import ErroDeLeitura, ler_manifesto
from .modelo import ErroDeModelo, carregar, definicao, literal, q
from .spec import validar as validar_spec

ARQUIVO_SPEC = Path("dashboard") / "spec.json"
TODOS = "__todos__"
VAZIO = "(não informado)"
LIMITES = {"poucos": 5, "medio": 10, "todos": 50}
COM_TOTAL = {"rosca", "tabela", "cascata", "barras_ranking"}
SEM_DIMENSAO = {"numero_destaque", "faixa_kpis", "funil"}
UMA_DIMENSAO = {"linha_tempo", "barras_ranking", "rosca", "tabela", "cascata", "mapa_uf"}
DUAS_DIMENSOES = {"area_empilhada", "mapa_calor"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE",
       "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


class ErroDeDashboard(ErroDeLeitura):
    pass


def _num(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def _texto(v):
    if v is None:
        return VAZIO
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def ler_spec(projeto: Path) -> dict:
    caminho = Path(projeto) / ARQUIVO_SPEC
    if not caminho.is_file():
        raise ErroDeDashboard(f"não existe {ARQUIVO_SPEC}", ["escreva a spec (ou use propor_spec) antes de renderizar"])
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErroDeDashboard(f"{ARQUIVO_SPEC} não é JSON válido (linha {e.lineno})") from None


def checar_spec(spec: dict, modelo: dict) -> list[str]:
    """Schema, métricas e dimensões do modelo e regras de forma de cada tipo de bloco."""
    problemas = validar_spec(spec, set(modelo["metricas"]))
    dims = modelo["dimensoes"]
    for f in spec.get("filtros_globais") or []:
        if f not in dims:
            problemas.append(f"filtros_globais: dimensão {f!r} não existe no modelo")
        elif dims[f].get("granularidade"):
            problemas.append(f"filtros_globais: {f} é dimensão de tempo; use o período da spec")
    for i, b in enumerate(spec.get("blocos") or []):
        if not isinstance(b, dict):
            continue
        lugar, tipo, bd = f"blocos[{i}] ({b.get('id')})", b.get("tipo"), b.get("dimensoes") or []
        for d in bd:
            if d not in dims:
                problemas.append(f"{lugar}: dimensão {d!r} não existe no modelo")
        for f in b.get("filtros") or []:
            if f.get("dimensao") not in dims:
                problemas.append(f"{lugar}: filtro em dimensão {f.get('dimensao')!r} que não existe no modelo")
        if tipo in SEM_DIMENSAO and bd:
            problemas.append(f"{lugar}: {tipo} não leva dimensões")
        if tipo in UMA_DIMENSAO and len(bd) != 1:
            problemas.append(f"{lugar}: {tipo} precisa de exatamente uma dimensão")
        if tipo in DUAS_DIMENSOES and len(bd) != 2:
            problemas.append(f"{lugar}: {tipo} precisa de duas dimensões")
        if tipo == "barras_agrupadas" and not bd:
            problemas.append(f"{lugar}: barras_agrupadas precisa de uma ou duas dimensões")
        if tipo in ("linha_tempo", "area_empilhada") and bd and bd[0] in dims and not dims[bd[0]].get("granularidade"):
            problemas.append(f"{lugar}: a primeira dimensão de {tipo} deve ser de tempo (com granularidade)")
        if tipo == "funil" and len(b.get("metricas") or []) < 2:
            problemas.append(f"{lugar}: funil precisa de pelo menos duas métricas, uma por etapa")
        comp = b.get("comparacao", "nenhuma")
        if comp == "meta":
            problemas.append(f"{lugar}: comparação com meta ainda não é suportada")
        if comp not in (None, "nenhuma", "meta"):
            if spec.get("periodo") == "tudo":
                problemas.append(f"{lugar}: comparação precisa de um período definido na spec (não 'tudo')")
            if any(d in dims and dims[d].get("granularidade") for d in bd):
                problemas.append(f"{lugar}: comparação não combina com dimensão de tempo")
    return problemas


# ---------------------------------------------------------------- cálculo

def _consulta_bloco(con, arquivo, modelo, bloco, filtros_globais, janela):
    mets, dims = modelo["metricas"], modelo["dimensoes"]
    cdata = modelo["fonte"].get("coluna_data")
    bdims = bloco.get("dimensoes") or []
    # Filtro global que também é dimensão do bloco não entra no agrupamento: o bloco já traz uma
    # linha por valor, e o navegador só escolhe as linhas (sem total) quando o filtro está ativo.
    fexpr = {f: expressao_dimensao(dims[f])[0] for f in filtros_globais if f not in bdims}
    bexpr = {d: expressao_dimensao(dims[d])[0] for d in bdims}
    chave_dia_semana = {d: f"min(isodow({q(dims[d]['coluna'])}))" for d in bdims
                        if dims[d].get("granularidade") == "dia_semana"}
    todas = list(fexpr.values()) + list(bexpr.values())
    grupo_id = f"GROUPING({', '.join(todas)})" if todas else "0"
    particao = ", ".join([grupo_id] + list(fexpr.values()))

    selecao = [f"'{TODOS}' AS {q('f__' + f)}" for f in filtros_globais if f in bdims]
    for f, e in fexpr.items():
        selecao.append(f"CASE WHEN GROUPING({e}) = 1 THEN '{TODOS}' ELSE coalesce(CAST({e} AS VARCHAR), '{VAZIO}') END AS {q('f__' + f)}")
    for d, e in bexpr.items():
        selecao.append(f"CASE WHEN GROUPING({e}) = 1 THEN '{TODOS}' ELSE coalesce(CAST({e} AS VARCHAR), '{VAZIO}') END AS {q('d__' + d)}")
    for d, e in chave_dia_semana.items():
        selecao.append(f"{e} AS {q('o__' + d)}")
    for m in bloco["metricas"]:
        sql = expressao(m, mets, cdata).replace("OVER ()", f"OVER (PARTITION BY {particao})")
        selecao.append(f"{sql} AS {q('m__' + m)}")

    conjuntos = []
    for n in range(len(fexpr) + 1):
        for sub in itertools.combinations(fexpr.values(), n):
            conjuntos.append(list(sub) + list(bexpr.values()))
            if bdims and bloco["tipo"] in COM_TOTAL:
                conjuntos.append(list(sub))
    agrupamento = ""
    if todas:
        agrupamento = " GROUP BY GROUPING SETS (" + ", ".join("(" + ", ".join(c) + ")" for c in conjuntos) + ")"

    onde, params = [], []
    if janela:
        onde.append(f"CAST({q(cdata)} AS DATE) BETWEEN ? AND ?")
        params += list(janela)
    for f in bloco.get("filtros") or []:
        e = expressao_dimensao(dims[f["dimensao"]])[0]
        marcas = ", ".join("?" for _ in f["valores"])
        onde.append(f"CAST({e} AS VARCHAR) {'IN' if f['operador'] == 'em' else 'NOT IN'} ({marcas})")
        params += [str(v) for v in f["valores"]]
    sql = f"SELECT {', '.join(selecao)} FROM read_parquet({literal(arquivo)})"
    if onde:
        sql += " WHERE " + " AND ".join(onde)
    sql += agrupamento
    cursor = con.execute(sql, params)
    nomes = [c[0] for c in cursor.description]
    return [dict(zip(nomes, r)) for r in cursor.fetchall()], sql


def _criterio(bloco, dims) -> str:
    """Ordenação efetiva: a da spec, ou a natural do tipo de bloco."""
    ordem = bloco.get("ordenacao")
    if ordem:
        return ordem
    bdims = bloco.get("dimensoes") or []
    if bdims and dims[bdims[0]].get("granularidade"):
        return "cronologica"
    if bloco["tipo"] == "cascata":
        return "cascata"
    if bloco["tipo"] in ("barras_ranking", "rosca", "tabela", "mapa_uf", "barras_agrupadas"):
        return "maior_primeiro"
    return "alfabetica"


def _ordenar(pares, bloco, dims):
    """Ordena pares (linha bruta do DuckDB, linha do bloco) pelo critério do bloco."""
    bdims = bloco.get("dimensoes") or []
    m0 = "m__" + bloco["metricas"][0]
    criterio = _criterio(bloco, dims)

    def valor(par):
        v = par[0][m0]
        return float(v) if v is not None else None

    if criterio in ("maior_primeiro", "menor_primeiro"):
        sinal = -1 if criterio == "maior_primeiro" else 1
        return sorted(pares, key=lambda p: (valor(p) is None, sinal * (valor(p) or 0)))
    if criterio == "cascata":
        # entradas primeiro, da maior para a menor; depois as saídas, da maior para a menor
        return sorted(pares, key=lambda p: ((valor(p) or 0) < 0, -abs(valor(p) or 0)))
    if criterio == "cronologica":
        return sorted(pares, key=lambda p: [p[0].get("o__" + d) or p[0]["d__" + d] for d in bdims])
    return sorted(pares, key=lambda p: [str(p[0]["d__" + d]) for d in bdims])


def calcular_bloco(con, arquivo, modelo, bloco, filtros_globais, janelas):
    dims = modelo["dimensoes"]
    bdims = bloco.get("dimensoes") or []
    atuais, sql = _consulta_bloco(con, arquivo, modelo, bloco, filtros_globais, janelas["atual"])
    anteriores = []
    if janelas.get("comparacao") and bloco.get("comparacao") not in (None, "nenhuma"):
        anteriores, _ = _consulta_bloco(con, arquivo, modelo, bloco, filtros_globais, janelas["comparacao"])

    def chave_f(l):
        return "|".join(l["f__" + f] for f in filtros_globais)

    def chave_d(l):
        return "|".join(l["d__" + d] for d in bdims)

    antes = {(chave_f(l), chave_d(l)): l for l in anteriores}
    pares_por_filtro: dict[str, list] = {}
    totais: dict[str, dict] = {}
    for l in atuais:
        linha = {d: l["d__" + d] for d in bdims}
        for m in bloco["metricas"]:
            v = _num(l["m__" + m])
            linha[m] = v
            if anteriores:
                b = _num((antes.get((chave_f(l), chave_d(l))) or {}).get("m__" + m))
                linha[m + "__comparacao"] = b
                linha[m + "__variacao_pct"] = (v - b) / abs(b) if v is not None and b else None
        if bdims and l["d__" + bdims[0]] == TODOS:
            totais[chave_f(l)] = linha
        else:
            pares_por_filtro.setdefault(chave_f(l), []).append((l, linha))

    sem_corte = bloco["tipo"] in ("linha_tempo", "area_empilhada", "mapa_calor", "mapa_uf")
    limite = None if sem_corte else LIMITES.get(bloco.get("limite_itens") or "todos", 50)
    por_filtro = {}
    for chave in set(pares_por_filtro) | set(totais):
        ordenadas = _ordenar(pares_por_filtro.get(chave, []), bloco, dims)
        por_filtro[chave] = {"linhas": [linha for _, linha in ordenadas][:limite], "total": totais.get(chave)}
    return por_filtro, sql


def _opcoes_de_filtro(con, arquivo, modelo, filtros_globais, janela):
    dims, cdata = modelo["dimensoes"], modelo["fonte"].get("coluna_data")
    opcoes = {}
    for f in filtros_globais:
        e = expressao_dimensao(dims[f])[0]
        sql = f"SELECT DISTINCT coalesce(CAST({e} AS VARCHAR), '{VAZIO}') v FROM read_parquet({literal(arquivo)})"
        params = []
        if janela:
            sql += f" WHERE CAST({q(cdata)} AS DATE) BETWEEN ? AND ?"
            params = list(janela)
        opcoes[f] = sorted(r[0] for r in con.execute(sql + " ORDER BY 1", params).fetchall())
    return opcoes


def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def montar(projeto: Path) -> dict:
    """Tudo o que o HTML precisa, calculado: spec, métricas, filtros, blocos e metadados."""
    import duckdb

    projeto = Path(projeto)
    modelo, arquivo, _ = carregar(projeto)
    spec = ler_spec(projeto)
    problemas = checar_spec(spec, modelo)
    if problemas:
        raise ErroDeDashboard(f"{ARQUIVO_SPEC} tem {len(problemas)} problema(s)", problemas)
    tokens_rel = spec["estilo"]["tokens"]
    if not (projeto / tokens_rel).is_file():
        raise ErroDeDesign(f"não existe {tokens_rel}", ["defina o visual com /bi-html:design antes de renderizar"])

    mets, dims, fonte = modelo["metricas"], modelo["dimensoes"], modelo["fonte"]
    cdata = fonte.get("coluna_data")
    periodo = spec["periodo"]
    data_max = _data_max(arquivo, cdata) if cdata else None
    janela = resolver_periodo(periodo, data_max) if periodo != "tudo" else None
    comparacoes = {b.get("comparacao") for b in spec["blocos"]} - {None, "nenhuma"}
    filtros_globais = list(spec.get("filtros_globais") or [])

    blocos, avisos = [], []
    con = duckdb.connect()
    try:
        if periodo == "tudo" and cdata:
            ini, fim = con.execute(f"SELECT CAST(min({q(cdata)}) AS DATE), CAST(max({q(cdata)}) AS DATE) "
                                   f"FROM read_parquet({literal(arquivo)})").fetchone()
            rotulo_periodo = f"{_br(ini)} a {_br(fim)}"
        else:
            rotulo_periodo = f"{_br(janela[0])} a {_br(janela[1])}" if janela else "todo o período"
        opcoes = _opcoes_de_filtro(con, arquivo, modelo, filtros_globais, janela)
        for b in spec["blocos"]:
            janelas = {"atual": janela}
            comp = b.get("comparacao")
            if comp not in (None, "nenhuma"):
                janelas["comparacao"] = periodo_de_comparacao(periodo, janela, comp)
            dados, sql = calcular_bloco(con, arquivo, modelo, b, filtros_globais, janelas)
            if b["tipo"] == "mapa_uf":
                valores = {l[b["dimensoes"][0]] for v in dados.values() for l in v["linhas"]}
                fora = sorted(valores - UFS - {VAZIO})
                if fora:
                    avisos.append(f"bloco {b['id']}: valores que não são UF ({', '.join(fora[:5])}) ficam fora do mapa")
            sem_comparacao = comp not in (None, "nenhuma") and all(
                all(l.get(m + "__comparacao") is None for m in b["metricas"]) for v in dados.values() for l in v["linhas"] + [v["total"] or {}])
            if sem_comparacao and b["tipo"] in SEM_DIMENSAO:
                avisos.append(f"bloco {b['id']}: o período de comparação não tem dados")
            blocos.append({**b, "dados": dados,
                           "comparacao_periodo": ({"inicio": _br(janelas["comparacao"][0]), "fim": _br(janelas["comparacao"][1])}
                                                  if "comparacao" in janelas else None),
                           "sql": sql})
    finally:
        con.close()

    usadas = sorted({m for b in spec["blocos"] for m in b["metricas"]})
    manifesto = ler_manifesto(projeto)
    origem_fonte = (manifesto.get("metricas") or {}).get(usadas[0], {}).get("fonte") if usadas else None
    tokens = json.loads((projeto / tokens_rel).read_text(encoding="utf-8"))
    return {
        "spec": {k: v for k, v in spec.items() if k != "blocos"},
        "blocos": blocos,
        "metricas": {m: {"descricao": mets[m]["descricao"], "definicao": definicao(m, mets, fonte),
                         "formato": mets[m]["formato"], "unidade": mets[m].get("unidade"),
                         "melhor": mets[m].get("melhor", "maior")} for m in usadas},
        "dimensoes": {d: {"descricao": dims[d].get("descricao") or d, "granularidade": dims[d].get("granularidade")}
                      for d in set(filtros_globais) | {d for b in spec["blocos"] for d in b.get("dimensoes") or []}},
        "filtros": [{"dimensao": f, "rotulo": dims[f].get("descricao") or f, "opcoes": opcoes[f]} for f in filtros_globais],
        "periodo": {"nome": periodo, "rotulo": rotulo_periodo},
        "fonte": {"arquivo": str(arquivo.relative_to(projeto)),
                  "sha256": (origem_fonte or {}).get("sha256")},
        "origem": spec.get("origem", "planilha_direta"),
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tokens": tokens,
        "avisos": avisos,
        "constantes": {"todos": TODOS, "vazio": VAZIO},
    }
