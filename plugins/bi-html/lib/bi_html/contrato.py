"""
Checagem do contrato entre o plugin analise-dados e o bi-html (CONTRATO.md).

A etapa de BI começa quando a análise entrega três arquivos na pasta do projeto:

- `saidas/dados_tratados.parquet`: os dados depois do tratamento;
- `analise.ipynb`: o notebook, com uma seção de conclusão em markdown;
- `contexto.md`: pergunta de negócio, público, dicionário de colunas e decisões.

Cada item recebe um estado:

- `ok`: presente e utilizável;
- `alerta`: utilizável, mas com algo a conferir (não bloqueia);
- `ausente` ou `invalido`: bloqueia a passagem para o BI, com a correção indicada.

Além do veredito, a checagem devolve o que o BI reaproveita sem perguntar de
novo ao usuário: o objetivo do `contexto.md`, o dicionário de colunas, as
decisões de tratamento, os itens da conclusão e o esquema dos dados tratados.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

VERSAO = "0.1"
PARQUET = "saidas/dados_tratados.parquet"
NOTEBOOK = "analise.ipynb"
CONTEXTO = "contexto.md"
DESIGN = "estilos/design-system.md"

COMO_GRAVAR_PARQUET = ('grave os dados tratados no notebook com '
                       'df.to_parquet("saidas/dados_tratados.parquet") logo depois do tratamento '
                       '(o /painel do analise-dados insere essa célula se faltar)')
VAZIO = {"", "?", "...", "…", "-", "—"}


# ---------------------------------------------------------------- contexto.md

def _campo(texto: str, rotulo: str) -> str | None:
    m = re.search(rf"^\s*-\s*\*\*{re.escape(rotulo)}:?\*\*:?\s*(.*)$", texto, re.MULTILINE | re.IGNORECASE)
    if not m:
        return None
    valor = m.group(1).strip().rstrip(".").strip()
    return None if valor in VAZIO else m.group(1).strip()


def _secao(texto: str, titulo: str) -> str:
    m = re.search(rf"^##\s+{re.escape(titulo)}\s*$(.*?)(?=^##\s|\Z)", texto, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else ""


def _dicionario(texto: str) -> list[dict]:
    """Linhas das tabelas `| Coluna | Significado | ... |` da seção Dados, com o arquivo de origem."""
    colunas, arquivo, cabecalho = [], None, None
    for linha in _secao(texto, "Dados").splitlines():
        if linha.startswith("### "):
            arquivo, cabecalho = linha[4:].strip(), None
            continue
        if not linha.strip().startswith("|"):
            cabecalho = None if not linha.strip() else cabecalho
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if cabecalho is None:
            cabecalho = [c.lower() for c in celulas]
            continue
        if set("".join(celulas)) <= set("-: "):
            continue
        item = dict(zip(cabecalho, celulas))
        nome = item.get("coluna", "").strip("` ")
        if nome and nome not in VAZIO:
            colunas.append({"arquivo": arquivo, "coluna": nome, "significado": item.get("significado", ""),
                            "unidade": item.get("unidade / formato", ""), "observacoes": item.get("observações", "")})
    return colunas


def _itens(secao: str) -> list[str]:
    return [l.strip()[2:].strip() for l in secao.splitlines() if l.strip().startswith(("- ", "* "))]


def ler_contexto(caminho: Path) -> dict:
    texto = caminho.read_text(encoding="utf-8")
    return {
        "pergunta_negocio": _campo(texto, "Pergunta de negócio"),
        "publico": _campo(texto, "Quem lê o resultado"),
        "decisao": _campo(texto, "Decisão que a análise apoia"),
        "dicionario": _dicionario(texto),
        "decisoes_tratamento": _itens(_secao(texto, "Decisões de tratamento")),
    }


# ---------------------------------------------------------------- analise.ipynb

TITULO_CONCLUSAO = re.compile(r"^\s{0,3}#{1,4}\s*conclus(ão|ões|ao|oes)\b", re.IGNORECASE | re.MULTILINE)


def ler_notebook(caminho: Path) -> dict:
    nb = json.loads(caminho.read_text(encoding="utf-8"))
    celulas = nb.get("cells", [])
    conclusao = None
    for c in celulas:
        texto = "".join(c.get("source", []))
        if c.get("cell_type") == "markdown" and TITULO_CONCLUSAO.search(texto):
            conclusao = texto
    codigo = [c for c in celulas if c.get("cell_type") == "code" and "".join(c.get("source", [])).strip()]
    contagens = [c.get("execution_count") for c in codigo]
    em_ordem = bool(contagens) and all(isinstance(n, int) for n in contagens) and contagens == sorted(contagens)
    return {
        "celulas": len(celulas),
        "conclusao": conclusao,
        "itens_conclusao": _itens(conclusao or ""),
        "executado_em_ordem": em_ordem,
        "grava_parquet": any(PARQUET in "".join(c.get("source", [])) for c in codigo),
    }


# ---------------------------------------------------------------- dados_tratados.parquet

def ler_parquet(caminho: Path) -> dict:
    import duckdb

    con = duckdb.connect()
    try:
        alvo = str(caminho)
        esquema = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [alvo]).fetchall()
        colunas = [(nome, tipo) for nome, tipo, *_ in esquema if nome != "__index_level_0__"]
        contagem = ", ".join(f'count("{n.replace(chr(34), chr(34) * 2)}")' for n, _ in colunas)
        linha = con.execute(f"SELECT count(*), {contagem} FROM read_parquet(?)", [alvo]).fetchone()
    finally:
        con.close()
    total = linha[0]
    return {
        "linhas": total,
        "colunas": [{"coluna": n, "tipo": t, "nulos": total - preenchidas}
                    for (n, t), preenchidas in zip(colunas, linha[1:])],
    }


# ---------------------------------------------------------------- veredito

def _item(arquivo, estado, detalhe, correcao=None):
    d = {"arquivo": arquivo, "estado": estado, "detalhe": detalhe}
    if correcao:
        d["correcao"] = correcao
    return d


def checar(projeto: Path) -> dict:
    projeto = Path(projeto)
    itens, contexto, notebook, dados = [], None, None, None

    # contexto.md
    caminho = projeto / CONTEXTO
    if not caminho.is_file():
        itens.append(_item(CONTEXTO, "ausente", "não existe na pasta do projeto",
                           "rode /analise do analise-dados: ele cria o contexto.md com o usuário"))
    else:
        contexto = ler_contexto(caminho)
        faltam = [r for r, c in (("Pergunta de negócio", "pergunta_negocio"), ("Quem lê o resultado", "publico"))
                  if not contexto[c]]
        if faltam:
            itens.append(_item(CONTEXTO, "invalido", f"sem resposta em: {', '.join(faltam)}",
                               "complete o Objetivo do contexto.md com o usuário (o /analise faz essas perguntas)"))
        elif not contexto["dicionario"]:
            itens.append(_item(CONTEXTO, "alerta", "objetivo preenchido, mas sem dicionário de colunas",
                               "descreva as colunas na seção Dados do contexto.md"))
        elif not contexto["decisao"]:
            itens.append(_item(CONTEXTO, "alerta", "sem 'Decisão que a análise apoia'; o documento de decisão fica genérico"))
        else:
            itens.append(_item(CONTEXTO, "ok", f"objetivo completo e {len(contexto['dicionario'])} colunas no dicionário"))

    # analise.ipynb
    caminho = projeto / NOTEBOOK
    if not caminho.is_file():
        itens.append(_item(NOTEBOOK, "ausente", "não existe na pasta do projeto",
                           "rode /analise do analise-dados para criar e conduzir o notebook"))
    else:
        try:
            notebook = ler_notebook(caminho)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            itens.append(_item(NOTEBOOK, "invalido", f"o arquivo não é um notebook legível ({e.__class__.__name__})"))
        else:
            if not notebook["conclusao"]:
                itens.append(_item(NOTEBOOK, "invalido", "não tem seção de conclusão em markdown (título '## Conclusão')",
                                   "escreva a conclusão no fim do notebook (skill analista-senior) e rode /revisar"))
            elif not notebook["executado_em_ordem"]:
                itens.append(_item(NOTEBOOK, "alerta", "as células não foram executadas de cima a baixo",
                                   "rode /validar do analise-dados para provar que o notebook roda do zero"))
            else:
                itens.append(_item(NOTEBOOK, "ok", f"conclusão com {len(notebook['itens_conclusao'])} itens; "
                                                   "células executadas em ordem"))

    # saidas/dados_tratados.parquet
    caminho = projeto / PARQUET
    if not caminho.is_file():
        dica = "o notebook já tem a célula; rode-o de novo" if notebook and notebook["grava_parquet"] else COMO_GRAVAR_PARQUET
        itens.append(_item(PARQUET, "ausente", "os dados tratados não foram gravados", dica))
    else:
        try:
            dados = ler_parquet(caminho)
        except Exception as e:  # o duckdb levanta tipos variados para arquivo corrompido
            itens.append(_item(PARQUET, "invalido", f"não foi possível ler o arquivo ({e.__class__.__name__})",
                               COMO_GRAVAR_PARQUET))
        else:
            avisos = []
            if dados["linhas"] == 0:
                itens.append(_item(PARQUET, "invalido", "o arquivo não tem linhas", COMO_GRAVAR_PARQUET))
            else:
                com_nulos = [f"{c['coluna']} ({c['nulos']})" for c in dados["colunas"] if c["nulos"]]
                if com_nulos:
                    avisos.append("colunas com vazios: " + ", ".join(com_nulos))
                if contexto and contexto["dicionario"]:
                    nomes = {c["coluna"] for c in dados["colunas"]}
                    documentadas = {c["coluna"] for c in contexto["dicionario"]}
                    tratamento = " ".join(contexto["decisoes_tratamento"])
                    sumiram = sorted(documentadas - nomes)
                    sem_definicao = sorted(n for n in nomes - documentadas if f"`{n}`" not in tratamento)
                    if sumiram:
                        avisos.append("colunas do dicionário que não estão nos dados tratados: " + ", ".join(sumiram))
                    if sem_definicao:
                        avisos.append("colunas sem definição no contexto.md: " + ", ".join(sem_definicao))
                if (projeto / NOTEBOOK).is_file() and (projeto / NOTEBOOK).stat().st_mtime > caminho.stat().st_mtime:
                    avisos.append("o notebook foi alterado depois da gravação dos dados tratados; rode-o de novo")
                resumo = f"{dados['linhas']} linhas e {len(dados['colunas'])} colunas"
                itens.append(_item(PARQUET, "alerta" if avisos else "ok",
                                   resumo + ("; " + "; ".join(avisos) if avisos else "")))

    bloqueios = [i for i in itens if i["estado"] in ("ausente", "invalido")]
    return {
        "versao_contrato": VERSAO,
        "pronto_para_bi": not bloqueios,
        "itens": itens,
        "faltando": [f"{i['arquivo']}: {i['detalhe']}" + (f" → {i['correcao']}" if i.get("correcao") else "")
                     for i in bloqueios],
        "design_system": (projeto / DESIGN).is_file(),
        "contexto": contexto,
        "conclusao": notebook["itens_conclusao"] if notebook else [],
        "esquema": dados,
    }
