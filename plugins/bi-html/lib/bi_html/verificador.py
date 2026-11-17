"""
Verificador do documento de decisão.

O Claude escreve `decisao/documento.md` a partir dos achados. Este módulo
confere, antes de qualquer renderização:

1. as seções obrigatórias (Resposta, Achados, O que os dados não permitem
   afirmar, Opções de decisão, Próximas perguntas);
2. que a seção Achados tem de três a cinco achados (`### título [A3]`), cada um
   citando pelo menos um achado calculado (`[A3]`) ou um item reproduzido da
   conclusão da análise (`[C1]`); item não reproduzido não pode ser citado;
3. que **todo número do texto** corresponde a um valor calculado: um valor dos
   achados, um valor observado na reprodução ou um número da conclusão que foi
   reproduzido, arredondado da forma como o texto escreveu. Datas e anos
   precisam estar no período dos dados.

Grava `saidas/bi/verificacao_documento.json`. O documento só é renderizado com
100% dos números rastreados.

Formato do `documento.md`:

    # Título curto
    **Pergunta:** a pergunta de negócio
    **Decisão:** a decisão que o documento apoia (opcional)

    ## Resposta
    Uma ou duas frases.

    ## Achados
    ### Frase que diz o achado [A6]
    Um parágrafo curto, com os números dos achados citados.

    ## O que os dados não permitem afirmar
    ## Opções de decisão
    ## Próximas perguntas
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .achados import ler as ler_achados
from .conclusao import ARQUIVO as ARQUIVO_REPRODUCAO
from .ingestao import PASTA_BI, ErroDeLeitura
from .numeros import Numero, extrair

ARQUIVO_DOCUMENTO = Path("decisao") / "documento.md"
ARQUIVO = PASTA_BI / "verificacao_documento.json"
SECOES = ["Resposta", "Achados", "O que os dados não permitem afirmar", "Opções de decisão", "Próximas perguntas"]
REF = re.compile(r"\[([AC]\d+)\]")


class ErroDeDocumento(ErroDeLeitura):
    pass


def ler_documento(projeto: Path) -> str:
    caminho = Path(projeto) / ARQUIVO_DOCUMENTO
    if not caminho.is_file():
        raise ErroDeDocumento(f"não existe {ARQUIVO_DOCUMENTO}", ["escreva o documento a partir dos achados"])
    return caminho.read_text(encoding="utf-8")


def separar(texto: str) -> dict:
    """Título, pergunta e o texto de cada seção ## do documento."""
    titulo = re.search(r"^#\s+(.+)$", texto, re.MULTILINE)
    pergunta = re.search(r"^\*\*Pergunta:\*\*\s*(.+)$", texto, re.MULTILINE)
    decisao = re.search(r"^\*\*Decisão:\*\*\s*(.+)$", texto, re.MULTILINE)
    secoes = {}
    partes = re.split(r"^##\s+(.+?)\s*$", texto, flags=re.MULTILINE)
    for nome, corpo in zip(partes[1::2], partes[2::2]):
        secoes[nome.strip()] = corpo.strip()
    achados = []
    for nome, corpo in zip(*[iter(re.split(r"^###\s+(.+?)\s*$", secoes.get("Achados", ""), flags=re.MULTILINE)[1:])] * 2):
        achados.append({"titulo": nome.strip(), "texto": corpo.strip(), "refs": REF.findall(nome + " " + corpo)})
    return {"titulo": titulo.group(1).strip() if titulo else None,
            "pergunta": pergunta.group(1).strip() if pergunta else None,
            "decisao": decisao.group(1).strip() if decisao else None,
            "secoes": secoes, "achados": achados}


