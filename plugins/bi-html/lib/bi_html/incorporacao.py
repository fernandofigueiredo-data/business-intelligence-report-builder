"""
incorporacao.py — Fluxo 2, via (b): o relatório original do Power BI ao lado do convertido.

A página de comparação (`saidas/bi/comparativo/index.html`) põe lado a lado o relatório
publicado no serviço do Power BI e a página convertida pelo bi-html (via (a)), com o resumo da
conversão e o status de cada visual. É uma página estática: abre do disco e pode ser hospedada em
qualquer lugar (GitHub Pages, a vitrine da fase F9).

Ela não serve como Artifact do claude.ai: o contrato de página dos Artifacts recusa incorporar
outros sites, para qualquer leitor. O teste da F7b (provas/f7b) registrou o outro lado: os links
do Power BI de "Publicar na Web" (`/view?r=`) e de incorporação segura (`/reportEmbed`) não
bloqueiam a incorporação; a página comum do serviço (`/home`) bloqueia.

O caminho depende da licença:
- Free: só "Publicar na Web" (link público, sem login; precisa ser habilitado pelo administrador
  do tenant). Qualquer pessoa com o link vê os dados: use com dados fictícios ou públicos.
- Pro ou PPU: também a incorporação segura (o leitor faz login e precisa de licença).

Os números da página saem do relatório da conversão (`saidas/bi/pbix/conversao.json`); nenhum é
digitado à mão.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .conversao import RELATORIO
from .ingestao import PASTA_BI, ErroDeLeitura, ler_manifesto

PASTA = PASTA_BI / "comparativo"
LICENCAS = {"free", "pro", "ppu"}
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
STATUS = {"convertido": "convertido", "parcial": "parcial", "filtro_global": "virou filtro",
          "nao_convertido": "não convertido", "decorativo": "decorativo"}


class ErroDeIncorporacao(ErroDeLeitura):
    pass


def validar_link(url: str, licenca: str = "free") -> dict:
    """Confere o link do Power BI e diz por qual caminho da via (b) ele veio."""
    licenca = (licenca or "").strip().lower()
    if licenca not in LICENCAS:
        raise ErroDeIncorporacao(f"licença {licenca!r} desconhecida", ["use free, pro ou ppu"])
    p = urlparse((url or "").strip())
    if p.scheme != "https" or p.hostname != "app.powerbi.com":
        raise ErroDeIncorporacao("o link precisa ser do serviço do Power BI (https://app.powerbi.com/...)",
                                 ["copie o link de 'Publicar na Web' (Arquivo > Inserir relatório > Publicar na Web) "
                                  "ou o de incorporação segura (Inserir relatório > Site ou portal)"])
    q = parse_qs(p.query)
    avisos = []
    if p.path.rstrip("/") == "/view" and q.get("r", [""])[0]:
        via = "publicar_na_web"
        avisos.append("link de 'Publicar na Web': qualquer pessoa com ele vê os dados do relatório, sem login; "
                      "use só com dados fictícios ou públicos")
    elif p.path.rstrip("/") == "/reportEmbed" and GUID.match(q.get("reportId", [""])[0]):
        via = "incorporacao_segura"
        if licenca == "free":
            avisos.append("a incorporação segura exige login e licença Pro ou PPU de cada leitor; com conta Free, "
                          "o caminho é 'Publicar na Web'")
    else:
        raise ErroDeIncorporacao("o link não é de incorporação de relatório",
                                 ["esperado .../view?r=... (Publicar na Web) ou .../reportEmbed?reportId=... "
                                  "(incorporação segura); a página comum do serviço bloqueia a incorporação"])
    return {"via": via, "url": p.geturl(), "licenca": licenca, "avisos": avisos}


def _resumo(rel: dict) -> dict:
    medidas = [m for m in rel["medidas"] if m["classe"] != "implicita"]
    traduzidas = [m for m in medidas if m["classe"] == "traduzida"]
    validadas = [m for m in traduzidas if (m.get("equivalencia") or {}).get("validada")]
    visuais = [v for p in rel["paginas"] for v in p.get("visuais") or []]
    com_dado = [v for v in visuais if v["status"] != "decorativo"]
    return {
        "arquivo": rel["arquivo"]["nome"],
        "tabelas": len(rel["tabelas"]), "tabelas_iguais": sum(t["iguais"] for t in rel["tabelas"]),
        "medidas": len(medidas), "traduzidas": len(traduzidas), "validadas": len(validadas),
        "nao_validadas": [m["medida"] for m in traduzidas if m not in validadas],
        "visuais_com_dado": len(com_dado),
        "visuais_convertidos": sum(v["status"] in ("convertido", "filtro_global") for v in com_dado),
        "visuais_parciais": sum(v["status"] == "parcial" for v in com_dado),
    }


def _n(x: int) -> str:
    return f"{x:,}".replace(",", ".")


def _pagina(resumo: dict, rel: dict, link: dict | None, pagina_convertida: str) -> str:
    e = html.escape
    if link:
        original = (f'<iframe title="Relatório original no Power BI" src="{e(link["url"])}" loading="lazy" '
                    'allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>')
        nota_original = ("Publicado com “Publicar na Web”: qualquer pessoa com o link vê os dados."
                         if link["via"] == "publicar_na_web" else
                         "Incorporação segura: o leitor entra com a conta Microsoft e precisa de licença Pro ou PPU.")
    else:
        original = """<div class="vazio">
  <p class="vazio-titulo">O original entra aqui quando o relatório estiver publicado</p>
  <ol>
    <li>Envie o .pbix ao serviço do Power BI (Meu workspace &gt; Carregar).</li>
    <li>Abra o relatório e use Arquivo &gt; Inserir relatório &gt; Publicar na Web. O administrador do tenant precisa ter habilitado essa opção.</li>
    <li>Copie o link (app.powerbi.com/view?r=…) e rode <code>/bi-html:comparar &lt;link&gt;</code>.</li>
  </ol>
  <p class="nota">Com conta Free, “Publicar na Web” é o único caminho. O link fica público: use dados fictícios ou públicos.</p>
