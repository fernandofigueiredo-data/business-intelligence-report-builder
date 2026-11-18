#!/usr/bin/env python3
"""
executar.py — prova da F8: o fluxo completo do bi-html num caso real, sem publicação.

    uv run --no-project --python 3.12 --with duckdb --with openpyxl --with pyyaml --with jsonschema \\
        python provas/f8/executar.py

O caso fica em casos/eleicoes/ (ignorado pelo git): uma cópia dos arquivos do projeto do autor
(o conjunto de dados, o dicionário, o tema e o .pbix), feita sem alterar a pasta de origem, e os
arquivos que o Claude escreveu no fluxo (modelo/metricas.yaml revisado, dashboard/spec.json e
decisao/documento.md). O .pbix é convertido em casos/eleicoes-pbix/.

O script refaz cada etapa pelas mesmas funções que o servidor MCP expõe e grava só o estado de cada
uma, o tempo e contagens (linhas, achados, números verificados), nunca valores do caso, em
resultados.json e RESULTADO.md. Nada é publicado: as saídas ficam em disco.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
CASO = RAIZ / "casos" / "eleicoes"
CASO_PBIX = RAIZ / "casos" / "eleicoes-pbix"
RESULTADOS = AQUI / "resultados.json"
RESULTADO_MD = AQUI / "RESULTADO.md"
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))


def etapas() -> list[tuple[str, str, object]]:
    from bi_html.achados import gerar
    from bi_html.assistente import renderizar_assistente
    from bi_html.ciclo import estado
    from bi_html.conversao import converter
    from bi_html.design import importar
    from bi_html.documento import renderizar_documento
    from bi_html.exportacao import exportar
    from bi_html.incorporacao import montar_comparativo
    from bi_html.ingestao import ingerir
    from bi_html.modelo import carregar, registrar_linhagem
    from bi_html.perfil import perfilar
    from bi_html.render import renderizar
    from bi_html.verificador import verificar

    def ingestao():
        r = ingerir(CASO, "original/eleicoes_presidente.csv")
        return {"linhas": r["linhas"], "colunas": len(r["colunas"])}

    def perfil():
        q = perfilar(CASO, "eleicoes_presidente")
        return {"alertas": len(q["alertas"]), "bloqueios": len(q["bloqueios"]), "dados_pessoais": len(q["dados_pessoais"])}

    def modelo():
        m, arq, _ = carregar(CASO)
        registrar_linhagem(CASO, m, arq)
        return {"metricas": len(m["metricas"]), "dimensoes": len(m["dimensoes"])}

    def design():
        r = importar(CASO, "original/tema_eleicoes_br.json")
        return {"aa": r["aa"], "ajustes_de_contraste": len(r["ajustes_de_contraste"])}

    def dashboard():
        r = renderizar(CASO)
        return {"blocos": r["blocos"], "dentro_da_meta": r["dentro_da_meta"], "avisos": len(r["avisos"]),
                "publicacao_bloqueada": len(r["publicacao_bloqueada"])}

    def achados():
        return {"achados": len(gerar(CASO)["achados"])}

    def documento():
        v = verificar(CASO)
        if not v["ok"]:
            raise RuntimeError(f"verificação falhou: {len(v['problemas'])} problema(s)")
        r = renderizar_documento(CASO)
        return {"verificacao": r["verificacao"], "palavras": r["palavras"]}

    def offline():
        r = exportar(CASO)
        return {"bytes": r["bytes"]}

    def assistente():
        r = renderizar_assistente(CASO)
        return {"perguntas": r["perguntas"], "publicacao_bloqueada": len(r["publicacao_bloqueada"])}

    def conversao():
        CASO_PBIX.mkdir(parents=True, exist_ok=True)
        r = converter(CASO_PBIX, CASO / "original" / "eleicoes-presidenciais-br.pbix")
        eq = r["equivalencia"]
        return {"tabelas_iguais": r["tabelas_iguais"], "medidas": r["medidas"],
                "traduzidas_que_batem": sum(v.split(" de ")[0] == v.split(" de ")[1] for v in eq.values()),
                "traduzidas_testadas": len(eq), "paginas_com_spec": len(r["paginas"]), "avisos": len(r["avisos"])}

    def comparativo():
        r = montar_comparativo(CASO_PBIX)
        return {"via": r["via"], "visuais_com_dado": r["resumo"]["visuais_com_dado"]}

    def ciclo():
        e = estado(CASO)
        return {"estado_do_ciclo": e["etapa"]}

    return [
        ("ingestao", "Ingestão do CSV (atalho sem análise prévia)", ingestao),
        ("perfil", "Perfil e dados pessoais", perfil),
        ("modelo", "Modelo de métricas revisado", modelo),
        ("design", "Design enviado (tema do Power BI do projeto)", design),
        ("dashboard", "Dashboard", dashboard),
        ("achados", "Achados", achados),
        ("documento", "Documento de decisão verificado", documento),
        ("offline", "Cópia para envio (sem publicar)", offline),
        ("assistente", "Página do assistente (sem publicar)", assistente),
        ("conversao", "Conversão do .pbix do projeto", conversao),
        ("comparativo", "Comparação com o original (sem link)", comparativo),
        ("ciclo", "Estado do ciclo", ciclo),
    ]


def executar() -> dict:
    if not (CASO / "original" / "eleicoes_presidente.csv").is_file():
        raise SystemExit("falta a cópia do caso em casos/eleicoes/original (ver provas/f8/README.md)")
    saida = []
    for chave, nome, funcao in etapas():
        t = time.perf_counter()
        try:
            r = {"etapa": chave, "nome": nome, "ok": True, **funcao()}
        except Exception as e:  # noqa: BLE001
            r = {"etapa": chave, "nome": nome, "ok": False, "erro": f"{type(e).__name__}: {e}",
                 "local": traceback.format_exc().splitlines()[-3].strip()}
        r["tempo_s"] = round(time.perf_counter() - t, 2)
        saida.append(r)
        print(f"{chave:12} {'ok' if r['ok'] else 'ERRO':5} {r['tempo_s']:6.1f}s")
    resultado = {"executado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                 "publicado": False, "etapas": saida}
    RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULTADO_MD.write_text(gerar_md(resultado), encoding="utf-8")
    return resultado


def gerar_md(r: dict) -> str:
    L = ["# F8 — fluxo completo no caso real, sem publicação", "",
         "Gerado por `provas/f8/executar.py` a partir de `resultados.json`; não edite à mão. Só estados e contagens: "
         "nenhum valor do caso entra aqui.", "",
         f"**Execução:** {r['executado_em']} · nada publicado.", "",
         "| Etapa | Resultado | Detalhes | Tempo (s) |", "|---|---|---|---|"]
    for e in r["etapas"]:
        detalhes = "; ".join(f"{k}: {v}" for k, v in e.items() if k not in ("etapa", "nome", "ok", "tempo_s", "local"))
        L.append(f"| {e['nome']} | {'ok' if e['ok'] else 'erro'} | {detalhes} | {str(e['tempo_s']).replace('.', ',')} |")
    L += ["", "Os problemas que o caso revelou estão em [`ISSUES.md`](ISSUES.md).", ""]
    return "\n".join(L)


if __name__ == "__main__":
    if "--so-md" in sys.argv:
        RESULTADO_MD.write_text(gerar_md(json.loads(RESULTADOS.read_text(encoding="utf-8"))), encoding="utf-8")
    else:
        executar()