def _repertorio(achados: dict, reproducao: dict | None) -> tuple[list[tuple[Numero, str]], set[str], set[int]]:
    """Números que o texto pode citar, com a origem de cada um; datas permitidas; anos cobertos."""
    numeros, datas, anos = [], set(), set()
    for a in achados["achados"]:
        for chave, texto in a["formatado"].items():
            for n in extrair(str(texto)):
                if n.tipo == "data":
                    datas.add(n.texto)
                elif n.tipo == "ano":
                    anos.add(int(n.valor))
                else:
                    # Compara com o valor sem arredondar, quando existe: arredondar o que já foi
                    # arredondado aceitaria números errados (17,496% → "17,5%" → "18%").
                    bruto = a["valores"].get(chave)
                    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
                        n = Numero(n.texto, n.tipo, float(bruto), n.casas, n.escala, n.inicio)
                    numeros.append((n, f"{a['id']}.{chave}"))
        cob = a["formatado"] if a["tipo"] == "cobertura" else {}
        if cob.get("inicio") and cob.get("fim"):
            for ano in range(int(cob["inicio"][-4:]), int(cob["fim"][-4:]) + 1):
                anos.add(ano)
    for chave in ("periodo", "comparacao"):
        p = achados.get(chave) or {}
        for k in ("inicio", "fim"):
            if p.get(k):
                a, m, d = p[k].split("-")
                datas.add(f"{d}/{m}/{a}")
                anos.add(int(a))
    for item in (reproducao or {}).get("itens", []):
        if item["estado"] != "reproduzido":
            continue
        for n in extrair(item["texto"]):
            if n.tipo == "ano":
                anos.add(int(n.valor))
            elif n.tipo != "data":
                numeros.append((n, f"C{item['item']}"))
        for v in item["verificacoes"]:
            for o in v.get("observado", []):
                for n in extrair(o["formatado"]):
                    numeros.append((Numero(n.texto, n.tipo, float(o["valor"]), n.casas, n.escala, n.inicio),
                                    f"C{item['item']}"))
    return numeros, datas, anos


def verificar(projeto: Path) -> dict:
    projeto = Path(projeto)
    texto = ler_documento(projeto)
    doc = separar(texto)
    achados = ler_achados(projeto)
    reproducao = None
    if (projeto / ARQUIVO_REPRODUCAO).is_file():
        reproducao = json.loads((projeto / ARQUIVO_REPRODUCAO).read_text(encoding="utf-8"))
    ids = {a["id"] for a in achados["achados"]}
    estados_c = {f"C{i['item']}": i["estado"] for i in (reproducao or {}).get("itens", [])}
    problemas = []

    if not doc["titulo"]:
        problemas.append("falta o título (linha que começa com '# ')")
    if not doc["pergunta"]:
        problemas.append("falta a linha '**Pergunta:** ...'")
    for s in SECOES:
        if s not in doc["secoes"] or not doc["secoes"][s].strip():
            problemas.append(f"falta a seção '## {s}' (ou ela está vazia)")
    resposta = doc["secoes"].get("Resposta", "")
    if len(re.findall(r"[.!?](\s|$)", resposta)) > 2:
        problemas.append("a Resposta deve ter no máximo duas frases")
    if not 3 <= len(doc["achados"]) <= 5:
        problemas.append(f"a seção Achados deve ter de três a cinco achados (tem {len(doc['achados'])})")
    for a in doc["achados"]:
        if not a["refs"]:
            problemas.append(f"o achado '{a['titulo']}' não cita nenhum [A…] ou [C…]")
    for ref in sorted({r for a in doc["achados"] for r in a["refs"]} | set(REF.findall(texto))):
        if ref.startswith("A") and ref not in ids:
            problemas.append(f"[{ref}] não existe nos achados calculados")
        if ref.startswith("C"):
            if ref not in estados_c:
                problemas.append(f"[{ref}] não é um item da conclusão da análise")
            elif estados_c[ref] != "reproduzido":
                problemas.append(f"[{ref}] não foi reproduzido pela camada de métricas e não pode entrar no documento")

    repertorio, datas, anos = _repertorio(achados, reproducao)
    numeros = []
    cabecalho = [("Título", doc["titulo"] or ""), ("Pergunta", doc["pergunta"] or ""), ("Decisão", doc["decisao"] or "")]
    for secao_nome, secao_texto in cabecalho + list(doc["secoes"].items()):
        for n in extrair(secao_texto):
            if n.tipo == "data":
                origens = ["período"] if n.texto in datas else []
            elif n.tipo == "ano":
                origens = ["período"] if int(n.valor) in anos else []
            else:
                origens = sorted({o for c, o in repertorio if c.tipo == n.tipo and n.bate_com(c.valor, c.tipo)})
            numeros.append({"secao": secao_nome, "texto": n.texto, "rastreado": bool(origens), "origens": origens})
    nao_rastreados = [n for n in numeros if not n["rastreado"]]
    for n in nao_rastreados:
        problemas.append(f"número sem origem em '{n['secao']}': {n['texto']}")

    resultado = {
        "ok": not problemas,
        "numeros": numeros,
        "rastreados": len(numeros) - len(nao_rastreados),
        "total_de_numeros": len(numeros),
        "cobertura_pct": 100.0 if not numeros else round(100 * (len(numeros) - len(nao_rastreados)) / len(numeros), 1),
        "achados_no_texto": len(doc["achados"]),
        "problemas": problemas,
    }
    destino = projeto / ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resultado
