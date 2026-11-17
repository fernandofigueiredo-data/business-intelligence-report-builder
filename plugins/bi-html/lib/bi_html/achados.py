"""
Motor de achados: fatos calculados que o documento de decisão pode citar.

O Claude não calcula nada no documento de decisão. Ele recebe uma lista de
achados, cada um com valores já calculados pela camada de métricas, e só
redige. O verificador (`verificador.py`) confere depois que todo número do
texto corresponde a um valor daqui.

Achados gerados (a partir do modelo e da spec do dashboard):
- `total`: a métrica principal no período, com a comparação quando a spec pede;
- `lider`, `concentracao`: quem lidera cada dimensão e quantos grupos somam 80%;
- `amplitude`: a menor e a maior razão (ticket, margem, custo) entre os grupos;
- `tempo`: primeiro, último, maior e menor ponto da série mensal;
- `cobertura`: período, registros, anos distintos e vazios, que alimentam a
  seção de limites.

Grava `saidas/bi/achados.json`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .consulta import consultar, formatar
from .dashboard import ler_spec
from .ingestao import PASTA_BI
from .modelo import carregar, definicao, literal, q

ARQUIVO = PASTA_BI / "achados.json"


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


def _metrica_principal(modelo: dict, spec: dict | None) -> str:
    mets = modelo["metricas"]
    if spec:
        for b in spec["blocos"]:
            if b["tipo"] == "numero_destaque":
                return b["metricas"][0]
    somas = [m for m, d in mets.items() if d["tipo"] == "soma" and d["formato"] == "moeda"]
    return (somas or [m for m, d in mets.items() if d["tipo"] in ("soma", "contagem")] or list(mets))[0]


def _dimensoes_categoricas(modelo: dict, spec: dict | None) -> list[str]:
    dims = modelo["dimensoes"]
    usadas = []
    if spec:
        for d in list(spec.get("filtros_globais") or []) + [d for b in spec["blocos"] for d in b.get("dimensoes") or []]:
            if d in dims and not dims[d].get("granularidade") and d not in usadas:
                usadas.append(d)
    return usadas or [d for d, v in dims.items() if not v.get("granularidade")][:3]


def _dimensao_mensal(modelo: dict) -> str | None:
    return next((d for d, v in modelo["dimensoes"].items() if v.get("granularidade") == "mes"), None)


def _razoes(modelo: dict, principal: str, spec: dict | None) -> list[str]:
    mets = modelo["metricas"]
    nomes = [m for m, d in mets.items() if d["tipo"] in ("razao", "media") and m != principal]
    if spec:
        usadas = {m for b in spec["blocos"] for m in b["metricas"]}
        nomes = [m for m in nomes if m in usadas] or nomes
    return nomes[:3]


NAO_INFORMADO = {"não informada", "não informado", "nao informada", "nao informado", "(não informado)", "sem região", ""}


def _informado(valor) -> bool:
    return valor is not None and str(valor).strip().lower() not in NAO_INFORMADO


def _contador(modelo: dict) -> str | None:
    """Métrica que conta registros (vendas, pedidos), para mostrar o n junto das participações."""
    mets = modelo["metricas"]
    return next((m for m, d in mets.items() if d["tipo"] in ("contagem", "contagem_distinta") and not d.get("filtro")), None)


def _fmt(v, metrica: dict) -> str:
    return formatar(v, metrica["formato"], metrica.get("unidade"))


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


def _mes(chave: str) -> str:
    """'2025-11' → 'novembro de 2025'."""
    return f"{MESES[int(chave[5:7]) - 1]} de {chave[:4]}" if chave and len(chave) == 7 else str(chave)


def _pct(v) -> str:
    return formatar(v, "percentual")


def gerar(projeto: Path) -> dict:
    """Calcula os achados e grava saidas/bi/achados.json."""
    import duckdb

    projeto = Path(projeto)
    modelo, arquivo, _ = carregar(projeto)
    spec = ler_spec(projeto) if (projeto / "dashboard" / "spec.json").is_file() else None
    mets, dims, fonte = modelo["metricas"], modelo["dimensoes"], modelo["fonte"]
    principal = _metrica_principal(modelo, spec)
    mp = mets[principal]
    periodo = (spec or {}).get("periodo", "tudo")
    comparacao = "nenhuma"
    if spec and periodo != "tudo":
        comparacao = next((b.get("comparacao") for b in spec["blocos"]
                           if b["tipo"] == "numero_destaque" and b.get("comparacao") not in (None, "nenhuma", "meta")),
                          "nenhuma")
    achados: list[dict] = []

    def novo(tipo, titulo, metricas, valores, formatado, consulta, dimensao=None):
        achados.append({"id": f"A{len(achados) + 1}", "tipo": tipo, "titulo": titulo, "metricas": metricas,
                        "dimensao": dimensao, "valores": valores, "formatado": formatado, "consulta": consulta})

    # total
    r = consultar(projeto, [principal], periodo=periodo, comparacao=comparacao)
    l = r["linhas"][0]
    valores = {"valor": _f(l[principal])}
    formatado = {"valor": _fmt(l[principal], mp)}
    if comparacao != "nenhuma" and l.get(f"{principal}__comparacao") is not None:
        valores |= {"anterior": _f(l[f"{principal}__comparacao"]), "variacao_pct": l[f"{principal}__variacao_pct"],
                    "variacao": _f(l[f"{principal}__variacao"])}
        formatado |= {"anterior": _fmt(l[f"{principal}__comparacao"], mp), "variacao_pct": _pct(l[f"{principal}__variacao_pct"]),
                      "variacao": _fmt(l[f"{principal}__variacao"], mp)}
    novo("total", f"{mp['descricao']} no período", [principal], valores, formatado,
         {"metricas": [principal], "periodo": periodo, "comparacao": comparacao})
    periodo_r, comparacao_r = r["periodo"], r["comparacao"]

    # líder e concentração por dimensão
    for d in _dimensoes_categoricas(modelo, spec):
        r = consultar(projeto, [principal], [d], periodo=periodo, ordenacao="maior_primeiro")
        linhas = [x for x in r["linhas"] if x[principal] is not None]
        total = sum(Decimal(str(x[principal])) for x in linhas)
        if len(linhas) < 2 or not total:
            continue
        rotulo = dims[d].get("descricao") or d
        if any(x[principal] < 0 for x in linhas):
            # Sinais misturados (receitas e despesas): participação no total não tem sentido.
            # O achado é a composição: a maior entrada, a maior saída e o peso da saída sobre as entradas.
            entradas = sum(Decimal(str(x[principal])) for x in linhas if x[principal] > 0)
            pos, neg = linhas[0], linhas[-1]
            peso = float(-Decimal(str(neg[principal])) / entradas) if entradas else None
            novo("composicao", f"Maiores entradas e saídas por {rotulo.lower()}", [principal],
                 {"maior_entrada": _f(pos[principal]), "maior_saida": _f(neg[principal]),
                  "saida_sobre_entradas_pct": peso, "entradas": float(entradas)},
                 {"maior_entrada": _fmt(pos[principal], mp), "grupo_entrada": str(pos[d]),
                  "maior_saida": _fmt(neg[principal], mp), "grupo_saida": str(neg[d]),
                  "saida_sobre_entradas_pct": _pct(peso) if peso is not None else "—",
                  "entradas": _fmt(float(entradas), mp)},
                 {"metricas": [principal], "dimensoes": [d], "periodo": periodo, "ordenacao": "maior_primeiro"}, d)
            continue
        lider = linhas[0]
        fatia = float(Decimal(str(lider[principal])) / total)
        acumulado, k = Decimal(0), 0
        for x in linhas:
            acumulado += Decimal(str(x[principal]))
            k += 1
            if acumulado / total >= Decimal("0.8"):
                break
        nome_lider = lider[d] if lider[d] is not None else "(não informado)"
        valores = {"valor": _f(lider[principal]), "participacao": fatia, "grupos": len(linhas),
                   "valor_segundo": _f(linhas[1][principal])}
        formatado = {"valor": _fmt(lider[principal], mp), "participacao": _pct(fatia), "grupos": str(len(linhas)),
                     "lider": str(nome_lider), "valor_segundo": _fmt(linhas[1][principal], mp),
                     "segundo": str(linhas[1][d] if linhas[1][d] is not None else "(não informado)")}
        metricas_achado = [principal]
        contador = _contador(modelo)
        if contador and contador != principal:
            rc = consultar(projeto, [contador], [d], periodo=periodo)
            por_grupo = {x[d]: x[contador] for x in rc["linhas"]}
            total_n = sum(v for v in por_grupo.values() if v is not None)
            n_lider, n_segundo = por_grupo.get(lider[d]), por_grupo.get(linhas[1][d])
            mc = mets[contador]
            valores |= {"contagem": n_lider, "contagem_total": total_n, "contagem_segundo": n_segundo,
                        "contagem_participacao": n_lider / total_n if total_n else None}
            formatado |= {"contagem": _fmt(n_lider, mc), "contagem_total": _fmt(total_n, mc),
                          "contagem_segundo": _fmt(n_segundo, mc),
                          "contagem_participacao": _pct(n_lider / total_n) if total_n else "—"}
            metricas_achado.append(contador)
        novo("lider", f"{nome_lider} lidera {mp['descricao'].lower()} por {rotulo.lower()}", metricas_achado,
             valores, formatado,
             {"metricas": metricas_achado, "dimensoes": [d], "periodo": periodo, "ordenacao": "maior_primeiro"}, d)
        segundo = linhas[1]
        novo("concentracao", f"Quantos grupos de {rotulo.lower()} somam oitenta por cento", [principal],
             {"grupos_para_oitenta_pct": k, "grupos": len(linhas),
              "participacao_segundo": float(Decimal(str(segundo[principal])) / total)},
             {"grupos_para_oitenta_pct": str(k), "grupos": str(len(linhas)),
              "segundo": str(segundo[d] if segundo[d] is not None else "(não informado)"),
              "participacao_segundo": _pct(float(Decimal(str(segundo[principal])) / total))},
             {"metricas": [principal], "dimensoes": [d], "periodo": periodo}, d)
        # amplitude das razões entre os grupos dessa dimensão
        for razao in _razoes(modelo, principal, spec):
            rr = consultar(projeto, [razao], [d], periodo=periodo, ordenacao="maior_primeiro")
            vals = [x for x in rr["linhas"] if x[razao] is not None and _informado(x[d])]
            if len(vals) < 2:
                continue
            maior, menor = vals[0], vals[-1]
            diferenca = (_f(maior[razao]) / _f(menor[razao]) - 1) if _f(menor[razao]) else None
            mr = mets[razao]
            novo("amplitude", f"{mr['descricao']} entre os grupos de {rotulo.lower()}", [razao],
                 {"maior": _f(maior[razao]), "menor": _f(menor[razao]), "diferenca_pct": diferenca, "grupos": len(vals)},
                 {"maior": _fmt(maior[razao], mr), "menor": _fmt(menor[razao], mr),
                  "diferenca_pct": _pct(diferenca) if diferenca is not None else "—",
                  "grupo_maior": str(maior[d]), "grupo_menor": str(menor[d]), "grupos": str(len(vals))},
                 {"metricas": [razao], "dimensoes": [d], "periodo": periodo, "ordenacao": "maior_primeiro"}, d)

    # pares de métricas com o mesmo formato lado a lado num bloco (realizado × orçado, por exemplo)
    vistos = set()
    for b in (spec or {}).get("blocos", []):
        if b["tipo"] not in ("barras_agrupadas", "linha_tempo", "tabela"):
            continue
        ms_bloco = [m for m in b["metricas"] if mets[m]["tipo"] in ("soma", "contagem")]
        for a_, b_ in zip(ms_bloco, ms_bloco[1:]):
            if mets[a_]["formato"] != mets[b_]["formato"] or (a_, b_) in vistos:
                continue
            vistos.add((a_, b_))
            r = consultar(projeto, [a_, b_], periodo=periodo)["linhas"][0]
            va, vb = _f(r[a_]), _f(r[b_])
            if va is None or not vb:
                continue
            novo("comparacao_metricas", f"{mets[a_]['descricao']} contra {mets[b_]['descricao'].lower()}", [a_, b_],
                 {"a": va, "b": vb, "diferenca": va - vb, "diferenca_pct": va / vb - 1},
                 {"a": _fmt(va, mets[a_]), "b": _fmt(vb, mets[b_]), "diferenca": _fmt(va - vb, mets[a_]),
                  "diferenca_pct": _pct(va / vb - 1)},
                 {"metricas": [a_, b_], "periodo": periodo})

    # série mensal
    tempo = _dimensao_mensal(modelo)
    if tempo:
        por_dia = next((m for m, x in mets.items() if x["tipo"] == "por_dia" and x.get("metrica") == principal), None)
        serie_m = por_dia or principal
        ms = mets[serie_m]
        r = consultar(projeto, [serie_m], [tempo], periodo=periodo, ordenacao="cronologica")
        pontos = [x for x in r["linhas"] if x[serie_m] is not None]
        if len(pontos) >= 3:
            maior = max(pontos, key=lambda x: x[serie_m])
            menor = min(pontos, key=lambda x: x[serie_m])
            media = sum(_f(x[serie_m]) for x in pontos) / len(pontos)
            ultimo, penultimo = pontos[-1], pontos[-2]
            serie_val = {f"mes_{x[tempo]}": _f(x[serie_m]) for x in pontos}
            serie_fmt = {f"mes_{x[tempo]}": f"{_mes(x[tempo])}: {_fmt(x[serie_m], ms)}" for x in pontos}
            novo("tempo", f"{ms['descricao']} mês a mês", [serie_m],
                 serie_val | {"maior": _f(maior[serie_m]), "menor": _f(menor[serie_m]), "media": media,
                  "maior_vs_media_pct": _f(maior[serie_m]) / media - 1,
                  "ultimo": _f(ultimo[serie_m]), "ultimo_vs_anterior_pct": _f(ultimo[serie_m]) / _f(penultimo[serie_m]) - 1,
                  "meses": len(pontos)},
                 {"maior": _fmt(maior[serie_m], ms), "menor": _fmt(menor[serie_m], ms), "media": _fmt(media, ms),
                  "maior_vs_media_pct": _pct(_f(maior[serie_m]) / media - 1), "mes_maior": _mes(maior[tempo]),
                  "mes_menor": _mes(menor[tempo]), "ultimo": _fmt(ultimo[serie_m], ms), "mes_ultimo": _mes(ultimo[tempo]),
                  "ultimo_vs_anterior_pct": _pct(_f(ultimo[serie_m]) / _f(penultimo[serie_m]) - 1),
                  "meses": str(len(pontos))} | serie_fmt,
                 {"metricas": [serie_m], "dimensoes": [tempo], "periodo": periodo, "ordenacao": "cronologica"}, tempo)

    # cobertura (para a seção de limites)
    con = duckdb.connect()
    try:
        cd = fonte.get("coluna_data")
        sel = "count(*)"
        if cd:
            sel += f", CAST(min({q(cd)}) AS DATE), CAST(max({q(cd)}) AS DATE), count(DISTINCT year({q(cd)}))"
        linha = con.execute(f"SELECT {sel} FROM read_parquet({literal(arquivo)})").fetchone()
        vazios = {}
        for d in _dimensoes_categoricas(modelo, spec):
            col = dims[d]["coluna"]
            n = con.execute(f"SELECT count(*) - count({q(col)}) FROM read_parquet({literal(arquivo)})").fetchone()[0]
            if n:
                vazios[d] = n
    finally:
        con.close()
    cob_val = {"registros": linha[0]}
    cob_fmt = {"registros": formatar(linha[0], "inteiro")}
    if cd:
        cob_val |= {"anos": linha[3]}
        from .consulta import _data_max

        fim = _data_max(arquivo, cd)
        cob_fmt |= {"inicio": linha[1].strftime("%d/%m/%Y"), "fim": fim.strftime("%d/%m/%Y"), "anos": str(linha[3])}
    for d, n in vazios.items():
        cob_val[f"vazios_{d}"] = n
        cob_val[f"vazios_{d}_pct"] = n / linha[0]
        cob_fmt[f"vazios_{d}"] = formatar(n, "inteiro")
        cob_fmt[f"vazios_{d}_pct"] = _pct(n / linha[0])
    novo("cobertura", "O que os dados cobrem", [], cob_val, cob_fmt, {"periodo": "tudo"})

    resultado = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metrica_principal": principal,
        "periodo": periodo_r,
        "comparacao": comparacao_r,
        "definicoes": {m: {"descricao": mets[m]["descricao"], "definicao": definicao(m, mets, fonte)}
                       for m in sorted({m for a in achados for m in a["metricas"]})},
        "achados": achados,
    }
    destino = projeto / ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return resultado


def ler(projeto: Path) -> dict:
    caminho = Path(projeto) / ARQUIVO
    if not caminho.is_file():
        from .ingestao import ErroDeLeitura

        raise ErroDeLeitura("ainda não há achados calculados", ["chame gerar_achados primeiro"])
    return json.loads(caminho.read_text(encoding="utf-8"))
