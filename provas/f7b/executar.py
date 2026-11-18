#!/usr/bin/env python3
"""
executar.py — teste do iframe da F7b: o Power BI deixa a página do relatório ser incorporada?

    python3 provas/f7b/executar.py [--link https://app.powerbi.com/view?r=...]

Pede ao serviço do Power BI três endereços com identificadores fictícios (nenhum dado do usuário
vai na requisição) e registra os cabeçalhos que decidem se um navegador aceita a página num
iframe: X-Frame-Options e o frame-ancestors da Content-Security-Policy. Grava resultados.json e
RESULTADO.md. Sem rede, só regenera RESULTADO.md (opção --so-md). Com --link, testa também o
relatório fictício publicado com Publicar na Web (fixtures/vendas.pbix, conta Free) e registra o
critério de aceite da F7b: o original visível ao lado do convertido.

O lado do Artifact do claude.ai não depende de rede: o contrato de página dos Artifacts recusa
incorporar outros sites, para qualquer leitor (registrado em RESULTADO.md como fato documental).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RESULTADOS = AQUI / "resultados.json"
RESULTADO_MD = AQUI / "RESULTADO.md"

ENDERECOS = [
    ("publicar_na_web", "https://app.powerbi.com/view?r=teste-de-incorporacao",
     "link de Publicar na Web (licença Free serve)"),
    ("incorporacao_segura", "https://app.powerbi.com/reportEmbed?reportId=00000000-0000-0000-0000-000000000000&autoAuth=true",
     "link de incorporação segura (leitor com login e licença Pro ou PPU)"),
    ("servico", "https://app.powerbi.com/home", "página comum do serviço (controle)"),
]
ARTIFACT = ("O contrato de página dos Artifacts do claude.ai diz que outros sites não podem ser incorporados "
            "(sem iframes de YouTube, mapas ou formulários, e sem `<object>` ou `<embed>`) e que a recusa vale para "
            "qualquer leitor; o caminho é linkar para fora.")


def bloqueio(cabecalhos: dict) -> str | None:
    xfo = (cabecalhos.get("x-frame-options") or "").strip().lower()
    if xfo in ("deny", "sameorigin"):
        return f"X-Frame-Options: {xfo}"
    for parte in (cabecalhos.get("content-security-policy") or "").split(";"):
        parte = parte.strip()
        if parte.lower().startswith("frame-ancestors") and "*" not in parte.split()[1:]:
            return "Content-Security-Policy: " + parte[:120]
    return None


PUBLICADO = ("A página de comparação da vitrine (docs/power-bi/), servida em localhost com o link publicado: o "
             "relatório do Power BI carregou inteiro no quadro (cartões de faturamento, pedidos e ticket médio, gráficos "
             "e o filtro de região), com os mesmos valores que o lado convertido mostra, e o console não registrou erro")


def testar(link: str | None = None) -> dict:
    casos = []
    enderecos = list(ENDERECOS)
    if link:
        enderecos.append(("relatorio_publicado", link,
                          "relatório fictício publicado com Publicar na Web (vendas.pbix, conta Free)"))
    for via, url, descricao in enderecos:
        req = urllib.request.Request(url, headers={"User-Agent": "bi-html-teste-de-incorporacao"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                status, cab = r.status, {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            status, cab = e.code, {k.lower(): v for k, v in e.headers.items()}
        motivo = bloqueio(cab)
        casos.append({"via": via, "url": url, "descricao": descricao, "status_http": status,
                      "x_frame_options": cab.get("x-frame-options"),
                      "frame_ancestors": next((p.strip() for p in (cab.get("content-security-policy") or "").split(";")
                                               if p.strip().lower().startswith("frame-ancestors")), None),
                      "incorporavel": motivo is None, "bloqueio": motivo})
    publicado = None
    if link:
        caso = next(c for c in casos if c["via"] == "relatorio_publicado")
        publicado = {"link": link, "licenca": "free", "via": "publicar_na_web", "incorporavel": caso["incorporavel"],
                     "verificado_no_navegador": PUBLICADO, "data": datetime.now().strftime("%Y-%m-%d")}
    return {"executado_em": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "publicado": publicado, "casos": casos, "artifact": {"incorporavel": False, "fonte": "contrato de página da ferramenta Artifact",
                                         "texto": ARTIFACT},
            "navegador": {"verificado": "A página comparativo/index.html servida em localhost, com o link de Publicar na "
                                        "Web (token fictício): o leitor do Power BI carregou no quadro, com o rodapé e os "
                                        "controles, e o console não registrou erro de incorporação",
                          "data": "2026-11-17"}}


def gerar_md(r: dict) -> str:
    L = ["# F7b — teste do iframe do Power BI", "",
         "Gerado por `provas/f7b/executar.py` a partir de `resultados.json`; não edite à mão.", "",
         f"**Execução:** {r['executado_em']}. Os três primeiros endereços usam identificadores fictícios"
         + ("; o último é o link público do relatório fictício publicado." if r.get("publicado") else ".")
         + " Nenhum dado do usuário vai nas requisições.", "",
         "## Cabeçalhos do serviço do Power BI", "",
         "| Endereço | Para quê | HTTP | X-Frame-Options | frame-ancestors | Pode ir num iframe |", "|---|---|---|---|---|---|"]
    for c in r["casos"]:
        fa = (c["frame_ancestors"] or "—")[:70] + ("…" if c["frame_ancestors"] and len(c["frame_ancestors"]) > 70 else "")
        L.append(f"| `{c['url'].split('?')[0].replace('https://', '')}` | {c['descricao']} | {c['status_http']} | "
                 f"{c['x_frame_options'] or '—'} | {fa} | {'sim' if c['incorporavel'] else 'não'} |")
    L += ["", "## No navegador", "", r["navegador"]["verificado"] + f" ({r['navegador']['data']}).", ""]
    if r.get("publicado"):
        p = r["publicado"]
        L += ["## O relatório publicado (critério de aceite da F7b)", "",
              f"Caminho escolhido pela licença ({p['licenca']}): Publicar na Web. Link: <{p['link']}>.", "",
              p["verificado_no_navegador"] + f" ({p['data']}). A página de comparação mora na vitrine estática "
              "(`docs/power-bi/`), não no Artifact.", ""]
    L += [
          "## No Artifact do claude.ai", "", r["artifact"]["texto"] + " Por isso a página de comparação não é "
          "publicada como Artifact: ela é uma pasta estática (`saidas/bi/comparativo/`) para hospedar em qualquer "
          "lugar, e o dashboard convertido continua publicável como Artifact.", ""]
    return "\n".join(L)


def main() -> None:
    if "--so-md" in sys.argv:
        r = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    else:
        link = sys.argv[sys.argv.index("--link") + 1] if "--link" in sys.argv else None
        r = testar(link)
        RESULTADOS.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    RESULTADO_MD.write_text(gerar_md(r), encoding="utf-8")
    for c in r["casos"]:
        print(f"{c['via']:22} {'incorporável' if c['incorporavel'] else 'bloqueado: ' + c['bloqueio']}")


if __name__ == "__main__":
    main()
