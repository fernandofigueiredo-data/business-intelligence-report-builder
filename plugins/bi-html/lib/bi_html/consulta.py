"""
Consulta à camada de métricas e exportação do cubo agregado.

`consulta()` é o único caminho para um número do sistema: recebe ids de
métricas e dimensões do modelo (`modelo/metricas.yaml`), filtros por valor de
dimensão e um período relativo, e devolve os valores calculados pelo DuckDB,
já formatados em pt-BR, com a definição de cada métrica e o SQL executado.

`exportar_cubo()` grava o que o dashboard embute: os dados agregados no grão
das dimensões pedidas, guardando componentes somáveis (somas e contagens) para
que o navegador possa refiltrar e reagregar sem errar. Métricas que não se
reagregam (contagem distinta, mínimo, máximo, por dia) vão calculadas no grão
e marcadas como `reagregavel: false`.

Somas usam DECIMAL para não acumular erro de ponto flutuante: o total de uma
coluna em reais bate com o cálculo manual até o centavo.
"""
from __future__ import annotations

import calendar
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from .ingestao import PASTA_BI
from .modelo import ErroDeModelo, OPERADORES, carregar, definicao, literal, q

PERIODOS = ("tudo", "ultimos_trinta_dias", "ultimo_mes", "ultimo_trimestre", "ano_corrente", "ultimo_ano_completo")
COMPARACOES = ("nenhuma", "periodo_anterior", "mesmo_periodo_ano_anterior")
ORDENACOES = ("maior_primeiro", "menor_primeiro", "cronologica", "alfabetica")
CUBOS = PASTA_BI / "cubos"
META_CUBO_BYTES = 5 * 1024 * 1024
DIAS_SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


# ---------------------------------------------------------------- períodos

