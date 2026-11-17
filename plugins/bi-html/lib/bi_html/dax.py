"""
dax.py — tradução de medidas DAX para a camada de métricas do bi-html.

O bi-html não executa DAX. Uma medida do .pbix só vira métrica quando a expressão cabe nos
tipos do modelo (`modelo/metricas.yaml`): soma, média, mínimo, máximo, contagem, contagem
distinta, razão e participação, com filtros por coluna. Cada medida sai com uma de três
classes:

- `traduzida`: vira métrica (com as ressalvas de semântica, quando houver) e passa pelo teste
  de equivalência contra o motor DAX do pbix-mcp antes de valer como validada;
- `texto`: devolve rótulo, cor ou frase (FORMAT, CONCATENATEX, "&"); não é número, e o
  bi-html não converte;
- `nao_traduzida`: usa lógica sem equivalente na camada (SELECTEDVALUE, REMOVEFILTERS, TOPN,
  RANKX, IF, comparação com outra eleição ou período...), com o motivo.

Padrões traduzidos:

    SUM / AVERAGE / MIN / MAX / COUNT / COUNTA / DISTINCTCOUNT (T[c])  → soma, media, minimo...
    COUNTROWS(T) e COUNTROWS(FILTER(T, condição))                       → contagem
    SUMX / AVERAGEX / MINX / MAXX (T ou FILTER(T, cond), expressão)     → agregação de uma
        coluna calculada linha a linha (aritmética e DIVIDE sobre colunas de T e das tabelas
        ligadas a T); a coluna entra na tabela convertida, não no modelo
    CALCULATE(medida, T[c] = v, T[c] IN {...}, NOT ISBLANK(T[c]), KEEPFILTERS(...), FILTER(T, ...))
                                                                        → filtro da métrica
    DIVIDE(a, b) e a / b                                                → razao
    DIVIDE([m], CALCULATE([m], ALLSELECTED(...)))                       → participacao
    DIVIDE([m], constante), [m] * constante                             → a mesma métrica, com
        a escala registrada (o bi-html formata a grandeza; o teste confere o fator)
    VAR ... RETURN, quando o corpo cabe nos padrões acima

A árvore devolvida não tem ids: `conversao.py` dá nome às métricas e grava o modelo.
"""
from __future__ import annotations

import re

SUPORTADAS = {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA", "COUNTROWS", "DISTINCTCOUNT", "DISTINCTCOUNTNOBLANK",
              "SUMX", "AVERAGEX", "MINX", "MAXX", "COUNTX", "FILTER", "CALCULATE", "KEEPFILTERS", "DIVIDE", "RELATED",
              "TRUE", "FALSE", "BLANK", "ISBLANK", "NOT", "ALLSELECTED"}
DE_TEXTO = {"FORMAT", "CONCATENATEX", "UNICHAR", "CONCATENATE", "LEFT", "RIGHT", "MID", "UPPER", "LOWER", "SUBSTITUTE",
            "REPT", "COMBINEVALUES", "FIXED", "TRIM"}
AGREGACOES = {"SUM": "soma", "AVERAGE": "media", "MIN": "minimo", "MAX": "maximo", "DISTINCTCOUNT": "contagem_distinta",
              "DISTINCTCOUNTNOBLANK": "contagem_distinta", "COUNT": "contagem", "COUNTA": "contagem"}
ITERADORES = {"SUMX": "soma", "AVERAGEX": "media", "MINX": "minimo", "MAXX": "maximo", "COUNTX": "contagem"}
COMPARACOES = {"=": "igual", "==": "igual", "<>": "diferente", ">": "maior", "<": "menor", ">=": "maior_igual",
               "<=": "menor_igual"}
INVERSA = {"maior": "menor", "menor": "maior", "maior_igual": "menor_igual", "menor_igual": "maior_igual",
           "igual": "igual", "diferente": "diferente"}
RESSALVA_CALCULATE = ("o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro "
                      "na mesma coluna")


class ErroDeDax(Exception):
    """Expressão que o analisador não entende."""


