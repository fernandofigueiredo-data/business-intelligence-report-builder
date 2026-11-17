"""
Perfil e validação de uma tabela ingerida (atalho sem análise prévia).

Lê `saidas/bi/tabelas/<nome>.parquet` com DuckDB e grava
`saidas/bi/perfil/<nome>.qualidade.json` com:

- por coluna: tipo, vazios, distintos e, conforme o tipo, mínimo, máximo,
  média, zeros, negativos, valores fora da faixa típica, período coberto ou os
  valores mais frequentes;
- na tabela: linhas, linhas repetidas, chaves candidatas, colunas de data;
- dados pessoais detectados (CPF, CNPJ, e-mail, telefone), que bloqueiam a
  publicação até as colunas serem removidas ou agregadas;
- regras bloqueantes e alertas, cada um com uma frase em português.

Todos os números do relatório saem de consultas ao arquivo, não do modelo.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .ingestao import MANIFESTO, PASTA_BI, TABELAS, ErroDeLeitura, ler_manifesto

PERFIL = PASTA_BI / "perfil"
LIMITE_VAZIOS = 0.05

PADROES_PESSOAIS = {
    "cpf": re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$"),
    "cnpj": re.compile(r"^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$"),
    "email": re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$"),
    "telefone": re.compile(r"^(\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}$"),
}
NOMES_PESSOAIS = {"cpf": "cpf", "cnpj": "cnpj", "email": "email", "e_mail": "email", "telefone": "telefone",
                  "celular": "telefone", "fone": "telefone", "rg": "rg", "nome": "nome", "nome_completo": "nome",
                  "endereco": "endereco", "cep": "cep", "data_nascimento": "data_nascimento"}
NUMERICOS = ("inteiro", "decimal")
TEMPORAIS = ("data", "data_hora", "mes")


def _cpf_valido(texto: str) -> bool:
    d = [int(c) for c in texto if c.isdigit()]
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        resto = sum(x * p for x, p in zip(d[:n], range(n + 1, 1, -1))) % 11
        if d[n] != (0 if resto < 2 else 11 - resto):
            return False
    return True


def _q(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def _detectar_pessoal(nome: str, amostra: list[str]) -> dict | None:
    """Tipo de dado pessoal da coluna, pelo conteúdo (forte) ou pelo nome (fraco)."""
    if amostra:
        for tipo, rx in PADROES_PESSOAIS.items():
            casam = [v for v in amostra if rx.match(v.strip())]
            if tipo == "cpf":
                casam = [v for v in casam if _cpf_valido(v)]
            if len(casam) >= 0.5 * len(amostra):
                return {"tipo": tipo, "evidencia": "conteudo", "proporcao_na_amostra": round(len(casam) / len(amostra), 2)}
    tipo = NOMES_PESSOAIS.get(nome)
    return {"tipo": tipo, "evidencia": "nome_da_coluna"} if tipo else None


def perfilar(projeto: Path, nome: str) -> dict:
    import duckdb

    projeto = Path(projeto)
    manifesto = ler_manifesto(projeto)
    registro = manifesto["tabelas"].get(nome)
    if registro is None:
        disponiveis = ", ".join(sorted(manifesto["tabelas"])) or "nenhuma"
        raise ErroDeLeitura(f"a tabela {nome!r} não foi ingerida", [f"tabelas ingeridas: {disponiveis}"])
    arquivo = projeto / registro["parquet"]
    tipos = {c["nome"]: c["tipo"] for c in registro["colunas"]}

    con = duckdb.connect()
    literal = "'" + str(arquivo).replace("'", "''") + "'"
    con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet({literal})")
    total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    repetidas = con.execute("SELECT count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM t)) FROM t").fetchone()[0]

    colunas, chaves, bloqueios, alertas, pessoais = [], [], [], [], []
    for col, tipo in tipos.items():
        q = _q(col)
        vazios, distintos = con.execute(f"SELECT count(*) - count({q}), count(DISTINCT {q}) FROM t").fetchone()
        info = {"coluna": col, "tipo": tipo, "vazios": vazios,
                "vazios_pct": round(100 * vazios / total, 1) if total else 0.0, "distintos": distintos}
        if tipo in NUMERICOS:
            mn, mx, media, zeros, neg, q1, q3 = con.execute(
                f"SELECT min({q}), max({q}), avg({q}), count(*) FILTER ({q} = 0), count(*) FILTER ({q} < 0), "
                f"quantile_cont({q}, 0.25), quantile_cont({q}, 0.75) FROM t").fetchone()
            faixa = (q3 - q1) if q1 is not None else 0
            fora = con.execute(f"SELECT count(*) FROM t WHERE {q} < ? OR {q} > ?",
                               [q1 - 3 * faixa, q3 + 3 * faixa]).fetchone()[0] if faixa else 0
            info.update({"minimo": mn, "maximo": mx, "media": round(media, 4) if media is not None else None,
                         "zeros": zeros, "negativos": neg, "fora_da_faixa_tipica": fora})
        elif tipo in TEMPORAIS:
            inicio, fim = con.execute(f"SELECT min({q}), max({q}) FROM t").fetchone()
            info.update({"inicio": str(inicio) if inicio else None, "fim": str(fim) if fim else None})
            if tipo == "data" and inicio:
                dias_com = con.execute(f"SELECT count(DISTINCT {q}) FROM t").fetchone()[0]
                info["dias_no_periodo"] = (fim - inicio).days + 1
                info["dias_sem_registro"] = info["dias_no_periodo"] - dias_com
        else:
            frequentes = con.execute(
                f"SELECT {q}, count(*) n FROM t WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1 LIMIT 5").fetchall()
            info["mais_frequentes"] = [{"valor": v, "linhas": n} for v, n in frequentes]
        if tipo == "texto":
            amostra = [r[0] for r in con.execute(
                f"SELECT DISTINCT {q} FROM t WHERE {q} IS NOT NULL LIMIT 2000").fetchall()]
        else:
            amostra = []
        achado = _detectar_pessoal(col, amostra) if tipo in ("texto", "inteiro", "data") else None
        if achado:
            info["dado_pessoal"] = achado
            pessoais.append({"coluna": col, **achado})
        if total and vazios == 0 and distintos == total:
            chaves.append(col)
        obs = next((c.get("obs") for c in registro["colunas"] if c["nome"] == col), None)
        if obs:
            info["leitura"] = obs
        colunas.append(info)

    con.close()

    # regras
    if total == 0:
        bloqueios.append("a tabela não tem linhas")
    if not any(t in NUMERICOS for t in tipos.values()):
        bloqueios.append("não há nenhuma coluna numérica: o dashboard não tem o que somar ou contar além de linhas")
    for c in colunas:
        if c["vazios"] and c["vazios"] / total > LIMITE_VAZIOS:
            alertas.append(f"{c['coluna']}: {c['vazios_pct']}% de valores vazios")
        # Valores fora da faixa típica ficam só na estatística da coluna: em vendas e finanças
        # a cauda longa é normal, e alertar sempre ensinaria o usuário a ignorar alertas.
        # O que costuma ser erro de digitação é o negativo raro numa coluna quase toda positiva.
        if c.get("negativos") and c["negativos"] <= max(1, 0.01 * total):
            alertas.append(f"{c['coluna']}: {c['negativos']} valor(es) negativo(s) numa coluna quase toda positiva")
        # Dias sem registro só importam em série diária densa (vendas por dia, mídia por dia);
        # numa data esparsa, como a de cadastro, lacuna é o esperado.
        if c.get("dias_sem_registro") and c["dias_no_periodo"] - c["dias_sem_registro"] >= 0.5 * c["dias_no_periodo"]:
            alertas.append(f"{c['coluna']}: {c['dias_sem_registro']} dias sem registro entre {c['inicio']} e {c['fim']}")
        leitura = c.get("leitura") or {}
        if "quase_numerica" in leitura:
            ex = ", ".join(repr(e) for e in leitura["quase_numerica"]["exemplos"])
            alertas.append(f"{c['coluna']}: parece numérica, mas ficou como texto por causa de valores como {ex}")
        if "formato_ambiguo" in leitura:
            alertas.append(f"{c['coluna']}: {leitura['formato_ambiguo']}")
    if repetidas:
        alertas.append(f"{repetidas} linhas repetidas (todas as colunas iguais)")
    if pessoais:
        lista = ", ".join(f"{p['coluna']} ({p['tipo']})" for p in pessoais)
        alertas.append(f"dados pessoais detectados em {lista}: a publicação fica bloqueada até remover ou agregar")

    situacao = "bloqueado" if bloqueios else ("com_alertas" if alertas else "ok")
    relatorio = {
        "tabela": nome,
        "origem": registro["origem"],
        "sha256": registro["sha256"],
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "situacao": situacao,
        "publicacao_bloqueada": bool(pessoais) or bool(bloqueios),
        "linhas": total,
        "linhas_repetidas": repetidas,
        "chaves_candidatas": chaves,
        "colunas_de_data": [c for c, t in tipos.items() if t in TEMPORAIS],
        "dados_pessoais": pessoais,
        "bloqueios": bloqueios,
        "alertas": alertas,
        "colunas": colunas,
    }
    destino = projeto / PERFIL / f"{nome}.qualidade.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    manifesto["tabelas"][nome]["qualidade"] = str(destino.relative_to(projeto))
    manifesto["tabelas"][nome]["situacao"] = situacao
    manifesto["eventos"].append({"quando": relatorio["gerado_em"], "evento": "perfil", "tabela": nome,
                                 "situacao": situacao})
    (projeto / MANIFESTO).write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str) + "\n",
                                     encoding="utf-8")
    return relatorio


def resumo(relatorio: dict) -> dict:
    """Versão curta do relatório para a conversa: sem a lista completa de colunas."""
    return {
        "tabela": relatorio["tabela"],
        "situacao": relatorio["situacao"],
        "publicacao_bloqueada": relatorio["publicacao_bloqueada"],
        "linhas": relatorio["linhas"],
        "colunas": [{"coluna": c["coluna"], "tipo": c["tipo"], "vazios": c["vazios"]} for c in relatorio["colunas"]],
        "colunas_de_data": relatorio["colunas_de_data"],
        "chaves_candidatas": relatorio["chaves_candidatas"],
        "dados_pessoais": relatorio["dados_pessoais"],
        "bloqueios": relatorio["bloqueios"],
        "alertas": relatorio["alertas"],
        "arquivo": str(PERFIL / f"{relatorio['tabela']}.qualidade.json"),
    }