def _somar_meses(d: date, n: int) -> date:
    mes = d.month - 1 + n
    ano, mes = d.year + mes // 12, mes % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def resolver_periodo(nome: str, data_max: date) -> tuple[date, date] | None:
    """Janela do período relativo, ancorada na data mais recente dos dados."""
    m = data_max
    if nome == "tudo":
        return None
    if nome == "ultimos_trinta_dias":
        return m - timedelta(days=29), m
    if nome == "ultimo_mes":
        return m.replace(day=1), m
    if nome == "ultimo_trimestre":
        return date(m.year, 3 * ((m.month - 1) // 3) + 1, 1), m
    if nome == "ano_corrente":
        return date(m.year, 1, 1), m
    if nome == "ultimo_ano_completo":
        ano = m.year if (m.month, m.day) == (12, 31) else m.year - 1
        return date(ano, 1, 1), date(ano, 12, 31)
    raise ErroDeModelo(f"período {nome!r} fora das opções", list(PERIODOS))


def periodo_de_comparacao(nome: str, janela: tuple[date, date], tipo: str) -> tuple[date, date]:
    inicio, fim = janela
    if tipo == "mesmo_periodo_ano_anterior":
        return _somar_meses(inicio, -12), _somar_meses(fim, -12)
    if nome == "ultimos_trinta_dias":
        return inicio - timedelta(days=30), fim - timedelta(days=30)
    passo = {"ultimo_mes": 1, "ultimo_trimestre": 3, "ano_corrente": 12, "ultimo_ano_completo": 12}[nome]
    novo_fim = _somar_meses(fim, -passo)
    if fim == date(fim.year, fim.month, calendar.monthrange(fim.year, fim.month)[1]):
        novo_fim = date(novo_fim.year, novo_fim.month, calendar.monthrange(novo_fim.year, novo_fim.month)[1])
    return _somar_meses(inicio, -passo), novo_fim


# ---------------------------------------------------------------- SQL das métricas

def _valor_sql(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return literal(v)


def _condicao(filtros) -> str:
    partes = []
    for f in filtros or []:
        op = OPERADORES[f["operador"]]
        if f["operador"] in ("em", "fora_de"):
            partes.append(f"{q(f['coluna'])} {op} ({', '.join(_valor_sql(v) for v in f['valores'])})")
        else:
            partes.append(f"{q(f['coluna'])} {op} {_valor_sql(f['valor'])}")
    return " AND ".join(partes)


def _agregado(funcao: str, filtros) -> str:
    cond = _condicao(filtros)
    return f"{funcao} FILTER (WHERE {cond})" if cond else funcao


def expressao(nome: str, mets: dict, coluna_data: str | None) -> str:
    m = mets[nome]
    t = m["tipo"]
    col = q(m["coluna"]) if m.get("coluna") else None
    filtros = m.get("filtro")
    if t == "soma":
        return _agregado(f"sum(CAST({col} AS DECIMAL(38, 6)))", filtros)
    if t == "contagem":
        return _agregado(f"count({col})" if col else "count(*)", filtros)
    if t == "contagem_distinta":
        return _agregado(f"count(DISTINCT {col})", filtros)
    if t == "media":
        return _agregado(f"avg({col})", filtros)
    if t == "minimo":
        return _agregado(f"min({col})", filtros)
    if t == "maximo":
        return _agregado(f"max({col})", filtros)
    if t == "razao":
        num = expressao(m["numerador"], mets, coluna_data)
        den = expressao(m["denominador"], mets, coluna_data)
        return f"(CAST({num} AS DOUBLE) / NULLIF(CAST({den} AS DOUBLE), 0))"
    base = expressao(m["metrica"], mets, coluna_data)
    if t == "participacao":
        return f"(CAST({base} AS DOUBLE) / NULLIF(CAST(sum({base}) OVER () AS DOUBLE), 0))"
    cd = q(coluna_data)
    return f"(CAST({base} AS DOUBLE) / NULLIF(date_diff('day', CAST(min({cd}) AS DATE), CAST(max({cd}) AS DATE)) + 1, 0))"


def expressao_dimensao(d: dict) -> tuple[str, str]:
    """Expressão SQL da dimensão e a chave de ordenação cronológica correspondente."""
    col = q(d["coluna"])
    g = d.get("granularidade")
    if g is None:
        return col, col
    if g == "dia":
        e = f"CAST({col} AS DATE)"
        return e, e
    if g == "semana":
        e = f"strftime(date_trunc('week', {col}), '%Y-%m-%d')"
        return e, e
    if g == "mes":
        e = f"strftime({col}, '%Y-%m')"
        return e, e
    if g == "trimestre":
        e = f"CAST(year({col}) AS VARCHAR) || '-T' || CAST(quarter({col}) AS VARCHAR)"
        return e, e
    if g == "ano":
        e = f"year({col})"
        return e, e
    nomes = ", ".join(literal(n) for n in DIAS_SEMANA)
    return f"list_extract([{nomes}], isodow({col}))", f"min(isodow({col}))"


# ---------------------------------------------------------------- formatação pt-BR

def _milhar(texto_inteiro: str) -> str:
    neg = texto_inteiro.startswith("-")
    d = texto_inteiro.lstrip("-")
    grupos = []
    while len(d) > 3:
        grupos.insert(0, d[-3:])
        d = d[:-3]
    grupos.insert(0, d)
    return ("-" if neg else "") + ".".join(grupos)


def _numero_br(v: float, casas: int) -> str:
    texto = f"{v:.{casas}f}"
    inteiro, _, frac = texto.partition(".")
    return _milhar(inteiro) + ("," + frac if casas else "")


def formatar(valor, formato: str, unidade: str | None = None) -> str:
    if valor is None:
        return "—"
    v = float(valor)
    if formato == "moeda":
        texto = ("-" if v < 0 else "") + "R$ " + _numero_br(abs(v), 2)
    elif formato == "inteiro":
        texto = _numero_br(round(v), 0)
    elif formato == "percentual":
        texto = _numero_br(100 * v, 1) + "%"
    elif formato == "decimal":
        texto = _numero_br(v, 2)
    else:
        texto = _numero_br(v, 2).rstrip("0").rstrip(",")
    return f"{texto} {unidade}".strip() if unidade else texto


def _json(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


# ---------------------------------------------------------------- consulta

def _validar_pedido(modelo, metricas, dimensoes, filtros, periodo, comparacao, ordenacao):
    mets, dims = modelo["metricas"], modelo["dimensoes"]
    problemas = [f"métrica {m!r} não existe no modelo" for m in metricas if m not in mets]
    problemas += [f"dimensão {d!r} não existe no modelo" for d in dimensoes if d not in dims]
    for f in filtros:
        if f.get("dimensao") not in dims:
            problemas.append(f"filtro: dimensão {f.get('dimensao')!r} não existe no modelo")
        if f.get("operador") not in ("em", "fora_de"):
            problemas.append("filtro: operador deve ser 'em' ou 'fora_de'")
        if not isinstance(f.get("valores"), list) or not f["valores"]:
            problemas.append("filtro: 'valores' deve ser uma lista não vazia")
    if not metricas:
        problemas.append("informe pelo menos uma métrica")
    if periodo not in PERIODOS:
        problemas.append(f"período {periodo!r} fora das opções: {', '.join(PERIODOS)}")
    if comparacao not in COMPARACOES:
        problemas.append(f"comparação {comparacao!r} fora das opções: {', '.join(COMPARACOES)}")
    if ordenacao is not None and ordenacao not in ORDENACOES:
        problemas.append(f"ordenação {ordenacao!r} fora das opções: {', '.join(ORDENACOES)}")
    cdata = modelo["fonte"].get("coluna_data")
    if (periodo != "tudo" or comparacao != "nenhuma") and not cdata:
        problemas.append("períodos e comparações precisam de fonte.coluna_data no modelo")
    if comparacao != "nenhuma" and periodo == "tudo":
        problemas.append("comparação precisa de um período definido (não 'tudo')")
    if comparacao != "nenhuma" and any(dims[d].get("granularidade") for d in dimensoes if d in dims):
        problemas.append("comparação não combina com dimensão de tempo; use a dimensão de tempo sem comparação")
    if problemas:
        raise ErroDeModelo("consulta inválida", problemas)


def _executar(arquivo, modelo, metricas, dimensoes, filtros, janela, ordenacao, limite):
    import duckdb

    mets, dims = modelo["metricas"], modelo["dimensoes"]
    cdata = modelo["fonte"].get("coluna_data")
    selecao, grupos, ordem_crono = [], [], []
    for d in dimensoes:
        e, chave = expressao_dimensao(dims[d])
        selecao.append(f"{e} AS {q(d)}")
        grupos.append(e)
        ordem_crono.append(chave if chave.startswith("min(") else q(d))
    for m in metricas:
        selecao.append(f"{expressao(m, mets, cdata)} AS {q(m)}")
    onde, params = [], []
    if janela:
        onde.append(f"CAST({q(cdata)} AS DATE) BETWEEN ? AND ?")
        params += [janela[0], janela[1]]
    for f in filtros:
        e, _ = expressao_dimensao(dims[f["dimensao"]])
        marcas = ", ".join("?" for _ in f["valores"])
        onde.append(f"CAST({e} AS VARCHAR) {'IN' if f['operador'] == 'em' else 'NOT IN'} ({marcas})")
        params += [str(v) for v in f["valores"]]
    sql = f"SELECT {', '.join(selecao)} FROM read_parquet({literal(arquivo)})"
    if onde:
        sql += " WHERE " + " AND ".join(onde)
    if grupos:
        sql += " GROUP BY " + ", ".join(grupos)
        if ordenacao in ("maior_primeiro", "menor_primeiro"):
            sql += f" ORDER BY {q(metricas[0])} {'DESC' if ordenacao == 'maior_primeiro' else 'ASC'} NULLS LAST, " \
                   + ", ".join(q(d) for d in dimensoes)
        else:
            sql += " ORDER BY " + ", ".join(ordem_crono)
    if limite:
        sql += f" LIMIT {int(limite)}"
    con = duckdb.connect()
    try:
        cursor = con.execute(sql, params)
        nomes = [c[0] for c in cursor.description]
        linhas = [dict(zip(nomes, r)) for r in cursor.fetchall()]
    finally:
        con.close()
    return linhas, sql


def _data_max(arquivo: Path, coluna: str) -> date:
    import duckdb

    con = duckdb.connect()
    try:
        v = con.execute(f"SELECT CAST(max({q(coluna)}) AS DATE) FROM read_parquet({literal(arquivo)})").fetchone()[0]
    finally:
        con.close()
    if v is None:
        raise ErroDeModelo(f"a coluna {coluna} não tem datas preenchidas")
    return v


def consultar(projeto: Path, metricas: list[str], dimensoes: list[str] | None = None,
              filtros: list[dict] | None = None, periodo: str = "tudo", comparacao: str = "nenhuma",
              ordenacao: str | None = None, limite: int | None = None) -> dict:
    """Calcula métricas do modelo. Valores brutos ficam em `linhas`; os textos prontos em `formatado`."""
    dimensoes, filtros = list(dimensoes or []), list(filtros or [])
    modelo, arquivo, _ = carregar(projeto)
    _validar_pedido(modelo, metricas, dimensoes, filtros, periodo, comparacao, ordenacao)
    if limite is not None and not (1 <= int(limite) <= 1000):
        raise ErroDeModelo("consulta inválida", ["limite deve ficar entre 1 e 1000"])
    mets, fonte = modelo["metricas"], modelo["fonte"]
    janela = resolver_periodo(periodo, _data_max(arquivo, fonte["coluna_data"])) if periodo != "tudo" else None
    linhas, sql = _executar(arquivo, modelo, metricas, dimensoes, filtros, janela, ordenacao, limite)

    janela_comp = None
    if comparacao != "nenhuma":
        janela_comp = periodo_de_comparacao(periodo, janela, comparacao)
        anteriores, _ = _executar(arquivo, modelo, metricas, dimensoes, filtros, janela_comp, None, None)
        por_chave = {tuple(l[d] for d in dimensoes): l for l in anteriores}
        for l in linhas:
            antes = por_chave.get(tuple(l[d] for d in dimensoes), {})
            for m in metricas:
                a, b = l.get(m), antes.get(m)
                l[f"{m}__comparacao"] = b
                l[f"{m}__variacao"] = (a - b) if a is not None and b is not None else None
                l[f"{m}__variacao_pct"] = (float(a - b) / abs(float(b))) if a is not None and b else None

    formatado = []
    for l in linhas:
        f = {d: str(_json(l[d])) if l[d] is not None else "—" for d in dimensoes}
        for m in metricas:
            fmt, un = mets[m]["formato"], mets[m].get("unidade")
            f[m] = formatar(l[m], fmt, un)
            if comparacao != "nenhuma":
                f[f"{m}__comparacao"] = formatar(l[f"{m}__comparacao"], fmt, un)
                pct = l[f"{m}__variacao_pct"]
                f[f"{m}__variacao_pct"] = "—" if pct is None else ("▲ " if pct >= 0 else "▼ ") + _numero_br(abs(100 * pct), 1) + "%"
        formatado.append(f)

    return {
        "metricas": metricas,
        "dimensoes": dimensoes,
        "periodo": {"nome": periodo, "inicio": janela[0].isoformat() if janela else None,
                    "fim": janela[1].isoformat() if janela else None},
        "comparacao": {"tipo": comparacao, "inicio": janela_comp[0].isoformat(), "fim": janela_comp[1].isoformat()}
        if janela_comp else None,
        "linhas": linhas,
        "formatado": formatado,
        "definicoes": {m: {"descricao": mets[m]["descricao"], "definicao": definicao(m, mets, fonte)} for m in metricas},
        "sql": sql,
    }


def para_json(resultado: dict) -> dict:
    """Converte Decimal e datas para tipos que o JSON aceita."""
    return {**resultado, "linhas": [{k: _json(v) for k, v in l.items()} for l in resultado["linhas"]]}


# ---------------------------------------------------------------- cubo

def _componentes(nome: str, mets: dict, cdata, saida: dict) -> list[str]:
    """Colunas somáveis de que a métrica depende (preenche `saida` com nome → SQL)."""
    m = mets[nome]
    t = m["tipo"]
    filtros = m.get("filtro")
    if t == "soma":
        saida[f"{nome}__soma"] = expressao(nome, mets, cdata)
        return [f"{nome}__soma"]
    if t == "contagem":
        saida[f"{nome}__n"] = expressao(nome, mets, cdata)
        return [f"{nome}__n"]
    if t == "media":
        col = q(m["coluna"])
        saida[f"{nome}__soma"] = _agregado(f"sum(CAST({col} AS DECIMAL(38, 6)))", filtros)
        saida[f"{nome}__n"] = _agregado(f"count({col})", filtros)
        return [f"{nome}__soma", f"{nome}__n"]
    if t == "razao":
        return _componentes(m["numerador"], mets, cdata, saida) + _componentes(m["denominador"], mets, cdata, saida)
    if t == "participacao":
        return _componentes(m["metrica"], mets, cdata, saida)
    saida[f"{nome}__valor"] = expressao(nome, mets, cdata)
    return [f"{nome}__valor"]


def _receita(nome: str, mets: dict) -> dict:
    """Como o navegador recalcula a métrica a partir dos componentes reagregados."""
    m = mets[nome]
    t = m["tipo"]
    if t == "soma":
        return {"operacao": "soma", "componente": f"{nome}__soma"}
    if t == "contagem":
        return {"operacao": "soma", "componente": f"{nome}__n"}
    if t == "media":
        return {"operacao": "divisao", "numerador": {"operacao": "soma", "componente": f"{nome}__soma"},
                "denominador": {"operacao": "soma", "componente": f"{nome}__n"}}
    if t == "razao":
        return {"operacao": "divisao", "numerador": _receita(m["numerador"], mets),
                "denominador": _receita(m["denominador"], mets)}
    if t == "participacao":
        return {"operacao": "participacao", "de": _receita(m["metrica"], mets)}
    return {"operacao": "valor_no_grao", "componente": f"{nome}__valor"}


def _reagregavel(nome: str, mets: dict) -> bool:
    m = mets[nome]
    if m["tipo"] in ("soma", "contagem", "media"):
        return True
    if m["tipo"] == "razao":
        return _reagregavel(m["numerador"], mets) and _reagregavel(m["denominador"], mets)
    if m["tipo"] == "participacao":
        return _reagregavel(m["metrica"], mets)
    return False


def exportar_cubo(projeto: Path, nome: str, metricas: list[str], dimensoes: list[str],
                  periodo: str = "tudo", comparacao: str = "nenhuma") -> dict:
    """Grava saidas/bi/cubos/<nome>.json com os componentes das métricas no grão das dimensões."""
    import duckdb

    from .ingestao import nome_de_tabela

    projeto = Path(projeto)
    modelo, arquivo, _ = carregar(projeto)
    _validar_pedido(modelo, metricas, [], [], periodo, comparacao, None)
    faltam = [d for d in dimensoes if d not in modelo["dimensoes"]]
    if faltam:
        raise ErroDeModelo("cubo inválido", [f"dimensão {d!r} não existe no modelo" for d in faltam])
    mets, dims, fonte = modelo["metricas"], modelo["dimensoes"], modelo["fonte"]
    cdata = fonte.get("coluna_data")

    componentes: dict[str, str] = {}
    for m in metricas:
        _componentes(m, mets, cdata, componentes)
    janelas = {"atual": resolver_periodo(periodo, _data_max(arquivo, cdata)) if periodo != "tudo" else None}
    if comparacao != "nenhuma":
        janelas["comparacao"] = periodo_de_comparacao(periodo, janelas["atual"], comparacao)

    linhas = []
    con = duckdb.connect()
    try:
        for rotulo, janela in janelas.items():
            selecao = [f"{expressao_dimensao(dims[d])[0]} AS {q(d)}" for d in dimensoes]
            selecao += [f"{sql} AS {q(c)}" for c, sql in componentes.items()]
            consulta = f"SELECT {', '.join(selecao)} FROM read_parquet({literal(arquivo)})"
            params = []
            if janela:
                consulta += f" WHERE CAST({q(cdata)} AS DATE) BETWEEN ? AND ?"
                params = list(janela)
            if dimensoes:
                consulta += " GROUP BY ALL ORDER BY ALL"
            cursor = con.execute(consulta, params)
            nomes = [c[0] for c in cursor.description]
            for r in cursor.fetchall():
                linha = {k: _json(v) for k, v in zip(nomes, r)}
                if comparacao != "nenhuma":
                    linha["_periodo"] = rotulo
                linhas.append(linha)
    finally:
        con.close()

    cubo = {
        "versao": "0.1",
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": str(arquivo.relative_to(projeto)),
        "periodo": {r: ({"inicio": j[0].isoformat(), "fim": j[1].isoformat()} if j else None) for r, j in janelas.items()},
        "dimensoes": {d: {"descricao": dims[d].get("descricao", ""), "granularidade": dims[d].get("granularidade")}
                      for d in dimensoes},
        "metricas": {m: {"descricao": mets[m]["descricao"], "definicao": definicao(m, mets, fonte),
                         "formato": mets[m]["formato"], "unidade": mets[m].get("unidade"),
                         "reagregavel": _reagregavel(m, mets), "receita": _receita(m, mets)} for m in metricas},
        "componentes": list(componentes),
        "linhas": linhas,
    }
    destino = projeto / CUBOS / f"{nome_de_tabela(nome)}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(cubo, ensure_ascii=False, separators=(",", ":"))
    destino.write_text(texto, encoding="utf-8")
    tamanho = len(texto.encode("utf-8"))
    return {
        "arquivo": str(destino.relative_to(projeto)),
        "linhas": len(linhas),
        "bytes": tamanho,
        "dentro_da_meta": tamanho <= META_CUBO_BYTES,
        "nao_reagregaveis": [m for m in metricas if not cubo["metricas"][m]["reagregavel"]],
    }
