#!/usr/bin/env python3
"""
executar.py — prova da F7: a conversão de .pbix (Fluxo 2, via (a)) rodada com arquivos reais.

    uv run --no-project --python 3.12 --with duckdb --with pyyaml --with jsonschema \\
        python -I provas/f7/executar.py --arquivo ifdata=/caminho/a.pbix --arquivo eleicoes=... --arquivo lab1=...

Sem --arquivo, só regenera RESULTADO.md a partir de resultados.json.

Cada arquivo é convertido num processo próprio (que chama o processo de leitura do .pbix), numa
pasta de projeto temporária: tabelas, modelo e páginas renderizadas não entram no repositório.
Ficam aqui o relatório de cada conversão (conversao.json, sem os caminhos locais) e o
fidelidade.md, mais o resumo em RESULTADO.md, com os critérios de aceite da F7:

- contagem de linhas idêntica por tabela;
- todas as medidas classificadas (traduzida, texto ou não traduzida, com o motivo);
- as traduzidas batem com a avaliação de referência (motor DAX do pbix-mcp) numa amostra de
  contextos;
- relatório de fidelidade por visual.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
SAIDAS = AQUI / "saidas"
RESULTADOS = AQUI / "resultados.json"
RESULTADO_MD = AQUI / "RESULTADO.md"
LIB = RAIZ / "plugins" / "bi-html" / "lib"


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def filho(caminho: str, projeto: str, destino: str) -> None:
    """Converte um arquivo e grava o resumo com tempo e pico de memória (deste processo e dos filhos)."""
    import resource

    sys.path.insert(0, str(LIB))
    from bi_html.conversao import converter
    from bi_html.ingestao import ErroDeLeitura

    t = time.perf_counter()
    try:
        r = {"ok": True, **converter(Path(projeto), caminho)}
    except ErroDeLeitura as e:
        r = {"ok": False, "erro": e.mensagem, "detalhes": e.detalhes}
    escala = 1024 * 1024 if sys.platform == "darwin" else 1024
    picos = [resource.getrusage(q).ru_maxrss / escala for q in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)]
    r.update({"tempo_s": round(time.perf_counter() - t, 2), "pico_rss_mb": round(max(picos), 1)})
    Path(destino).write_text(json.dumps(r, ensure_ascii=False, default=str), encoding="utf-8")


def _limpar(relatorio: dict) -> dict:
    """conversao.json sem nada que dependa da máquina (os caminhos já são relativos ao projeto)."""
    r = dict(relatorio)
    r.pop("renderizadas", None)
    return r


def executar(arquivos: dict[str, Path]) -> dict:
    if SAIDAS.exists():
        shutil.rmtree(SAIDAS)
    SAIDAS.mkdir()
    resultado = {"executado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                 "ambiente": {"python": platform.python_version(), "maquina": f"{platform.machine()} {platform.system()}"},
                 "arquivos": {}}
    for apelido, caminho in arquivos.items():
        with tempfile.TemporaryDirectory() as tmp:
            projeto = Path(tmp) / "projeto"
            projeto.mkdir()
            destino = Path(tmp) / "resumo.json"
            proc = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--filho", str(caminho),
                                   str(projeto), str(destino)], capture_output=True, text=True)
            if not destino.is_file():
                raise SystemExit(f"{apelido}: a conversão falhou\n{proc.stderr[-2000:]}")
            resumo = json.loads(destino.read_text(encoding="utf-8"))
            pasta = SAIDAS / apelido
            pasta.mkdir()
            info = {"arquivo": {"nome": caminho.name, "bytes": caminho.stat().st_size, "sha256": _sha256(caminho)},
                    "ok": resumo["ok"], "tempo_s": resumo["tempo_s"], "pico_rss_mb": resumo["pico_rss_mb"]}
            if resumo["ok"]:
                rel = json.loads((projeto / "saidas" / "bi" / "pbix" / "conversao.json").read_text(encoding="utf-8"))
                (pasta / "conversao.json").write_text(json.dumps(_limpar(rel), ensure_ascii=False, indent=2) + "\n",
                                                      encoding="utf-8")
                shutil.copy2(projeto / "saidas" / "bi" / "pbix" / "fidelidade.md", pasta / "fidelidade.md")
                info["resumo"] = criterios(rel)
                info["anexos"] = [f"saidas/{apelido}/conversao.json", f"saidas/{apelido}/fidelidade.md"]
            else:
                info.update(erro=resumo["erro"], detalhes=resumo["detalhes"])
            resultado["arquivos"][apelido] = info
            print(f"{apelido:10} {'ok' if resumo['ok'] else 'recusado':8} {resumo['tempo_s']:7.1f}s "
                  f"{resumo['pico_rss_mb']:7.0f} MB  {json.dumps(info.get('resumo') or info.get('erro'), ensure_ascii=False)[:160]}",
                  flush=True)
    RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULTADO_MD.write_text(gerar_md(resultado), encoding="utf-8")
    return resultado


def criterios(rel: dict) -> dict:
    """Os quatro critérios de aceite da F7, calculados do relatório de uma conversão."""
    tabelas = rel["tabelas"]
    medidas = [m for m in rel["medidas"] if m["classe"] != "implicita"]
    traduzidas = [m for m in medidas if m["classe"] == "traduzida"]
    implicitas = [m for m in rel["medidas"] if m["classe"] == "implicita"]
    validadas = [m for m in traduzidas if (m.get("equivalencia") or {}).get("validada")]
    imp_validadas = [m for m in implicitas if (m.get("equivalencia") or {}).get("validada")]
    casos = rel["equivalencia"]["casos"]
    visuais = [v for p in rel["paginas"] for v in p.get("visuais") or []]
    return {
        "tabelas": len(tabelas), "tabelas_com_linhas_iguais": sum(t["iguais"] for t in tabelas),
        "medidas": len(medidas), "medidas_classificadas": sum(1 for m in medidas if m["classe"] in
                                                             ("traduzida", "texto", "nao_traduzida")),
        "classes": {c: sum(1 for m in medidas if m["classe"] == c) for c in ("traduzida", "texto", "nao_traduzida")},
        "traduzidas_validadas": len(validadas), "traduzidas": len(traduzidas),
        "nao_validadas": sorted(m["medida"] for m in traduzidas if m not in validadas),
        "implicitas": len(implicitas), "implicitas_validadas": len(imp_validadas),
        "contextos_testados": len(casos), "contextos_que_batem": sum(c["bate"] for c in casos),
        "visuais": len(visuais), "visuais_por_status": {s: sum(1 for v in visuais if v["status"] == s)
                                                        for s in sorted({v["status"] for v in visuais})},
        "visuais_com_status": sum(1 for v in visuais if v["status"]),
        "paginas": len(rel["paginas"]), "paginas_com_spec": sum(1 for p in rel["paginas"] if p.get("spec")),
        "formato_relatorio": rel["formato_relatorio"], "tema_importado": rel["tema"].get("importado"),
    }


def gerar_md(resultado: dict) -> str:
    """RESULTADO.md a partir de resultados.json (o teste regenera e compara)."""
    br = lambda x, c=1: f"{x:,.{c}f}".replace(",", "§").replace(".", ",").replace("§", ".")  # noqa: E731
    L = ["# F7 — conversão de .pbix com arquivos reais", "",
         "Gerado por `provas/f7/executar.py` a partir de `resultados.json`; não edite à mão.", "",
         f"**Execução:** {resultado['executado_em']} · Python {resultado['ambiente']['python']} · "
         f"{resultado['ambiente']['maquina']}", "",
         "## Critérios de aceite", "",
         "| Arquivo | Linhas idênticas por tabela | Medidas classificadas | Traduzidas que batem com o Power BI "
         "| Contextos testados que batem | Visuais no relatório de fidelidade |", "|---|---|---|---|---|---|"]
    for a, info in resultado["arquivos"].items():
        if not info["ok"]:
            L.append(f"| `{a}` | recusado: {info['erro']} | — | — | — | — |")
            continue
        r = info["resumo"]
        L.append(f"| `{a}` | {r['tabelas_com_linhas_iguais']} de {r['tabelas']} | {r['medidas_classificadas']} de "
                 f"{r['medidas']} | {r['traduzidas_validadas']} de {r['traduzidas']} | {r['contextos_que_batem']} de "
                 f"{r['contextos_testados']} | {r['visuais_com_status']} de {r['visuais']} |")
    L += ["", "## Medidas e visuais", "",
          "| Arquivo | Traduzidas | Texto | Não traduzidas | Agregações implícitas (validadas) | Visuais por status | "
          "Páginas com spec | Relatório | Tema |", "|---|---|---|---|---|---|---|---|---|"]
    for a, info in resultado["arquivos"].items():
        if not info["ok"]:
            continue
        r = info["resumo"]
        status = ", ".join(f"{s}: {n}" for s, n in r["visuais_por_status"].items())
        L.append(f"| `{a}` | {r['classes']['traduzida']} | {r['classes']['texto']} | {r['classes']['nao_traduzida']} | "
                 f"{r['implicitas']} ({r['implicitas_validadas']}) | {status} | {r['paginas_com_spec']} de {r['paginas']} | "
                 f"{r['formato_relatorio']} | {'importado' if r['tema_importado'] else 'não'} |")
    nao = [(a, m) for a, info in resultado["arquivos"].items() if info["ok"] for m in info["resumo"]["nao_validadas"]]
    if nao:
        L += ["", "**Traduzidas que não bateram** (levam \"(não validada)\" no modelo; o motivo está no fidelidade.md): "
              + "; ".join(f"`{a}` {m}" for a, m in nao) + "."]
    L += ["", "## Arquivos, tempo e memória", "",
          "Tempo e pico de memória da conversão inteira (extração, tradução, teste de equivalência e renderização), "
          "incluindo os processos de leitura do .pbix.", "",
          "| Arquivo | Nome | Tamanho | SHA-256 (12) | Tempo (s) | Pico (MB) | Saída |", "|---|---|---|---|---|---|---|"]
    for a, info in resultado["arquivos"].items():
        saida = " · ".join(f"[{Path(x).name}]({x})" for x in info.get("anexos", [])) or "—"
        L.append(f"| `{a}` | {info['arquivo']['nome']} | {br(info['arquivo']['bytes'] / 2**20)} MB | "
                 f"`{info['arquivo']['sha256'][:12]}` | {br(info['tempo_s'])} | {br(info['pico_rss_mb'], 0)} | {saida} |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--filho":
        filho(*sys.argv[2:5])
        return
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--arquivo", action="append", default=[], metavar="APELIDO=CAMINHO")
    args = ap.parse_args()
    if not args.arquivo:
        RESULTADO_MD.write_text(gerar_md(json.loads(RESULTADOS.read_text(encoding="utf-8"))), encoding="utf-8")
        print(f"regenerado: {RESULTADO_MD.relative_to(RAIZ)}")
        return
    arquivos = {}
    for item in args.arquivo:
        apelido, _, caminho = item.partition("=")
        p = Path(caminho).expanduser().resolve()
        if not apelido or not p.is_file():
            ap.error(f"arquivo inválido: {item}")
        arquivos[apelido] = p
    executar(arquivos)
    print(f"gravado: {RESULTADOS.relative_to(RAIZ)} e {RESULTADO_MD.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
