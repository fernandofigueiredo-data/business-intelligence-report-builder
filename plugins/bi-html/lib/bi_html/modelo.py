"""
Modelo de métricas: `modelo/metricas.yaml` na pasta do projeto.

O modelo é a única definição de cada número do sistema. Ele diz de onde vêm os
dados (`fonte`), por quais dimensões dá para abrir (`dimensoes`) e como cada
métrica é calculada (`metricas`). O Claude propõe, o usuário confirma, e este
módulo valida e registra a linhagem de cada métrica no manifesto.

Formato (versão 0.1):

    versao: "0.1"
    fonte:
      tabela: vendas                          # tabela ingerida (saidas/bi/tabelas/vendas.parquet)
      # ou: arquivo: saidas/dados_tratados.parquet   (entregue pela análise)
      coluna_data: data_pedido                # obrigatória para períodos e dimensões de tempo
    dimensoes:
      regiao: {coluna: regiao, descricao: Região do cliente}
      mes: {coluna: data_pedido, granularidade: mes, descricao: Mês do pedido}
    metricas:
      receita_total:
        descricao: Soma da receita dos pedidos
        tipo: soma
        coluna: receita
        formato: moeda
      pedidos: {descricao: Quantidade de pedidos, tipo: contagem, formato: inteiro}
      ticket_medio: {descricao: Receita por pedido, tipo: razao, numerador: receita_total,
                     denominador: pedidos, formato: moeda}

Tipos de métrica:
- `soma`, `media`, `minimo`, `maximo`, `contagem_distinta` (com `coluna`);
- `contagem` (linhas; `coluna` opcional conta os valores preenchidos);
- `razao` (`numerador` / `denominador`, outras métricas);
- `participacao` (`metrica` dividida pelo total de todas as linhas do resultado);
- `por_dia` (`metrica` dividida pelos dias entre o primeiro e o último registro do grupo).

Toda métrica aceita `melhor: menor` para indicar que cair é bom (custos, prazos): o dashboard
pinta a variação de verde quando ela cai. Toda métrica aceita `filtro`: lista de condições `{coluna, operador, valor | valores}`
com operador `igual`, `diferente`, `em`, `fora_de`, `maior`, `menor`, `maior_igual`,
`menor_igual`, `preenchido` ou `vazio` (os dois últimos sem valor). Não há SQL livre no modelo: colunas são conferidas contra o
arquivo e valores entram como parâmetros.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .ingestao import MANIFESTO, ErroDeLeitura, ler_manifesto

ARQUIVO_MODELO = Path("modelo") / "metricas.yaml"
VERSAO = "0.1"
ID = re.compile(r"^[a-z][a-z_]{0,47}$")
TIPOS = {"soma", "media", "minimo", "maximo", "contagem", "contagem_distinta", "razao", "participacao", "por_dia"}
COM_COLUNA = {"soma", "media", "minimo", "maximo", "contagem_distinta"}
NUMERICAS = {"soma", "media"}
FORMATOS = {"moeda", "inteiro", "decimal", "percentual", "numero"}
GRANULARIDADES = {"dia", "semana", "mes", "trimestre", "ano", "dia_semana"}
OPERADORES = {"igual": "=", "diferente": "<>", "maior": ">", "menor": "<", "maior_igual": ">=",
              "menor_igual": "<=", "em": "IN", "fora_de": "NOT IN", "preenchido": "IS NOT NULL", "vazio": "IS NULL"}
SEM_VALOR = {"preenchido", "vazio"}
TIPOS_NUMERICOS_DUCKDB = ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "FLOAT", "DOUBLE", "DECIMAL",
                          "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT")
TIPOS_DATA_DUCKDB = ("DATE", "TIMESTAMP")


class ErroDeModelo(ErroDeLeitura):
    """Modelo de métricas inválido; `detalhes` lista cada problema."""


def q(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def literal(texto: str) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------- fonte

def arquivo_da_fonte(projeto: Path, fonte: dict) -> Path:
    if "tabela" in fonte:
        registro = ler_manifesto(projeto)["tabelas"].get(fonte["tabela"])
        if not registro:
            raise ErroDeModelo(f"a tabela {fonte['tabela']!r} da fonte não foi ingerida",
                               ["rode /bi-html:ingerir ou aponte a fonte para o arquivo da análise"])
        return projeto / registro["parquet"]
    return projeto / fonte["arquivo"]


def esquema(arquivo: Path) -> dict[str, str]:
    import duckdb

    con = duckdb.connect()
    try:
        linhas = con.execute(f"DESCRIBE SELECT * FROM read_parquet({literal(arquivo)})").fetchall()
    finally:
        con.close()
    return {nome: tipo for nome, tipo, *_ in linhas if nome != "__index_level_0__"}


# ---------------------------------------------------------------- validação

def _validar_filtro(filtros, onde, colunas, problemas):
    if filtros is None:
        return
    if not isinstance(filtros, list):
        problemas.append(f"{onde}.filtro: deve ser uma lista de condições")
        return
    for i, f in enumerate(filtros):
        lugar = f"{onde}.filtro[{i}]"
        if not isinstance(f, dict):
            problemas.append(f"{lugar}: condição deve ter coluna, operador e valor")
            continue
        if f.get("coluna") not in colunas:
            problemas.append(f"{lugar}: coluna {f.get('coluna')!r} não existe nos dados")
        op = f.get("operador")
        if op not in OPERADORES:
            problemas.append(f"{lugar}: operador {op!r} fora das opções: {', '.join(OPERADORES)}")
        elif op in ("em", "fora_de"):
            if not isinstance(f.get("valores"), list) or not f["valores"]:
                problemas.append(f"{lugar}: operador {op} precisa de 'valores' (lista)")
        elif op in SEM_VALOR:
            if "valor" in f or "valores" in f:
                problemas.append(f"{lugar}: operador {op} não leva valor")
        elif "valor" not in f:
            problemas.append(f"{lugar}: operador {op} precisa de 'valor'")


def validar(modelo: dict, colunas: dict[str, str]) -> list[str]:
    """Problemas do modelo, conferido contra o esquema real do arquivo da fonte."""
    p: list[str] = []
    if str(modelo.get("versao")) != VERSAO:
        p.append(f"versao: deve ser \"{VERSAO}\"")
    fonte = modelo.get("fonte") or {}
    if ("tabela" in fonte) == ("arquivo" in fonte):
        p.append("fonte: informe 'tabela' (ingerida) ou 'arquivo' (parquet da análise), um dos dois")
    cdata = fonte.get("coluna_data")
    if cdata is not None and (cdata not in colunas or not colunas[cdata].startswith(TIPOS_DATA_DUCKDB)):
        p.append(f"fonte.coluna_data: {cdata!r} não é uma coluna de data nos dados")

    dims = modelo.get("dimensoes") or {}
    mets = modelo.get("metricas") or {}
    if not mets:
        p.append("metricas: o modelo precisa de pelo menos uma métrica")
    for nome in set(dims) & set(mets):
        p.append(f"{nome}: o mesmo id não pode ser dimensão e métrica")

    for nome, d in dims.items():
        lugar = f"dimensoes.{nome}"
        if not ID.match(nome):
            p.append(f"{lugar}: id deve ter só minúsculas e sublinhado, sem algarismos")
        if not isinstance(d, dict) or d.get("coluna") not in colunas:
            p.append(f"{lugar}: coluna {d.get('coluna') if isinstance(d, dict) else d!r} não existe nos dados")
            continue
        g = d.get("granularidade")
        if g is not None:
            if g not in GRANULARIDADES:
                p.append(f"{lugar}.granularidade: {g!r} fora das opções: {', '.join(sorted(GRANULARIDADES))}")
            elif not colunas[d["coluna"]].startswith(TIPOS_DATA_DUCKDB):
                p.append(f"{lugar}: granularidade só vale para coluna de data")

    for nome, m in mets.items():
        lugar = f"metricas.{nome}"
        if not ID.match(nome):
            p.append(f"{lugar}: id deve ter só minúsculas e sublinhado, sem algarismos")
        if not isinstance(m, dict):
            p.append(f"{lugar}: deve ser um bloco com descricao e tipo")
            continue
        if not str(m.get("descricao", "")).strip():
            p.append(f"{lugar}.descricao: obrigatória (é a definição que o leitor vê)")
        tipo = m.get("tipo")
        if tipo not in TIPOS:
            p.append(f"{lugar}.tipo: {tipo!r} fora das opções: {', '.join(sorted(TIPOS))}")
            continue
        if m.get("melhor", "maior") not in ("maior", "menor"):
            p.append(f"{lugar}.melhor: use 'maior' (padrão) ou 'menor', para custos e prazos")
        if m.get("formato") not in FORMATOS:
            p.append(f"{lugar}.formato: {m.get('formato')!r} fora das opções: {', '.join(sorted(FORMATOS))}")
        col = m.get("coluna")
        if tipo in COM_COLUNA or (tipo == "contagem" and col is not None):
            if col not in colunas:
                p.append(f"{lugar}.coluna: {col!r} não existe nos dados")
            elif tipo in NUMERICAS and not colunas[col].startswith(TIPOS_NUMERICOS_DUCKDB):
                p.append(f"{lugar}.coluna: {col} é {colunas[col]}, e {tipo} precisa de coluna numérica")
        if tipo == "razao":
            for lado in ("numerador", "denominador"):
                if m.get(lado) not in mets:
                    p.append(f"{lugar}.{lado}: {m.get(lado)!r} não é métrica do modelo")
        if tipo in ("participacao", "por_dia"):
            base = m.get("metrica")
            if base not in mets:
                p.append(f"{lugar}.metrica: {base!r} não é métrica do modelo")
            elif mets[base].get("tipo") not in ("soma", "contagem"):
                p.append(f"{lugar}.metrica: {tipo} só se aplica a soma ou contagem")
        if tipo == "por_dia" and not cdata:
            p.append(f"{lugar}: por_dia precisa de fonte.coluna_data")
        _validar_filtro(m.get("filtro"), lugar, colunas, p)

    # ciclos entre métricas compostas
    def deps(n):
        m = mets.get(n) or {}
        return [m.get(k) for k in ("numerador", "denominador", "metrica") if m.get(k) in mets]

    for inicio in mets:
        pilha, visto = [(inicio, (inicio,))], set()
        while pilha:
            atual, caminho = pilha.pop()
            for d in deps(atual):
                if d == inicio:
                    p.append(f"metricas.{inicio}: referência circular ({' → '.join(caminho + (d,))})")
                    pilha = []
                    break
                if d not in visto:
                    visto.add(d)
                    pilha.append((d, caminho + (d,)))
    return sorted(set(p), key=p.index)


# ---------------------------------------------------------------- carregar

def ler_yaml(projeto: Path) -> dict:
    import yaml

    caminho = Path(projeto) / ARQUIVO_MODELO
    if not caminho.is_file():
        raise ErroDeModelo(f"não existe {ARQUIVO_MODELO}", ["use a ferramenta propor_modelo para gerar um rascunho"])
    try:
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        marca = getattr(e, "problem_mark", None)
        onde = f" (linha {marca.line + 1})" if marca else ""
        raise ErroDeModelo(f"{ARQUIVO_MODELO} não é um YAML válido{onde}", [str(e).splitlines()[0]]) from None
    if not isinstance(dados, dict):
        raise ErroDeModelo(f"{ARQUIVO_MODELO} deve ter as chaves versao, fonte, dimensoes e metricas")
    return dados


def carregar(projeto: Path) -> tuple[dict, Path, dict[str, str]]:
    """Modelo validado, arquivo da fonte e esquema. Levanta ErroDeModelo com a lista de problemas."""
    projeto = Path(projeto)
    modelo = ler_yaml(projeto)
    fonte = modelo.get("fonte") or {}
    if ("tabela" in fonte) == ("arquivo" in fonte):
        raise ErroDeModelo("modelo inválido", ["fonte: informe 'tabela' ou 'arquivo', um dos dois"])
    arquivo = arquivo_da_fonte(projeto, fonte)
    if not arquivo.is_file():
        raise ErroDeModelo(f"o arquivo da fonte não existe: {arquivo.relative_to(projeto)}")
    colunas = esquema(arquivo)
    problemas = validar(modelo, colunas)
    if problemas:
        raise ErroDeModelo(f"{ARQUIVO_MODELO} tem {len(problemas)} problema(s)", problemas)
    modelo.setdefault("dimensoes", {})
    return modelo, arquivo, colunas


# ---------------------------------------------------------------- definição legível e linhagem

def _texto_filtro(filtros) -> str:
    partes = []
    for f in filtros or []:
        if f["operador"] in ("em", "fora_de"):
            lista = ", ".join(str(v) for v in f["valores"])
            partes.append(f"{f['coluna']} {'em' if f['operador'] == 'em' else 'fora de'} ({lista})")
        elif f["operador"] in SEM_VALOR:
            partes.append(f"{f['coluna']} {'preenchido' if f['operador'] == 'preenchido' else 'vazio'}")
        else:
            simbolo = {"igual": "=", "diferente": "≠", "maior": ">", "menor": "<", "maior_igual": "≥",
                       "menor_igual": "≤"}[f["operador"]]
            partes.append(f"{f['coluna']} {simbolo} {f['valor']}")
    return (" onde " + " e ".join(partes)) if partes else ""


def definicao(nome: str, mets: dict, fonte: dict) -> str:
    """Frase em português que diz como a métrica é calculada (sem números)."""
    m = mets[nome]
    t = m["tipo"]
    filtro = _texto_filtro(m.get("filtro"))
    if t == "soma":
        return f"soma de {m['coluna']}{filtro}"
    if t == "media":
        return f"média de {m['coluna']}{filtro}"
    if t == "minimo":
        return f"menor valor de {m['coluna']}{filtro}"
    if t == "maximo":
        return f"maior valor de {m['coluna']}{filtro}"
    if t == "contagem":
        return (f"quantidade de valores preenchidos em {m['coluna']}" if m.get("coluna") else "quantidade de linhas") + filtro
    if t == "contagem_distinta":
        return f"quantidade de valores diferentes de {m['coluna']}{filtro}"
    if t == "razao":
        return f"{m['numerador']} dividido por {m['denominador']}"
    if t == "participacao":
        return f"{m['metrica']} de cada grupo dividido pelo total de {m['metrica']} de todos os grupos"
    return f"{m['metrica']} dividido pelos dias entre o primeiro e o último registro de {fonte['coluna_data']} do grupo"


def colunas_usadas(nome: str, mets: dict, fonte: dict) -> list[str]:
    m = mets[nome]
    usadas = set()
    if m.get("coluna"):
        usadas.add(m["coluna"])
    usadas |= {f["coluna"] for f in m.get("filtro") or []}
    for k in ("numerador", "denominador", "metrica"):
        if m.get(k):
            usadas |= set(colunas_usadas(m[k], mets, fonte))
    if m["tipo"] == "por_dia":
        usadas.add(fonte["coluna_data"])
    return sorted(usadas)


def registrar_linhagem(projeto: Path, modelo: dict, arquivo: Path) -> dict:
    """Grava no manifesto a definição e a origem de cada métrica e dimensão do modelo."""
    projeto = Path(projeto)
    manifesto = ler_manifesto(projeto)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fonte = modelo["fonte"]
    origem = {"arquivo": str(arquivo.relative_to(projeto)), "sha256": _sha256(arquivo)}
    sha_modelo = _sha256(projeto / ARQUIVO_MODELO)
    mets = modelo["metricas"]
    manifesto["metricas"] = {
        nome: {
            "descricao": m["descricao"],
            "tipo": m["tipo"],
            "formato": m["formato"],
            "definicao": definicao(nome, mets, fonte),
            "colunas": colunas_usadas(nome, mets, fonte),
            "depende_de": [m[k] for k in ("numerador", "denominador", "metrica") if m.get(k)],
            "fonte": origem,
            "modelo_sha256": sha_modelo,
            "registrado_em": agora,
        }
        for nome, m in mets.items()
    }
    manifesto["dimensoes"] = {
        nome: {"coluna": d["coluna"], "granularidade": d.get("granularidade"), "descricao": d.get("descricao", ""),
               "fonte": origem}
        for nome, d in modelo["dimensoes"].items()
    }
    manifesto["eventos"].append({"quando": agora, "evento": "modelo_validado", "modelo_sha256": sha_modelo,
                                 "metricas": len(mets), "fonte_sha256": origem["sha256"]})
    caminho = projeto / MANIFESTO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return manifesto["metricas"]


# ---------------------------------------------------------------- proposta de rascunho

# Em ordem de prioridade para escolher a métrica principal (a primeira encontrada vira a base
# do ticket médio, da participação e do valor por dia).
MOEDA = ("receita", "faturamento", "venda", "valor", "lucro", "investimento", "gasto", "despesa", "custo")
# Preço unitário, custo unitário e afins: somar não tem sentido; a métrica proposta é a média.
UNITARIOS = ("preco", "unitario", "ticket")
CONTAVEIS = ("quantidade", "qtd", "cliques", "impressoes", "conversoes", "pedidos", "visitas", "sessoes", "unidades")
TAXAS = ("pct", "percentual", "taxa", "desconto")


def _id(texto: str) -> str:
    base = re.sub(r"[^a-z]+", "_", texto.lower()).strip("_")
    return base[:40] or "campo"


def _fonte_padrao(projeto: Path, tabela: str | None) -> dict:
    if tabela:
        return {"tabela": tabela}
    if (projeto / "saidas" / "dados_tratados.parquet").is_file():
        return {"arquivo": "saidas/dados_tratados.parquet"}
    tabelas = list(ler_manifesto(projeto)["tabelas"])
    if len(tabelas) == 1:
        return {"tabela": tabelas[0]}
    raise ErroDeModelo("não sei de qual tabela propor o modelo",
                       [f"tabelas ingeridas: {', '.join(tabelas) or 'nenhuma'}; informe 'tabela'"])


def propor(projeto: Path, tabela: str | None = None, sobrescrever: bool = False) -> dict:
    """Escreve um rascunho de modelo/metricas.yaml a partir das colunas da fonte.

    É só um ponto de partida: o usuário confirma ou ajusta cada definição antes de
    validar. Descrições vêm do dicionário do contexto.md quando ele existe.
    """
    import duckdb
    import yaml

    projeto = Path(projeto)
    destino = projeto / ARQUIVO_MODELO
    if destino.exists() and not sobrescrever:
        raise ErroDeModelo(f"{ARQUIVO_MODELO} já existe", ["edite o arquivo ou peça para sobrescrever o rascunho"])
    fonte = _fonte_padrao(projeto, tabela)
    arquivo = arquivo_da_fonte(projeto, fonte)
    colunas = esquema(arquivo)

    significados = {}
    if (projeto / "contexto.md").is_file():
        from .contrato import ler_contexto

        significados = {c["coluna"]: c["significado"] for c in ler_contexto(projeto / "contexto.md")["dicionario"]}

    con = duckdb.connect()
    try:
        total = con.execute(f"SELECT count(*) FROM read_parquet({literal(arquivo)})").fetchone()[0]
        distintos = {c: con.execute(f"SELECT count(DISTINCT {q(c)}) FROM read_parquet({literal(arquivo)})").fetchone()[0]
                     for c in colunas}
    finally:
        con.close()

    datas = [c for c, t in colunas.items() if t.startswith(TIPOS_DATA_DUCKDB)]
    cdata = datas[0] if datas else None
    if cdata:
        fonte["coluna_data"] = cdata

    def desc(c, padrao):
        return significados.get(c) or padrao

    dims: dict[str, dict] = {}
    for c, t in colunas.items():
        if t == "VARCHAR" and 1 < distintos[c] <= 50:
            dims[_id(c)] = {"coluna": c, "descricao": desc(c, c.replace("_", " ").capitalize())}
    if cdata:
        dims["mes"] = {"coluna": cdata, "granularidade": "mes", "descricao": f"Mês de {cdata}"}
        dims["ano"] = {"coluna": cdata, "granularidade": "ano", "descricao": f"Ano de {cdata}"}

    mets: dict[str, dict] = {"registros": {"descricao": "Quantidade de linhas", "tipo": "contagem", "formato": "inteiro"}}
    chaves = [c for c, t in colunas.items() if t == "VARCHAR" and distintos[c] == total and total > 1]
    for c in chaves[:1]:
        base = _id(c.removesuffix("_id"))
        nome = base if base.endswith("s") else base + "s"
        mets[nome] = {"descricao": desc(c, f"Quantidade de {c} diferentes"), "tipo": "contagem_distinta",
                      "coluna": c, "formato": "inteiro"}
    moedas = []
    for c, t in colunas.items():
        if not t.startswith(TIPOS_NUMERICOS_DUCKDB) or c in chaves:
            continue
        nome_c = c.lower()
        if any(p in nome_c for p in TAXAS):
            mets[f"{_id(c)}_medio"] = {"descricao": desc(c, f"Média de {c}"), "tipo": "media", "coluna": c,
                                       "formato": "numero"}
        elif any(p in nome_c for p in UNITARIOS):
            mets[f"{_id(c)}_medio"] = {"descricao": desc(c, f"Média de {c}"), "tipo": "media", "coluna": c,
                                       "formato": "moeda"}
        elif any(p in nome_c for p in MOEDA) and not t.endswith("INT") and "INT" not in t:
            nome = f"{_id(c)}_total"
            mets[nome] = {"descricao": desc(c, f"Soma de {c}"), "tipo": "soma", "coluna": c, "formato": "moeda"}
            moedas.append(nome)
        elif any(p in nome_c for p in CONTAVEIS) or "INT" in t:
            mets[f"{_id(c)}_total"] = {"descricao": desc(c, f"Soma de {c}"), "tipo": "soma", "coluna": c,
                                       "formato": "inteiro"}
        else:
            mets[f"{_id(c)}_total"] = {"descricao": desc(c, f"Soma de {c}"), "tipo": "soma", "coluna": c,
                                       "formato": "decimal"}
    if moedas:
        principal = min(moedas, key=lambda n: next(
            (i for i, p in enumerate(MOEDA) if p in mets[n]["coluna"].lower()), len(MOEDA)))
        contador = next((n for n, m in mets.items() if m["tipo"] == "contagem_distinta"), None)
        if contador:
            mets["ticket_medio"] = {"descricao": f"{principal} dividido por {contador}", "tipo": "razao",
                                    "numerador": principal, "denominador": contador, "formato": "moeda"}
        mets[f"participacao_{principal}"[:48]] = {
            "descricao": f"Participação de cada grupo em {principal}", "tipo": "participacao", "metrica": principal,
            "formato": "percentual"}
        if cdata:
            mets[f"{principal}_por_dia"[:48]] = {
                "descricao": f"{principal} por dia com registro no período do grupo", "tipo": "por_dia",
                "metrica": principal, "formato": "moeda"}

    modelo = {"versao": VERSAO, "fonte": fonte, "dimensoes": dims, "metricas": mets}
    problemas = validar(modelo, colunas)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cabecalho = (f"# Rascunho proposto pelo bi-html em {datetime.now().strftime('%d/%m/%Y')}.\n"
                 "# Confira cada definição com o usuário antes de validar: o nome e a descrição\n"
                 "# de cada métrica aparecem no dashboard e no documento de decisão.\n")
    destino.write_text(cabecalho + yaml.safe_dump(modelo, allow_unicode=True, sort_keys=False, width=100),
                       encoding="utf-8")
    return {"arquivo": str(ARQUIVO_MODELO), "fonte": fonte, "dimensoes": list(dims), "metricas": list(mets),
            "problemas": problemas}