</div>"""
        nota_original = "Ainda sem link: a página mostra o passo a passo."
    linhas = []
    for p in rel["paginas"]:
        for v in p.get("visuais") or []:
            if v["status"] == "decorativo":
                continue
            motivo = "; ".join(v["motivos"]) or "—"
            linhas.append(f'<tr><td>{e(p["nome"])}</td><td>{e(v["titulo"] or "(sem título)")}</td>'
                          f'<td><code>{e(v["tipo_power_bi"])}</code></td>'
                          f'<td><span class="st st-{e(v["status"])}">{e(STATUS.get(v["status"], v["status"]))}</span></td>'
                          f'<td class="motivo">{e(motivo)}</td></tr>')
    nao_validadas = ""
    if resumo["nao_validadas"]:
        nao_validadas = ('<p class="alerta">Não bateram com o Power BI no teste de equivalência e aparecem com '
                         f'“(não validada)”: {e(", ".join(resumo["nao_validadas"]))}.</p>')
    return f"""<title>Original e convertido</title>
<style>
/* Duas telas lado a lado sobre os tokens do projeto; a tabela de visuais embaixo. */
@import url("tokens.css");
:root {{ --gutter: max(16px, env(safe-area-inset-left, 0px)); }}
* {{ box-sizing: border-box; }}
body {{ background: var(--background); color: var(--foreground); font-family: var(--font-sans); margin: 0;
       padding-block: 24px 40px; padding-left: max(16px, env(safe-area-inset-left, 0px));
       padding-right: max(16px, env(safe-area-inset-right, 0px)); }}
header, main, section {{ max-width: 1680px; margin-inline: auto; }}
h1 {{ font-family: var(--font-titulo); font-size: 1.6rem; margin: 0 0 4px; text-wrap: balance; }}
.sub {{ color: var(--muted-foreground); margin: 0 0 16px; }}
.fatos {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 20px; padding: 0; list-style: none; }}
.fatos li {{ border: var(--border-width) solid var(--border); border-radius: 999px; padding: 4px 12px;
            font-size: .85rem; font-variant-numeric: tabular-nums; }}
.fatos strong {{ font-weight: 600; }}
.alerta {{ color: var(--alerta); margin: -8px 0 20px; font-size: .9rem; }}
.telas {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.tela {{ display: flex; flex-direction: column; gap: 8px; min-width: 0; }}
.tela h2 {{ font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted-foreground); margin: 0; }}
.quadro {{ border: var(--border-width) solid var(--border); border-radius: var(--radius); background: var(--card);
          aspect-ratio: 16 / 10; max-width: 100%; overflow: hidden; }}
.quadro iframe {{ width: 100%; height: 100%; border: 0; display: block; }}
.nota {{ color: var(--muted-foreground); font-size: .8rem; margin: 0; }}
.vazio {{ padding: 24px; display: flex; flex-direction: column; gap: 12px; height: 100%; justify-content: center; }}
.vazio-titulo {{ font-weight: 600; margin: 0; }}
.vazio ol {{ margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; max-width: 60ch; }}
code {{ font-family: var(--font-mono); font-size: .85em; }}
section {{ margin-top: 32px; }}
section h2 {{ font-family: var(--font-titulo); font-size: 1.1rem; margin: 0 0 12px; }}
.rolagem {{ overflow-x: auto; border: var(--border-width) solid var(--border); border-radius: var(--radius); }}
table {{ border-collapse: collapse; width: 100%; font-size: .85rem; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: var(--border-width) solid var(--border); vertical-align: top; }}
th {{ color: var(--muted-foreground); font-weight: 600; background: var(--muted); }}
td.motivo {{ color: var(--muted-foreground); min-width: 24ch; }}
.st {{ display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: .75rem; white-space: nowrap;
      border: var(--border-width) solid currentColor; }}
