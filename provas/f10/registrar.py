#!/usr/bin/env python3
"""
registrar.py — prova da F10: o assistente do dashboard contra perguntas de resposta conhecida.

    uv run --no-project --python 3.12 --with duckdb --with pyyaml --with jsonschema \\
        python provas/f10/registrar.py CAMINHO/avaliacoes/<id>.json

A bateria roda no Artifact publicado (exemplo de vendas fictício), pelo botão "Testar o assistente",
na conta de quem clica. A página grava cada pergunta, a resposta, as consultas que o assistente fez
e a correção na coleção `avaliacoes` do banco do Artifact. Este script recebe esse registro
(exportado com a ferramenta ArtifactData, `list` com `out_dir`), refaz a correção em Python (com
numeros.py, sobre o cubo recalculado pela camada de métricas) e grava resultados.json e
RESULTADO.md. Sem argumento, só regenera RESULTADO.md.

Critério de aceite (seção 10 do plano): pelo menos 90% de respostas corretas e nenhuma resposta
com número fora do cubo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
RESULTADOS = AQUI / "resultados.json"
RESULTADO_MD = AQUI / "RESULTADO.md"
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))


def registrar(registro: dict, projeto: Path | None = None) -> dict:
    from bi_html.assistente import avaliar
    from bi_html.dashboard import montar

    montado = montar(Path(projeto or RAIZ / "exemplos" / "vendas"))
    itens = {i["id"]: i for i in registro["itens"]}
    refeita = avaliar(montado, {k: i["resposta"] for k, i in itens.items()},
                      {k: i.get("consultas") or [] for k, i in itens.items()})
    linhas = []
    for r in refeita["itens"]:
        i = itens.get(r["id"], {})
        linhas.append({"id": r["id"], "pergunta": i.get("pergunta"), "tipo": i.get("tipo"), "resposta": i.get("resposta"),
                       "consultas": i.get("consultas"), "correta_na_pagina": i.get("correta"),
                       "correta_em_python": r["correta"], "numeros_fora": r["numeros_fora"]})
    return {
        "quando": registro.get("quando"), "dashboard": registro.get("dashboard"), "modelo": registro.get("modelo"),
        "total": refeita["total"], "acertos_python": refeita["acertos"], "acertos_pagina": registro.get("acertos"),
        "com_numero_fora": refeita["com_numero_fora"],
        "correcoes_iguais": all(l["correta_na_pagina"] == l["correta_em_python"] for l in linhas),
        "criterio": {"minimo_de_acertos": 0.9, "atende": refeita["acertos"] >= 0.9 * refeita["total"]
                     and refeita["com_numero_fora"] == 0},
        "itens": linhas,
    }


def _pl(n: int, palavra: str) -> str:
    return f"{n} {palavra}" + ("" if n == 1 else "s")


def gerar_md(r: dict) -> str:
    pct = f"{100 * r['acertos_python'] / r['total']:.0f}".replace(".", ",")
    L = ["# F10 — assistente contra perguntas de resposta conhecida", "",
         "Gerado por `provas/f10/registrar.py` a partir de `resultados.json`; não edite à mão.", "",
         f"**Bateria:** {r['quando']} · dashboard \"{r['dashboard']}\" (dados fictícios) · nível de modelo `{r['modelo']}`.", "",
         f"**Resultado:** {r['acertos_python']} de {r['total']} corretas ({pct}%); {_pl(r['com_numero_fora'], 'resposta')} "
         f"com número fora do que o assistente consultou. Critério (pelo menos 90% e nenhum número fora): "
         f"**{'atende' if r['criterio']['atende'] else 'não atende'}**. A correção da página e a refeita em Python "
         + ("concordam em todas as perguntas." if r["correcoes_iguais"] else
            f"divergem em {_pl(sum(i['correta_na_pagina'] != i['correta_em_python'] for i in r['itens']), 'pergunta')}."),
         "",
         "| Id | Tipo | Pergunta | Resposta | Correta | Números fora |", "|---|---|---|---|---|---|"]
    for i in r["itens"]:
        resposta = (i["resposta"] or "").replace("\n", " ").replace("|", "\\|")
        L.append(f"| {i['id']} | {i['tipo']} | {i['pergunta']} | {resposta} | {'sim' if i['correta_em_python'] else 'não'} | "
                 f"{', '.join(i['numeros_fora']) or '—'} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    if len(sys.argv) > 1:
        r = registrar(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
        RESULTADOS.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        r = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    RESULTADO_MD.write_text(gerar_md(r), encoding="utf-8")
    print(f"{r['acertos_python']} de {r['total']} corretas; {r['com_numero_fora']} com número fora; "
          f"critério {'atende' if r['criterio']['atende'] else 'não atende'}")


if __name__ == "__main__":
    main()