class NaoTraduzivel(Exception):
    """Expressão válida que não cabe nos tipos do bi-html; a mensagem é o motivo."""


# ---------------------------------------------------------------- análise léxica e sintática

_TOKEN = re.compile(r"""
    (?P<espaco>\s+|--[^\n]*|//[^\n]*|/\*.*?\*/)
  | (?P<texto>"(?:[^"]|"")*")
  | (?P<tabela>'(?:[^']|'')*')
  | (?P<colchete>\[(?:[^\]]|\]\])*\])
  | (?P<numero>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+)
  | (?P<op><=|>=|<>|==|&&|\|\||[-+*/=<>&^(),{}])
  | (?P<nome>[^\W\d][\w.]*)
""", re.X | re.S)


def tokens(texto: str) -> list[tuple[str, str]]:
    saida, i = [], 0
    while i < len(texto):
        m = _TOKEN.match(texto, i)
        if not m:
            raise ErroDeDax(f"caractere inesperado: {texto[i]!r}")
        i = m.end()
        tipo = m.lastgroup
        if tipo != "espaco":
            saida.append((tipo, m.group(tipo)))
    return saida


class _Analisador:
    def __init__(self, texto: str):
        self.t = tokens(texto)
        self.i = 0

    def ver(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else (None, None)

    def palavra(self, k=0):
        tipo, v = self.ver(k)
        return v.upper() if tipo == "nome" else None

    def comer(self, valor=None):
        tipo, v = self.ver()
        if tipo is None or (valor is not None and (v.upper() if tipo == "nome" else v) != valor):
            raise ErroDeDax(f"esperado {valor!r}, encontrado {v!r}")
        self.i += 1
        return tipo, v

    def tudo(self):
        no = self.expr()
        if self.i != len(self.t):
            raise ErroDeDax(f"sobrou {self.ver()[1]!r} no fim da expressão")
        return no

    def expr(self):
        if self.palavra() == "VAR":
            variaveis = []
            while self.palavra() == "VAR":
                self.comer("VAR")
                _, nome = self.comer()
                self.comer("=")
                variaveis.append((nome, self.expr()))
            self.comer("RETURN")
            return ("var", variaveis, self.expr())
        return self.ou()

    def ou(self):
        a = self.e()
        while self.ver()[1] == "||":
            self.comer()
            a = ("bin", "||", a, self.e())
        return a

    def e(self):
        a = self.nao()
        while self.ver()[1] == "&&":
            self.comer()
            a = ("bin", "&&", a, self.nao())
        return a

    def nao(self):
        if self.palavra() == "NOT" and self.ver(1)[1] != "(":
            self.comer()
            return ("un", "NOT", self.nao())
        return self.comparacao()

    def comparacao(self):
        a = self.concat()
        tipo, v = self.ver()
        if v in COMPARACOES:
            self.comer()
            return ("bin", v, a, self.concat())
        if self.palavra() == "IN":
            self.comer()
            return ("bin", "IN", a, self.concat())
        if self.palavra() == "NOT" and self.palavra(1) == "IN":
            self.comer(), self.comer()
            return ("un", "NOT", ("bin", "IN", a, self.concat()))
        return a

    def concat(self):
        a = self.soma()
        while self.ver()[1] == "&":
            self.comer()
            a = ("bin", "&", a, self.soma())
        return a

    def soma(self):
        a = self.produto()
        while self.ver()[1] in ("+", "-"):
            _, op = self.comer()
            a = ("bin", op, a, self.produto())
        return a

    def produto(self):
        a = self.unario()
        while self.ver()[1] in ("*", "/"):
            _, op = self.comer()
            a = ("bin", op, a, self.unario())
        return a

    def unario(self):
        if self.ver()[1] in ("-", "+"):
            _, op = self.comer()
            x = self.unario()
            return ("un", "-", x) if op == "-" else x
        a = self.primario()
        if self.ver()[1] == "^":
            self.comer()
            a = ("bin", "^", a, self.unario())
        return a

    def primario(self):
        tipo, v = self.ver()
        if tipo == "numero":
            self.comer()
            return ("num", float(v) if any(c in v for c in ".eE") else int(v))
        if tipo == "texto":
            self.comer()
            return ("str", v[1:-1].replace('""', '"'))
        if tipo == "colchete":
            self.comer()
            return ("ref", v[1:-1].replace("]]", "]"))
        if v == "(":
            self.comer()
            no = self.expr()
            self.comer(")")
            return no
        if v == "{":
            self.comer()
            itens = []
            if self.ver()[1] != "}":
                itens.append(self.expr())
                while self.ver()[1] == ",":
                    self.comer()
                    itens.append(self.expr())
            self.comer("}")
            return ("lista", itens)
        if tipo == "tabela":
            self.comer()
            nome = v[1:-1].replace("''", "'")
            if self.ver()[0] == "colchete":
                _, c = self.comer()
                return ("col", nome, c[1:-1].replace("]]", "]"))
            return ("tab", nome)
        if tipo == "nome":
            self.comer()
            if self.ver()[1] == "(":
                self.comer()
                args = []
                if self.ver()[1] != ")":
                    args.append(self.expr())
                    while self.ver()[1] == ",":
                        self.comer()
                        args.append(self.expr() if self.ver()[1] not in (",", ")") else ("vazio",))
                self.comer(")")
                return ("call", v.upper(), args)
            if self.ver()[0] == "colchete":
                _, c = self.comer()
                return ("col", v, c[1:-1].replace("]]", "]"))
            return ("nome", v)
        raise ErroDeDax(f"inesperado: {v!r}")


def analisar(texto: str):
    return _Analisador(texto or "").tudo()


def funcoes(no) -> set[str]:
    """Nomes de função usados na expressão (para o motivo de não tradução)."""
    achadas = set()
    if isinstance(no, tuple):
        if len(no) >= 2 and no[0] == "call":
            achadas.add(no[1])
        for filho in no[1:]:
            achadas |= funcoes(filho)
    elif isinstance(no, list):
        for x in no:
            achadas |= funcoes(x)
    return achadas


# ---------------------------------------------------------------- tradução

def _literal(no, env):
    no = _resolver(no, env)
    if no[0] == "num":
        return no[1]
    if no[0] == "str":
        return no[1]
    if no[0] == "un" and no[1] == "-" and no[2][0] == "num":
        return -no[2][1]
    if no[0] == "call" and no[1] in ("TRUE", "FALSE") and not no[2]:
        return no[1] == "TRUE"
    raise NaoTraduzivel("filtro com valor que não é constante")


def _resolver(no, env):
    while no[0] == "nome" and no[1] in env:
        no = env[no[1]]
    return no


def _eh_branco(no) -> bool:
    return no[0] == "call" and no[1] == "BLANK" and not no[2]


def mesma(a, b) -> bool:
    """Duas árvores traduzidas que calculam a mesma coisa (ignorando de qual medida vieram)."""
    limpa = lambda n: {k: (limpa(v) if isinstance(v, dict) else v) for k, v in n.items() if k != "ref"}  # noqa: E731
    return limpa(a) == limpa(b)


class Tradutor:
    """Traduz as medidas de um modelo.

    `medidas`: nome → expressão DAX; `colunas`: tabela → {coluna: tipo pandas};
    `alcance(tabela)`: tabelas cujas colunas filtram a tabela (ela mesma e as do lado "um"
    das relações, seguidas em cadeia).
    """

    def __init__(self, medidas: dict[str, str], colunas: dict[str, dict], alcance):
        self.medidas, self.colunas, self.alcance = medidas, colunas, alcance
        self.memo: dict[str, dict] = {}
        self._pilha: list[str] = []
        self._ressalvas: set[str] = set()

    # -- resultado por medida

    def traduzir(self, nome: str) -> dict:
        if nome in self.memo:
            return self.memo[nome]
        if nome in self._pilha:
            raise NaoTraduzivel(f"referência circular em [{nome}]")
        self._pilha.append(nome)
        ressalvas_antes, self._ressalvas = self._ressalvas, set()
        try:
            arvore = analisar(self.medidas[nome])
        except ErroDeDax as e:
            r = {"classe": "nao_traduzida", "motivo": f"o analisador não entendeu a expressão ({e})"}
        else:
            try:
                no = self._no(arvore, {})
                r = {"classe": "traduzida", "no": no, "ressalvas": sorted(self._ressalvas)}
            except NaoTraduzivel as e:
                if self._texto(arvore, {}, set()):
                    r = {"classe": "texto", "motivo": "devolve texto (rótulo, cor ou frase), não número"}
                else:
                    fora = sorted(f for f in funcoes(arvore) - SUPORTADAS)
                    motivo = str(e)
                    if fora and not motivo.startswith("depende de"):
                        motivo = f"usa {', '.join(fora)}, sem equivalente na camada de métricas"
                    r = {"classe": "nao_traduzida", "motivo": motivo}
        finally:
            self._pilha.pop()
            self._ressalvas = ressalvas_antes | self._ressalvas
        self.memo[nome] = r
        return r

    # -- nós

    def _no(self, no, env):
        no = _resolver(no, env)
        tipo = no[0]
        if tipo == "var":
            env = dict(env)
            for nome, valor in no[1]:
                env[nome] = valor
            return self._no(no[2], env)
        if tipo == "ref":
            if no[1] not in self.medidas:
                raise NaoTraduzivel(f"[{no[1]}] não é medida do modelo")
            dep = self.traduzir(no[1])
            if dep["classe"] != "traduzida":
                raise NaoTraduzivel(f"depende de [{no[1]}], que não foi traduzida")
            self._ressalvas |= set(dep.get("ressalvas") or [])
            return {**dep["no"], "ref": no[1]}
        if tipo == "call":
            return self._chamada(no[1], no[2], env)
        if tipo == "bin" and no[1] == "/":
            return self._divisao(no[2], no[3], env)
        if tipo == "bin" and no[1] == "*":
            for a, b in ((no[2], no[3]), (no[3], no[2])):
                if _resolver(b, env)[0] == "num":
                    return self._escala(self._no(a, env), float(_resolver(b, env)[1]))
            raise NaoTraduzivel("produto de duas medidas não tem tipo no bi-html")
        if tipo == "bin" and no[1] in ("+", "-"):
            # Soma ou diferença de somas do mesmo fato, com os mesmos filtros, é a soma de uma coluna
            # calculada linha a linha (vazio conta como zero, como no DAX).
            a, b = self._no(no[2], env), self._no(no[3], env)
            if all(x["no"] == "base" and x["tipo"] == "soma" for x in (a, b)) and a["fato"] == b["fato"] \
                    and a["filtro"] == b["filtro"]:
                sql = lambda x: x["calc"] or '"' + x["coluna"].replace('"', '""') + '"'  # noqa: E731
                calc = f"(COALESCE({sql(a)}, 0) {no[1]} COALESCE({sql(b)}, 0))"
                return {"no": "base", "tipo": "soma", "coluna": None, "fato": a["fato"], "filtro": a["filtro"],
                        "calc": calc}
            raise NaoTraduzivel("soma ou diferença de medidas só se traduz entre somas do mesmo fato")
        raise NaoTraduzivel("expressão fora dos padrões traduzíveis")

    def _chamada(self, f, args, env):
        if f in AGREGACOES:
            col = _resolver(args[0], env) if args else None
            if not col or col[0] != "col":
                raise NaoTraduzivel(f"{f} sem coluna de tabela")
            self._checar_coluna(col[1], col[1], col[2])
            if f == "DISTINCTCOUNT":
                self._ressalvas.add("DISTINCTCOUNT conta o vazio como um valor; a contagem distinta do bi-html, não")
            return {"no": "base", "tipo": AGREGACOES[f], "coluna": f"{col[1]}.{col[2]}", "fato": col[1],
                    "filtro": [], "calc": None}
        if f == "COUNTROWS":
            tabela, filtros = self._tabela(args[0] if args else None, env)
            return {"no": "base", "tipo": "contagem", "coluna": None, "fato": tabela, "filtro": filtros, "calc": None}
        if f in ITERADORES:
            if len(args) != 2:
                raise NaoTraduzivel(f"{f} com argumentos inesperados")
            tabela, filtros = self._tabela(args[0], env)
            linha = _resolver(args[1], env)
            if linha[0] == "col" and linha[1] in self.alcance(tabela):
                self._checar_coluna(tabela, linha[1], linha[2])
                return {"no": "base", "tipo": ITERADORES[f], "coluna": f"{linha[1]}.{linha[2]}", "fato": tabela,
                        "filtro": filtros, "calc": None}
            return {"no": "base", "tipo": ITERADORES[f], "coluna": None, "fato": tabela, "filtro": filtros,
                    "calc": self._sql_linha(linha, tabela, env)}
        if f == "CALCULATE":
            if not args:
                raise NaoTraduzivel("CALCULATE vazio")
            base = self._no(args[0], env)
            filtros = []
            for a in args[1:]:
                filtros += self._condicao(a, None, env, de_calculate=True)
            return self._aplicar(base, filtros)
        if f == "DIVIDE":
            if len(args) == 3 and not _eh_branco(_resolver(args[2], env)):
                raise NaoTraduzivel("DIVIDE com resultado alternativo diferente de vazio")
            return self._divisao(args[0], args[1], env)
        raise NaoTraduzivel(f"usa {f}")

    def _divisao(self, a, b, env):
        b_ = _resolver(b, env)
        if b_[0] == "num":
            return self._escala(self._no(a, env), 1 / float(b_[1]))
        # DIVIDE([m], CALCULATE([m], ALLSELECTED(...))) → participação
        if b_[0] == "call" and b_[1] == "CALCULATE" and len(b_[2]) >= 2 and all(
                _resolver(x, env)[0] == "call" and _resolver(x, env)[1] == "ALLSELECTED" for x in b_[2][1:]):
            num, tot = self._no(a, env), self._no(b_[2][0], env)
            if mesma(num, tot) and num["no"] == "base" and num["tipo"] in ("soma", "contagem"):
                eixo = []
                for x in b_[2][1:]:
                    for arg in _resolver(x, env)[2]:
                        arg = _resolver(arg, env)
                        if arg[0] == "col":
                            eixo.append(f"{arg[1]}.{arg[2]}")
                self._ressalvas.add("participação: equivale quando o bloco agrupa pela coluna do ALLSELECTED"
                                    if eixo else "participação: o total é o de todas as linhas do bloco")
                return {"no": "participacao", "base": num, "eixo": eixo}
            raise NaoTraduzivel("ALLSELECTED fora do padrão de participação")
        num, den = self._no(a, env), self._no(b, env)
        fator = 1.0
        if num["no"] == "escala":
            fator, num = fator * num["fator"], num["base"]
        if den["no"] == "escala":
            fator, den = fator / den["fator"], den["base"]
        if "participacao" in (num["no"], den["no"]):
            raise NaoTraduzivel("razão com participação não tem tipo no bi-html")
        r = {"no": "razao", "num": num, "den": den}
        return r if fator == 1.0 else {"no": "escala", "base": r, "fator": fator}

    def _escala(self, base, fator):
        if base["no"] == "escala":
            return {"no": "escala", "base": base["base"], "fator": base["fator"] * fator}
        if base["no"] == "participacao":
            raise NaoTraduzivel("participação com escala")
        return {"no": "escala", "base": base, "fator": fator}

    def _aplicar(self, no, filtros):
        if not filtros:
            return no
        no = {k: v for k, v in no.items() if k != "ref"}
        if no["no"] == "base":
            for f in filtros:
                if f["_tabela"] not in self.alcance(no["fato"]):
                    raise NaoTraduzivel(f"filtro em {f['_tabela']}, que não filtra {no['fato']}")
            return {**no, "filtro": no["filtro"] + [{k: v for k, v in f.items() if k != "_tabela"} for f in filtros]}
        if no["no"] == "razao":
            return {**no, "num": self._aplicar(no["num"], filtros), "den": self._aplicar(no["den"], filtros)}
        if no["no"] == "escala":
            return {**no, "base": self._aplicar(no["base"], filtros)}
        raise NaoTraduzivel("CALCULATE sobre participação")

    # -- tabelas, colunas e condições

    def _checar_coluna(self, fato, tabela, coluna):
        if tabela not in self.colunas or coluna not in self.colunas[tabela]:
            raise NaoTraduzivel(f"coluna {tabela}[{coluna}] não existe nos dados extraídos")
        if tabela not in self.alcance(fato):
            raise NaoTraduzivel(f"{tabela} não se liga a {fato} por relação")

    def _tabela(self, no, env):
        no = _resolver(no, env) if no else None
        if no and no[0] in ("tab", "nome"):
            if no[1] not in self.colunas:
                raise NaoTraduzivel(f"tabela {no[1]} não existe nos dados extraídos")
            return no[1], []
        if no and no[0] == "call" and no[1] == "FILTER" and len(no[2]) == 2:
            tabela, filtros = self._tabela(no[2][0], env)
            conds = self._condicao(no[2][1], tabela, env)
            for c in conds:
                if c["_tabela"] not in self.alcance(tabela):
                    raise NaoTraduzivel(f"filtro em {c['_tabela']}, que não filtra {tabela}")
            return tabela, filtros + [{k: v for k, v in c.items() if k != "_tabela"} for c in conds]
        raise NaoTraduzivel("iterador sobre expressão de tabela que não é tabela nem FILTER(tabela, ...)")

    def _condicao(self, no, tabela, env, de_calculate=False) -> list[dict]:
        no = _resolver(no, env)
        if no[0] == "call" and no[1] in ("ALL", "ALLSELECTED", "ALLEXCEPT", "REMOVEFILTERS", "ALLNOBLANKROW"):
            raise NaoTraduzivel(f"CALCULATE com {no[1]} (remove filtros do leitor) fora do padrão de participação")
        if no[0] == "call" and no[1] == "KEEPFILTERS" and len(no[2]) == 1:
            return self._condicao(no[2][0], tabela, env)
        if no[0] == "call" and no[1] == "FILTER" and len(no[2]) == 2:
            t, _ = self._tabela(no[2][0], env)
            return self._condicao(no[2][1], t, env)
        if no[0] == "bin" and no[1] == "&&":
            return self._condicao(no[2], tabela, env, de_calculate) + self._condicao(no[3], tabela, env, de_calculate)
        if de_calculate:
            self._ressalvas.add(RESSALVA_CALCULATE)
        if no[0] == "un" and no[1] == "NOT":
            dentro = _resolver(no[2], env)
            if dentro[0] == "call" and dentro[1] == "ISBLANK" and len(dentro[2]) == 1:
                return [self._filtro(dentro[2][0], "preenchido", None, env)]
            if dentro[0] == "bin" and dentro[1] == "IN":
                return [self._filtro(dentro[2], "fora_de", [_literal(x, env) for x in self._lista(dentro[3], env)], env)]
        if no[0] == "call" and no[1] == "NOT" and len(no[2]) == 1:
            return self._condicao(("un", "NOT", no[2][0]), tabela, env)
        if no[0] == "call" and no[1] == "ISBLANK" and len(no[2]) == 1:
            return [self._filtro(no[2][0], "vazio", None, env)]
        if no[0] == "bin" and no[1] == "IN":
            return [self._filtro(no[2], "em", [_literal(x, env) for x in self._lista(no[3], env)], env)]
        if no[0] == "bin" and no[1] in COMPARACOES:
            esq, dir_ = _resolver(no[2], env), _resolver(no[3], env)
            op = COMPARACOES[no[1]]
            if esq[0] != "col" and dir_[0] == "col":
                esq, dir_, op = dir_, esq, INVERSA[op]
            if _eh_branco(dir_) and op in ("igual", "diferente"):
                return [self._filtro(esq, "vazio" if op == "igual" else "preenchido", None, env)]
            return [self._filtro(esq, op, _literal(dir_, env), env)]
        raise NaoTraduzivel("condição de filtro fora dos padrões (coluna comparada a constante)")

    def _lista(self, no, env):
        no = _resolver(no, env)
        if no[0] != "lista":
            raise NaoTraduzivel("IN sem lista de constantes")
        return no[1]

    def _filtro(self, col, operador, valor, env):
        col = _resolver(col, env)
        if col[0] != "col":
            raise NaoTraduzivel("filtro que não é sobre uma coluna")
        if col[1] not in self.colunas or col[2] not in self.colunas[col[1]]:
            raise NaoTraduzivel(f"coluna {col[1]}[{col[2]}] não existe nos dados extraídos")
        f = {"coluna": f"{col[1]}.{col[2]}", "operador": operador, "_tabela": col[1]}
        if operador in ("em", "fora_de"):
            f["valores"] = valor
        elif operador not in ("preenchido", "vazio"):
            f["valor"] = valor
        return f

    def _sql_linha(self, no, tabela, env) -> str:
        """Expressão linha a linha de um iterador, em SQL sobre as colunas da tabela convertida."""
        no = _resolver(no, env)
        if no[0] == "num":
            return repr(no[1])
        if no[0] == "col" or (no[0] == "call" and no[1] == "RELATED" and len(no[2]) == 1):
            col = no if no[0] == "col" else _resolver(no[2][0], env)
            if col[0] != "col":
                raise NaoTraduzivel("RELATED sem coluna")
            self._checar_coluna(tabela, col[1], col[2])
            return '"' + f"{col[1]}.{col[2]}".replace('"', '""') + '"'
        if no[0] == "un" and no[1] == "-":
            return f"(-{self._sql_linha(no[2], tabela, env)})"
        if no[0] == "bin" and no[1] in ("+", "-", "*"):
            return f"({self._sql_linha(no[2], tabela, env)} {no[1]} {self._sql_linha(no[3], tabela, env)})"
        if (no[0] == "bin" and no[1] == "/") or (no[0] == "call" and no[1] == "DIVIDE" and len(no[2]) == 2):
            a, b = (no[2], no[3]) if no[0] == "bin" else no[2]
            return (f"(CAST({self._sql_linha(a, tabela, env)} AS DOUBLE) / "
                    f"NULLIF(CAST({self._sql_linha(b, tabela, env)} AS DOUBLE), 0))")
        raise NaoTraduzivel("expressão linha a linha fora da aritmética sobre colunas")

    # -- medidas de texto

    def _texto(self, no, env, vistos) -> bool:
        no = _resolver(no, env)
        if no[0] == "str" or (no[0] == "bin" and no[1] == "&"):
            return True
        if no[0] == "var":
            env = dict(env)
            for nome, valor in no[1]:
                env[nome] = valor
            return self._texto(no[2], env, vistos)
        if no[0] == "ref" and no[1] in self.medidas and no[1] not in vistos:
            try:
                return self._texto(analisar(self.medidas[no[1]]), {}, vistos | {no[1]})
            except ErroDeDax:
                return False
        if no[0] == "call":
            if no[1] in DE_TEXTO:
                return True
            if no[1] == "IF":
                return any(self._texto(a, env, vistos) for a in no[2][1:])
            if no[1] == "SWITCH":
                return any(self._texto(a, env, vistos) for a in no[2][2::2] + no[2][-1:])
            if no[1] == "COALESCE":
                return any(self._texto(a, env, vistos) for a in no[2])
            if no[1] == "LOOKUPVALUE" and no[2] and _resolver(no[2][0], env)[0] == "col":
                t, c = _resolver(no[2][0], env)[1:]
                return str((self.colunas.get(t) or {}).get(c, "")).lower() in ("string", "object")
            if no[1] == "SELECTEDVALUE" and no[2] and _resolver(no[2][0], env)[0] == "col":
                t, c = _resolver(no[2][0], env)[1:]
                return str((self.colunas.get(t) or {}).get(c, "")).lower() in ("string", "object")
        return False