.st-convertido, .st-filtro_global {{ color: var(--positivo); }}
.st-parcial {{ color: var(--alerta); }}
.st-nao_convertido {{ color: var(--negativo); }}
@media (max-width: 1100px) {{ .telas {{ grid-template-columns: 1fr; }} .quadro {{ aspect-ratio: 4 / 5; }} }}
</style>
<header>
  <h1>Original e convertido</h1>
  <p class="sub">{e(resumo["arquivo"])}: à esquerda o relatório no Power BI, à direita a mesma página recalculada pela camada de métricas do bi-html.</p>
  <ul class="fatos">
    <li><strong>{resumo["tabelas_iguais"]} de {resumo["tabelas"]}</strong> tabelas com linhas idênticas</li>
    <li><strong>{resumo["traduzidas"]} de {resumo["medidas"]}</strong> medidas traduzidas</li>
    <li><strong>{resumo["validadas"]} de {resumo["traduzidas"]}</strong> traduzidas batem com o Power BI</li>
    <li><strong>{resumo["visuais_convertidos"]} de {resumo["visuais_com_dado"]}</strong> visuais com dado convertidos, {resumo["visuais_parciais"]} em parte</li>
  </ul>
  {nao_validadas}
</header>
<main class="telas">
  <div class="tela">
    <h2>No Power BI</h2>
    <div class="quadro">{original}</div>
    <p class="nota">{e(nota_original)}</p>
  </div>
  <div class="tela">
    <h2>No bi-html</h2>
    <div class="quadro"><iframe title="Página convertida pelo bi-html" src="{e(pagina_convertida)}" loading="lazy"></iframe></div>
    <p class="nota">Medidas sem tradução para a camada de métricas ficam de fora; a tabela abaixo diz o que mudou em cada visual.</p>
  </div>
</main>
<section>
  <h2>Visual a visual</h2>
  <div class="rolagem"><table>
    <thead><tr><th>Página</th><th>Visual</th><th>Tipo no Power BI</th><th>No bi-html</th><th>Motivo</th></tr></thead>
    <tbody>
{chr(10).join(linhas)}
    </tbody>
  </table></div>
</section>
"""


def _documento(pagina: str) -> str:
    """Documento completo: título e estilos no head, o resto no body."""
    cabeca, _, corpo = pagina.partition("</style>\n")
    return ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{cabeca}</style>\n</head>\n<body>\n{corpo}</body>\n</html>\n')


def montar_comparativo(projeto: Path, link: str | None = None, licenca: str = "free", pagina: str | None = None) -> dict:
    """Grava saidas/bi/comparativo/ (index.html, convertido.html e tokens.css) e registra a via (b)."""
    projeto = Path(projeto)
    arquivo_rel = projeto / RELATORIO
    if not arquivo_rel.is_file():
        raise ErroDeIncorporacao("não há conversão de .pbix neste projeto", ["rode /bi-html:pbix antes de comparar"])
    rel = json.loads(arquivo_rel.read_text(encoding="utf-8"))
    info = validar_link(link, licenca) if link else None
    if info is None and (licenca or "free").lower() not in LICENCAS:
        raise ErroDeIncorporacao(f"licença {licenca!r} desconhecida", ["use free, pro ou ppu"])
    paginas = [p for p in rel["paginas"] if p.get("html")]
    if not paginas:
        raise ErroDeIncorporacao("a conversão não renderizou nenhuma página", ["veja saidas/bi/pbix/fidelidade.md"])
    escolhida = next((p for p in paginas if pagina and p["nome"].lower() == pagina.lower()), None)
    if pagina and not escolhida:
        raise ErroDeIncorporacao(f"página {pagina!r} não foi convertida",
                                 [f"páginas convertidas: {', '.join(p['nome'] for p in paginas)}"])
    escolhida = escolhida or paginas[0]
    pasta = projeto / PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    shutil.copy2(projeto / escolhida["html"], pasta / "convertido.html")
    tokens = projeto / "design" / "tokens.css"
    if tokens.is_file():
        shutil.copy2(tokens, pasta / "tokens.css")
    resumo = _resumo(rel)
    (pasta / "index.html").write_text(_documento(_pagina(resumo, rel, info, "convertido.html")), encoding="utf-8")
    registro = {"via": info["via"] if info else None, "licenca": (licenca or "free").lower(),
                "link": info["url"] if info else None, "pagina": escolhida["nome"],
                "gravado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "artifact": "não: o Artifact do claude.ai recusa incorporar outros sites; hospede a pasta comparativo/"}
    manifesto = ler_manifesto(projeto)
    manifesto["incorporacao"] = registro
    manifesto["eventos"].append({"quando": registro["gravado_em"], "evento": "comparativo", "via": registro["via"]})
    (projeto / PASTA_BI / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                                                       encoding="utf-8")
    return {"pasta": PASTA.as_posix(), "html": (PASTA / "index.html").as_posix(), "pagina": escolhida["nome"],
            "via": registro["via"], "avisos": info["avisos"] if info else
            ["sem link do Power BI: o lado do original mostra o passo a passo para publicar"],
            "resumo": resumo}
