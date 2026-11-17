"""
Reprodução da conclusão do notebook pela camada de métricas.

Cada item da conclusão do `analise.ipynb` que afirma um número é um achado da
análise. Para entrar no documento de decisão, ele precisa ser reproduzido: a
camada de métricas calcula o mesmo número, por outro caminho, e o resultado
confere com o que a análise escreveu.

O Claude escreve `decisao/verificacoes.yaml`, um item por número afirmado,
dizendo qual consulta reproduz aquele número e que tipo de afirmação é:

    - item: 1                      # posição do item na conclusão (1 = primeiro)
      numero: "39%"                # o número exatamente como está escrito no item
      metrica: participacao_faturamento
      dimensoes: [regiao]
      onde: {regiao: Sudeste}      # a linha que o número descreve
      afirmacao: aproximado        # aproximado | mais_de | menos_de | igual
    - item: 2
      numero: "60%"
      metrica: faturamento_por_dia
      dimensoes: [mes]
      variacao: {de: {mes: "2025-10"}, para: [{mes: "2025-11"}, {mes: "2025-12"}]}
      afirmacao: mais_de
    - item: 3
      numero: "36%"
      metrica: margem
      dimensoes: [canal_venda]
      todas_as_linhas: true        # o número vale para cada linha
      afirmacao: aproximado

O número citado precisa existir no texto do item (não dá para "verificar" um
número que a análise não escreveu). Tolerâncias de `aproximado`: 1,5 ponto
percentual para percentuais e 3% para os demais valores.

Grava `saidas/bi/reproducao.json` com um estado por item: `reproduzido`,
`nao_reproduzido` (inclui número sem verificação) ou `sem_numero` (o item não
afirma número, como um próximo passo).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .consulta import consultar, formatar
from .contrato import NOTEBOOK, ler_notebook
from .ingestao import PASTA_BI, ErroDeLeitura
from .modelo import carregar
from .numeros import extrair

ARQUIVO_VERIFICACOES = Path("decisao") / "verificacoes.yaml"
ARQUIVO = PASTA_BI / "reproducao.json"
AFIRMACOES = ("aproximado", "mais_de", "menos_de", "igual")
TOLERANCIA_PP = 0.015
TOLERANCIA_RELATIVA = 0.03


class ErroDeReproducao(ErroDeLeitura):
    pass


def _numeros_afirmados(texto: str):
    return [n for n in extrair(texto) if n.tipo not in ("ano", "data")]


def _linha(linhas: list[dict], onde: dict) -> dict | None:
    for l in linhas:
        if all(str(l.get(k)) == str(v) for k, v in onde.items()):
            return l
    return None


def _confere(observado: float, citado, afirmacao: str) -> bool:
    alvo = citado.valor
    if afirmacao == "mais_de":
        return observado > alvo
    if afirmacao == "menos_de":
        return observado < alvo
    if afirmacao == "igual":
        return citado.bate_com(observado, citado.tipo)
    if citado.tipo in ("pct", "pp"):
        return abs(observado - alvo) <= TOLERANCIA_PP
    return abs(observado - alvo) <= TOLERANCIA_RELATIVA * abs(alvo)


def _verificar(projeto: Path, v: dict, itens: list[str], modelo: dict) -> dict:
    resultado = {"item": v.get("item"), "numero": v.get("numero"), "metrica": v.get("metrica"),
                 "afirmacao": v.get("afirmacao")}
    problemas = []
    idx = v.get("item")
    if not isinstance(idx, int) or not 1 <= idx <= len(itens):
        problemas.append(f"item {idx!r} não existe na conclusão (há {len(itens)} itens)")
    if v.get("afirmacao") not in AFIRMACOES:
        problemas.append(f"afirmacao deve ser uma de: {', '.join(AFIRMACOES)}")
    if v.get("metrica") not in modelo["metricas"]:
        problemas.append(f"métrica {v.get('metrica')!r} não existe no modelo")
    modos = [k for k in ("onde", "variacao", "todas_as_linhas") if v.get(k)]
    if len(modos) > 1:
        problemas.append("use só um de: onde, variacao, todas_as_linhas")
    citado = None
    if not problemas:
        candidatos = [n for n in _numeros_afirmados(itens[idx - 1]) if n.texto.replace(" ", "") == str(v.get("numero", "")).replace(" ", "")]
        if not candidatos:
            problemas.append(f"o número {v.get('numero')!r} não está escrito no item {idx}")
        else:
            citado = candidatos[0]
    if problemas:
        return resultado | {"estado": "invalida", "problemas": problemas}

    m = v["metrica"]
    formato = modelo["metricas"][m]["formato"]
    try:
        r = consultar(projeto, [m], v.get("dimensoes") or [], periodo=v.get("periodo", "tudo"))
    except ErroDeLeitura as e:
        return resultado | {"estado": "invalida", "problemas": [e.mensagem] + e.detalhes}
    linhas = r["linhas"]
    observados = []
    if v.get("variacao"):
        de = _linha(linhas, v["variacao"]["de"])
        paras = v["variacao"]["para"]
        paras = paras if isinstance(paras, list) else [paras]
        if de is None or any(_linha(linhas, p) is None for p in paras):
            return resultado | {"estado": "invalida", "problemas": ["alguma linha de 'variacao' não existe no resultado"]}
        for p in paras:
            l = _linha(linhas, p)
            observados.append({"linha": p, "valor": float(l[m]) / float(de[m]) - 1, "tipo": "pct"})
    elif v.get("todas_as_linhas"):
        for l in linhas:
            if l[m] is not None:
                observados.append({"linha": {d: l[d] for d in v.get("dimensoes") or []}, "valor": float(l[m]),
                                   "tipo": "pct" if formato == "percentual" else "valor"})
    else:
        l = _linha(linhas, v.get("onde") or {}) if v.get("onde") else (linhas[0] if linhas else None)
        if l is None or l[m] is None:
            return resultado | {"estado": "invalida", "problemas": ["a linha de 'onde' não existe no resultado"]}
        observados.append({"linha": v.get("onde") or {}, "valor": float(l[m]),
                           "tipo": "pct" if formato == "percentual" else "valor"})
    for o in observados:
        o["confere"] = _confere(o["valor"], citado, v["afirmacao"])
        o["formatado"] = formatar(o["valor"], "percentual" if o["tipo"] == "pct" else formato,
                                  modelo["metricas"][m].get("unidade"))
    ok = bool(observados) and all(o["confere"] for o in observados)
    return resultado | {"estado": "reproduzido" if ok else "nao_reproduzido", "observado": observados}


def reproduzir(projeto: Path) -> dict:
    import yaml

    projeto = Path(projeto)
    if not (projeto / NOTEBOOK).is_file():
        raise ErroDeReproducao("não há analise.ipynb: a reprodução só vale para projetos que passaram pela análise")
    notebook = ler_notebook(projeto / NOTEBOOK)
    itens = notebook["itens_conclusao"]
    if not itens:
        raise ErroDeReproducao("o notebook não tem itens de conclusão")
    modelo, _, _ = carregar(projeto)
    verificacoes = []
    if (projeto / ARQUIVO_VERIFICACOES).is_file():
        verificacoes = yaml.safe_load((projeto / ARQUIVO_VERIFICACOES).read_text(encoding="utf-8")) or []
        if not isinstance(verificacoes, list):
            raise ErroDeReproducao(f"{ARQUIVO_VERIFICACOES} deve ser uma lista de verificações")
    feitas = [_verificar(projeto, v, itens, modelo) for v in verificacoes]

    por_item = []
    for i, texto in enumerate(itens, start=1):
        numeros = [n.texto for n in _numeros_afirmados(texto)]
        verifs = [f for f in feitas if f.get("item") == i]
        sem_verificacao = [n for n in numeros if not any(f.get("numero", "").replace(" ", "") == n.replace(" ", "") for f in verifs)]
        if not numeros:
            estado = "sem_numero"
        elif sem_verificacao or not verifs or any(f["estado"] != "reproduzido" for f in verifs):
            estado = "nao_reproduzido"
        else:
            estado = "reproduzido"
        por_item.append({"item": i, "texto": texto, "numeros": numeros, "estado": estado,
                         "sem_verificacao": sem_verificacao, "verificacoes": verifs})
    resultado = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "itens": por_item,
        "resumo": {e: sum(1 for p in por_item if p["estado"] == e) for e in ("reproduzido", "nao_reproduzido", "sem_numero")},
        "verificacoes_invalidas": [f for f in feitas if f["estado"] == "invalida"],
    }
    destino = projeto / ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return resultado
