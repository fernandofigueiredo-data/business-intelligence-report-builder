"""
Ingestão: lê CSV, Excel ou texto colado e grava uma tabela tipada em Parquet.

Usada no atalho sem análise prévia (e, depois, no Fluxo 2). Segue a estrutura
de pasta do plugin analise-dados:

- o original fica em `dados/` e nunca é sobrescrito (arquivo de fora é copiado);
- a tabela tipada vai para `saidas/bi/tabelas/<nome>.parquet`;
- o manifesto `saidas/bi/manifesto.json` registra origem, hash, data e como o
  arquivo foi lido (codificação, separador, decimal, aba).

A leitura é estrita: uma coluna só vira número ou data se **todos** os valores
preenchidos tiverem esse formato. Linhas com número de colunas diferente do
cabeçalho, cabeçalho vazio ou repetido e arquivo ilegível viram um erro em
português, com as linhas afetadas, em vez de dados silenciosamente errados.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path

PASTA_BI = Path("saidas") / "bi"
MANIFESTO = PASTA_BI / "manifesto.json"
TABELAS = PASTA_BI / "tabelas"
EXTENSOES = {".csv", ".txt", ".tsv", ".xlsx", ".xlsm"}
VAZIOS = {"", "na", "n/a", "nan", "null", "none", "-"}


class ErroDeLeitura(Exception):
    """Arquivo que não pode virar tabela; a mensagem já é a que o usuário lê."""

    def __init__(self, mensagem: str, detalhes: list[str] | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.detalhes = detalhes or []


# ---------------------------------------------------------------- nomes

def nome_de_tabela(texto: str) -> str:
    """'Vendas 2025 (final).csv' → 'vendas_final': minúsculas, sem acento e sem algarismos,
    no mesmo formato dos ids da spec."""
    base = unicodedata.normalize("NFKD", Path(texto).stem).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z]+", "_", base.lower()).strip("_")
    return base or "tabela"


def _nome_de_coluna(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


# ---------------------------------------------------------------- texto e CSV

def _decodificar(bruto: bytes) -> tuple[str, str]:
    if bruto.startswith(b"\xef\xbb\xbf"):
        return bruto[3:].decode("utf-8"), "utf-8-sig"
    try:
        return bruto.decode("utf-8"), "utf-8"
    except UnicodeDecodeError as e:
        utf8_valido = re.search(rb"[\xc2-\xf4][\x80-\xbf]", bruto[: e.start]) is not None
        if utf8_valido:
            linha = bruto[: e.start].count(b"\n") + 1
            raise ErroDeLeitura(
                f"o arquivo mistura codificações: está em UTF-8, mas a linha {linha} não está",
                ["salve o arquivo de novo como CSV UTF-8 no Excel ou no editor"]) from None
        return bruto.decode("cp1252", errors="strict"), "cp1252"


def _separador(texto: str) -> str:
    amostra = "\n".join(texto.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(amostra, delimiters=";,\t|").delimiter
    except csv.Error:
        cabecalho = texto.splitlines()[0] if texto else ""
        contagem = {s: cabecalho.count(s) for s in ";,\t|"}
        melhor = max(contagem, key=contagem.get)
        if contagem[melhor] == 0:
            raise ErroDeLeitura("não encontrei separador de colunas na primeira linha",
                                ["use ponto e vírgula, vírgula ou tabulação entre as colunas"]) from None
        return melhor


def _linhas_csv(texto: str, sep: str) -> tuple[list[str], list[list[str]]]:
    linhas = [l for l in csv.reader(io.StringIO(texto), delimiter=sep) if any(c.strip() for c in l)]
    if not linhas:
        raise ErroDeLeitura("o arquivo está vazio")
    cabecalho, corpo = linhas[0], linhas[1:]
    erradas = [(i + 2, len(l)) for i, l in enumerate(corpo) if len(l) != len(cabecalho)]
    if erradas:
        detalhes = [f"linha {n}: {q} colunas, o cabeçalho tem {len(cabecalho)}" for n, q in erradas[:5]]
        if len(erradas) > 5:
            detalhes.append(f"e mais {len(erradas) - 5} linhas")
        raise ErroDeLeitura(f"{len(erradas)} linha(s) com número de colunas diferente do cabeçalho", detalhes)
    return cabecalho, corpo


# ---------------------------------------------------------------- tipos

RE_INT = re.compile(r"^-?\d+$")
RE_ZERO_ESQUERDA = re.compile(r"^-?0\d")
RE_DEC_PONTO = re.compile(r"^-?\d+\.\d+$")
RE_DEC_BR = re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+),\d+$")
RE_MIL_BR = re.compile(r"^-?\d{1,3}(\.\d{3})+$")
RE_DATA_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
RE_DATAHORA_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})[ T](\d{2}):(\d{2})(?::(\d{2}))?$")
RE_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
RE_DATAHORA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?")
RE_MES = re.compile(r"^(\d{4})-(\d{2})$")
BOOL = {"sim": True, "não": False, "nao": False, "true": True, "false": False, "s": True, "n": False}


def _vazio(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in VAZIOS)


def _testar(valores: list[str], regex) -> bool:
    return all(regex.match(v) for v in valores)


def inferir_coluna(valores: list[str], decimal_virgula: bool) -> tuple[str, list, dict]:
    """Tipo, valores convertidos e observações de uma coluna lida como texto.

    Tipos: inteiro, decimal, data, data_hora, mes, booleano, texto.
    """
    cheios = [v.strip() for v in valores if not _vazio(v)]
    obs: dict = {}

    def converter(fn):
        return [None if _vazio(v) else fn(v.strip()) for v in valores]

    if not cheios:
        return "texto", [None] * len(valores), {"so_vazios": True}
    # Código com zero à esquerda (CEP, matrícula, conta) não é número: convertê-lo perde o zero.
    codigo = any(RE_ZERO_ESQUERDA.match(v) for v in cheios)
    if not codigo and _testar(cheios, RE_INT):
        return "inteiro", converter(int), obs
    if _testar(cheios, RE_DATA_BR):
        try:
            dias = converter(lambda v: date(int(v[6:10]), int(v[3:5]), int(v[0:2])))
        except ValueError:
            pass
        else:
            if all(int(v[0:2]) <= 12 for v in cheios):
                obs["formato_ambiguo"] = "todos os dias são até 12; li como dd/mm/aaaa"
            return "data", dias, obs
    if _testar(cheios, RE_DATAHORA_BR):
        def dh(v):
            m = RE_DATAHORA_BR.match(v)
            d, mo, a, h, mi, s = m.groups()
            return datetime(int(a), int(mo), int(d), int(h), int(mi), int(s or 0))
        try:
            return "data_hora", converter(dh), obs
        except ValueError:
            pass
    if _testar(cheios, RE_DATA_ISO):
        try:
            return "data", converter(date.fromisoformat), obs
        except ValueError:
            pass
    if _testar(cheios, RE_DATAHORA_ISO):
        try:
            return "data_hora", converter(lambda v: datetime.fromisoformat(v.replace("Z", "+00:00"))), obs
        except ValueError:
            pass
    if _testar(cheios, RE_MES):
        try:
            meses = converter(lambda v: date(int(v[:4]), int(v[5:7]), 1))
        except ValueError:
            pass
        else:
            obs["granularidade"] = "mes"
            return "mes", meses, obs
    if codigo:
        return "texto", [None if _vazio(v) else v.strip() for v in valores], {"codigo_com_zero_a_esquerda": True}
    if decimal_virgula and all(RE_DEC_BR.match(v) or RE_INT.match(v) or RE_MIL_BR.match(v) for v in cheios):
        return "decimal", converter(lambda v: float(v.replace(".", "").replace(",", "."))), obs
    if not decimal_virgula and all(RE_DEC_PONTO.match(v) or RE_INT.match(v) for v in cheios):
        return "decimal", converter(float), obs
    if all(v.lower() in BOOL for v in cheios) and len({v.lower() for v in cheios}) <= 2:
        return "booleano", converter(lambda v: BOOL[v.lower()]), obs
    numericos = sum(bool(RE_INT.match(v) or RE_DEC_BR.match(v) or RE_DEC_PONTO.match(v)) for v in cheios)
    if numericos >= 0.9 * len(cheios):
        estranhos = sorted({v for v in cheios if not (RE_INT.match(v) or RE_DEC_BR.match(v) or RE_DEC_PONTO.match(v))})
        obs["quase_numerica"] = {"valores_nao_numericos": len(cheios) - numericos, "exemplos": estranhos[:3]}
    return "texto", [None if _vazio(v) else v.strip() for v in valores], obs


def _decimal_virgula(cabecalho, corpo, sep) -> bool:
    """O arquivo usa vírgula decimal? Decide pelo que aparece nas células."""
    br = ponto = 0
    for linha in corpo[:2000]:
        for v in linha:
            v = v.strip()
            br += bool(RE_DEC_BR.match(v))
            ponto += bool(RE_DEC_PONTO.match(v))
    if br or ponto:
        return br > ponto
    return sep == ";"


# ---------------------------------------------------------------- Excel

def _ler_excel(caminho: Path, aba: str | None) -> tuple[list[str], list[list], dict]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(caminho, read_only=True, data_only=True)
    except Exception as e:  # zip corrompido, formato antigo .xls renomeado etc.
        raise ErroDeLeitura(f"não consegui abrir a planilha ({e.__class__.__name__})",
                            ["confira se o arquivo abre no Excel e salve de novo como .xlsx"]) from None
    abas = wb.sheetnames
    escolhida = aba or abas[0]
    if escolhida not in abas:
        raise ErroDeLeitura(f"a aba {escolhida!r} não existe", [f"abas disponíveis: {', '.join(abas)}"])
    linhas = [list(l) for l in wb[escolhida].iter_rows(values_only=True)]
    wb.close()
    linhas = [l for l in linhas if any(c is not None and str(c).strip() for c in l)]
    if not linhas:
        raise ErroDeLeitura(f"a aba {escolhida!r} está vazia")
    cabecalho = ["" if c is None else str(c) for c in linhas[0]]
    while cabecalho and not cabecalho[-1].strip():
        cabecalho.pop()
    corpo = [l[: len(cabecalho)] + [None] * (len(cabecalho) - len(l)) for l in linhas[1:]]
    return cabecalho, corpo, {"formato": "xlsx", "aba": escolhida, "outras_abas": [a for a in abas if a != escolhida]}


def _coluna_excel(valores: list) -> tuple[str, list, dict]:
    """Excel já traz tipos: datas, números e texto. Coluna mista vira texto."""
    cheios = [v for v in valores if not _vazio(v)]
    if cheios and all(isinstance(v, datetime) for v in cheios):
        if all(v.hour == v.minute == v.second == 0 for v in cheios):
            return "data", [v.date() if isinstance(v, datetime) else None for v in valores], {}
        return "data_hora", [v if isinstance(v, datetime) else None for v in valores], {}
    if cheios and all(isinstance(v, bool) for v in cheios):
        return "booleano", [v if isinstance(v, bool) else None for v in valores], {}
    if cheios and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in cheios):
        if all(float(v).is_integer() for v in cheios):
            return "inteiro", [None if _vazio(v) else int(v) for v in valores], {}
        return "decimal", [None if _vazio(v) else float(v) for v in valores], {}
    textos = ["" if v is None else (v.strftime("%d/%m/%Y") if isinstance(v, (date, datetime)) else str(v))
              for v in valores]
    return inferir_coluna(textos, decimal_virgula=True)


# ---------------------------------------------------------------- gravação

TIPO_DUCKDB = {"inteiro": "BIGINT", "decimal": "DOUBLE", "data": "DATE", "data_hora": "TIMESTAMP",
               "mes": "DATE", "booleano": "BOOLEAN", "texto": "VARCHAR"}


def _gravar_parquet(colunas: list[dict], destino: Path) -> None:
    import duckdb

    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        intermediario = Path(tmp) / "t.csv"
        with open(intermediario, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([c["nome"] for c in colunas])
            for linha in zip(*(c["valores"] for c in colunas)):
                w.writerow(["" if v is None else (v.isoformat() if isinstance(v, (date, datetime)) else v)
                            for v in linha])
        tipos = {c["nome"]: TIPO_DUCKDB[c["tipo"]] for c in colunas}
        con = duckdb.connect()
        try:
            con.execute(
                f"COPY (SELECT * FROM read_csv(?, header=true, columns={tipos!r}, nullstr='', quote='\"')) "
                f"TO '{destino.as_posix()}' (FORMAT parquet)", [str(intermediario)])
        finally:
            con.close()


def _hash(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_manifesto(projeto: Path) -> dict:
    p = projeto / MANIFESTO
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {"versao": 1, "tabelas": {}, "eventos": []}


def _gravar_manifesto(projeto: Path, manifesto: dict) -> None:
    p = projeto / MANIFESTO
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _original_em_dados(projeto: Path, origem: Path) -> Path:
    """Garante o original em dados/: arquivo de fora é copiado; nada em dados/ é sobrescrito."""
    pasta = projeto / "dados"
    try:
        origem.resolve().relative_to(pasta.resolve())
        return origem
    except ValueError:
        pass
    pasta.mkdir(exist_ok=True)
    destino = pasta / origem.name
    if destino.exists():
        if _hash(destino) == _hash(origem):
            return destino
        raise ErroDeLeitura(f"já existe outro arquivo chamado {origem.name} em dados/",
                            ["renomeie o arquivo novo antes de ingerir; o original em dados/ não é sobrescrito"])
    shutil.copy2(origem, destino)
    return destino


def ingerir(projeto: Path, caminho: str | Path, nome: str | None = None, aba: str | None = None) -> dict:
    """Lê um arquivo e grava a tabela tipada. Devolve um resumo (sem os dados)."""
    projeto = Path(projeto)
    origem = Path(caminho).expanduser()
    if not origem.is_absolute():
        origem = projeto / origem
    if not origem.is_file():
        raise ErroDeLeitura(f"arquivo não encontrado: {caminho}")
    if origem.suffix.lower() not in EXTENSOES:
        raise ErroDeLeitura(f"formato {origem.suffix or 'sem extensão'} não suportado",
                            ["use CSV, TXT, TSV ou XLSX; para .pbix, use /bi-html:pbix (conversão de relatório em modo de importação)"])

    if origem.suffix.lower() in (".xlsx", ".xlsm"):
        cabecalho, corpo, leitura = _ler_excel(origem, aba)
        colunas_brutas = list(zip(*corpo)) if corpo else [()] * len(cabecalho)
        tipados = [_coluna_excel(list(v)) for v in colunas_brutas]
    else:
        texto, codificacao = _decodificar(origem.read_bytes())
        sep = _separador(texto)
        cabecalho, corpo = _linhas_csv(texto, sep)
        virgula = _decimal_virgula(cabecalho, corpo, sep)
        leitura = {"formato": "csv", "codificacao": codificacao, "separador": sep,
                   "decimal": "," if virgula else "."}
        colunas_brutas = list(zip(*corpo)) if corpo else [()] * len(cabecalho)
        tipados = [inferir_coluna(list(v), virgula) for v in colunas_brutas]

    nomes = [_nome_de_coluna(c) for c in cabecalho]
    vazias = [i + 1 for i, n in enumerate(nomes) if not n]
    if vazias:
        raise ErroDeLeitura("há colunas sem nome no cabeçalho",
                            [f"coluna {i}" for i in vazias] + ["dê um nome a cada coluna na primeira linha"])
    repetidas = sorted({n for n in nomes if nomes.count(n) > 1})
    if repetidas:
        raise ErroDeLeitura("há nomes de coluna repetidos no cabeçalho", repetidas)
    if not corpo:
        raise ErroDeLeitura("o arquivo tem cabeçalho, mas nenhuma linha de dados")

    original = _original_em_dados(projeto, origem)
    nome = nome_de_tabela(nome or origem.name)
    colunas = [{"nome": n, "original": c, "tipo": t, "valores": v, "obs": o}
               for n, c, (t, v, o) in zip(nomes, cabecalho, tipados)]
    destino = projeto / TABELAS / f"{nome}.parquet"
    _gravar_parquet(colunas, destino)

    manifesto = ler_manifesto(projeto)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    registro = {
        "origem": str(original.relative_to(projeto)) if original.is_relative_to(projeto) else str(original),
        "sha256": _hash(original),
        "bytes": original.stat().st_size,
        "ingerido_em": agora,
        "leitura": leitura,
        "parquet": str(destino.relative_to(projeto)),
        "linhas": len(corpo),
        "colunas": [{"nome": c["nome"], "original": c["original"], "tipo": c["tipo"], **({"obs": c["obs"]} if c["obs"] else {})}
                    for c in colunas],
    }
    manifesto["tabelas"][nome] = registro
    manifesto["eventos"].append({"quando": agora, "evento": "ingestao", "tabela": nome, "sha256": registro["sha256"]})
    _gravar_manifesto(projeto, manifesto)
    return {"tabela": nome, **registro}


def ingerir_texto(projeto: Path, texto: str, nome: str) -> dict:
    """Texto colado (por exemplo, copiado do Excel) vira dados/<nome>.csv e segue a ingestão normal."""
    projeto = Path(projeto)
    if not texto.strip():
        raise ErroDeLeitura("o texto colado está vazio")
    nome = nome_de_tabela(nome)
    destino = projeto / "dados" / f"{nome}.csv"
    destino.parent.mkdir(exist_ok=True)
    conteudo = texto.strip("\n") + "\n"
    if destino.exists() and destino.read_text(encoding="utf-8") != conteudo:
        raise ErroDeLeitura(f"já existe dados/{nome}.csv com outro conteúdo", ["escolha outro nome para o texto colado"])
    destino.write_text(conteudo, encoding="utf-8")
    return ingerir(projeto, destino, nome)
