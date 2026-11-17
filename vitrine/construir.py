#!/usr/bin/env python3
"""
construir.py — fase F9: a vitrine pública do portfólio, como site estático em docs/.

    uv run --no-project --python 3.12 --with duckdb --with openpyxl --with pyyaml --with jsonschema \\
        vitrine/construir.py [--link-power-bi https://app.powerbi.com/view?r=...]

1. Monta os quatro exemplos (exemplos/construir.py): vendas, marketing, financeiro e o ciclo completo
   com o documento de decisão.
2. Converte o .pbix fictício (fixtures/vendas.pbix) em exemplos/pbix/ e monta a comparação com o
   original no Power BI (via (b)); sem --link-power-bi, o lado do original mostra o passo a passo.
3. Copia os HTML para docs/ e gera docs/index.html.

Tudo é de dados fictícios. O site é estático: o GitHub Pages serve docs/ direto (Settings > Pages >
Deploy from a branch > /docs), e qualquer outra hospedagem estática também serve. Os números da
página inicial saem dos relatórios gerados (manifesto e relatório da conversão), não são digitados.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
sys.path.insert(0, str(RAIZ / "exemplos"))

DEMOS = [
    ("vendas", "Vendas de uma rede de lojas", "Planilha CSV com separador ponto e vírgula e vírgula decimal, "
     "ingerida pelo atalho, sem análise prévia.", "CSV · atalho"),
    ("marketing", "Mídia paga por campanha", "Planilha Excel com datas nativas: investimento, cliques, "
     "conversões e custo por resultado.", "Excel · atalho"),
    ("financeiro", "DRE realizado contra orçado", "Competência mensal, contas agrupadas e o orçamento ao lado do "
     "realizado.", "CSV · atalho"),
]


def _br(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def montar_exemplos() -> dict:
    from construir import construir

    feitos = {}
    for nome in ("vendas", "marketing", "financeiro", "ciclo"):
        r = construir(nome)
        feitos[nome] = r
        print(f"exemplo {nome}: {r['blocos']} blocos")
    return feitos


def converter_pbix(link: str | None) -> dict:
    from bi_html.conversao import converter
    from bi_html.incorporacao import montar_comparativo

    projeto = RAIZ / "exemplos" / "pbix"
    if projeto.exists():
        shutil.rmtree(projeto)
    projeto.mkdir(parents=True)
    r = converter(projeto, RAIZ / "fixtures" / "vendas.pbix")
    c = montar_comparativo(projeto, link, "free")
    print(f"pbix: {r['medidas']} · comparação: {c['via'] or 'sem link'}")
    return {"conversao": r, "comparativo": c, "projeto": projeto}


def copiar(feitos: dict, pbix: dict) -> None:
    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir()
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    for nome in ("vendas", "marketing", "financeiro"):
        (DOCS / nome).mkdir()
        shutil.copy2(RAIZ / "exemplos" / nome / "saidas" / "bi" / "dashboard.html", DOCS / nome / "index.html")
    (DOCS / "ciclo").mkdir()
    shutil.copy2(RAIZ / "exemplos" / "ciclo" / "saidas" / "bi" / "dashboard.html", DOCS / "ciclo" / "index.html")
    shutil.copy2(RAIZ / "exemplos" / "ciclo" / "saidas" / "bi" / "decisao.html", DOCS / "ciclo" / "decisao.html")
    projeto = pbix["projeto"]
    shutil.copytree(projeto / "saidas" / "bi" / "comparativo", DOCS / "power-bi")
    for pagina in (projeto / "saidas" / "bi" / "paginas").glob("*.html"):
        if not pagina.name.endswith(".artifact.html"):
            shutil.copy2(pagina, DOCS / "power-bi" / pagina.name)


CSS = """
/* Uma coluna de leitura com a grade de demonstrações; azul-petróleo como único acento. */
:root {
  --fundo: #f6f7f8; --superficie: #ffffff; --texto: #14181f; --apagado: #5a6270; --linha: #dde1e6;
  --acento: #0b6e74; --acento-texto: #ffffff; --sinal: #0b6e74;
  --fonte: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --fonte-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --fundo: #0f1318; --superficie: #171c23; --texto: #e6e9ee; --apagado: #9aa3b0; --linha: #2a313b;
    --acento: #4fb7bd; --acento-texto: #08201f; --sinal: #6fd0d5; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --fundo: #0f1318; --superficie: #171c23; --texto: #e6e9ee; --apagado: #9aa3b0; --linha: #2a313b;
  --acento: #4fb7bd; --acento-texto: #08201f; --sinal: #6fd0d5; color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo); color: var(--texto); font-family: var(--fonte); line-height: 1.55;
       padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.miolo { max-width: 1080px; margin-inline: auto; padding-block: 48px 64px; display: flex; flex-direction: column; gap: 56px; }
h1, h2, h3 { text-wrap: balance; line-height: 1.2; margin: 0; }
h1 { font-size: clamp(2rem, 4vw, 2.8rem); font-weight: 600; letter-spacing: -0.01em; }
h2 { font-size: 1.35rem; font-weight: 600; }
h3 { font-size: 1.05rem; font-weight: 600; }
p { margin: 0; max-width: 65ch; }
.olho { font-family: var(--fonte-mono); font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; color: var(--sinal); }
.abertura { display: flex; flex-direction: column; gap: 16px; }
.tese { font-size: 1.15rem; color: var(--apagado); }
.regra { font-family: var(--fonte-mono); font-size: .9rem; border-left: 3px solid var(--acento); padding: 4px 0 4px 14px; color: var(--texto); }
section { display: flex; flex-direction: column; gap: 20px; }
.grade { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.demo { background: var(--superficie); border: 1px solid var(--linha); border-radius: 8px; padding: 20px;
        display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.demo .tipo { font-family: var(--fonte-mono); font-size: .75rem; color: var(--apagado); }
.demo p { color: var(--apagado); font-size: .95rem; }
.links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto; padding-top: 6px; }
.links a { font-size: .9rem; font-weight: 500; text-decoration: none; border-radius: 6px; padding: 6px 12px;
           border: 1px solid var(--linha); color: var(--texto); }
.links a.principal { background: var(--acento); border-color: var(--acento); color: var(--acento-texto); }
.links a:hover { border-color: var(--acento); }
.links a:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; }
.destaque { grid-column: 1 / -1; }
.numeros { display: flex; flex-wrap: wrap; gap: 8px; list-style: none; padding: 0; margin: 0; }
.numeros li { font-family: var(--fonte-mono); font-size: .8rem; border: 1px solid var(--linha); border-radius: 999px;
              padding: 3px 10px; font-variant-numeric: tabular-nums; }
.etapas { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; list-style: none; padding: 0; margin: 0; counter-reset: etapa; }
.etapas li { border-top: 2px solid var(--linha); padding-top: 12px; display: flex; flex-direction: column; gap: 6px; counter-increment: etapa; }
.etapas li::before { content: counter(etapa); font-family: var(--fonte-mono); color: var(--sinal); font-size: .85rem; }
.etapas p { color: var(--apagado); font-size: .93rem; }
footer { border-top: 1px solid var(--linha); padding-top: 20px; color: var(--apagado); font-size: .88rem; display: flex; flex-direction: column; gap: 6px; }
code { font-family: var(--fonte-mono); font-size: .88em; }
"""


def pagina_inicial(feitos: dict, pbix: dict) -> str:
    e = html.escape
    rel = json.loads((pbix["projeto"] / "saidas" / "bi" / "pbix" / "conversao.json").read_text(encoding="utf-8"))
    from bi_html.incorporacao import _resumo

    r = _resumo(rel)
    paginas = [p for p in rel["paginas"] if p.get("html")]
    primeira = Path(paginas[0]["html"]).name if paginas else "index.html"
    cartoes = []
    for nome, titulo, texto, tipo in DEMOS:
        cartoes.append(f"""<article class="demo">
  <span class="tipo">{e(tipo)}</span>
  <h3>{e(titulo)}</h3>
  <p>{e(texto)} {feitos[nome]["blocos"]} blocos calculados pela camada de métricas.</p>
  <div class="links"><a class="principal" href="{nome}/">Abrir o dashboard</a></div>
</article>""")
    ciclo = feitos["ciclo"]
    cartoes.append(f"""<article class="demo">
  <span class="tipo">análise · dashboard · decisão</span>
  <h3>O ciclo completo</h3>
  <p>A análise feita no plugin analise-dados vira dashboard e documento de decisão. Cada número do texto é
  conferido contra os achados calculados: {e(str(ciclo.get("decisao", {}).get("verificacao", "verificado")))}.</p>
  <div class="links"><a class="principal" href="ciclo/">Abrir o dashboard</a><a href="ciclo/decisao.html">Ler o documento de decisão</a></div>
</article>""")
    sem_link = pbix["comparativo"]["via"] is None
    cartoes.append(f"""<article class="demo destaque">
  <span class="tipo">Power BI · .pbix em importação</span>
  <h3>Um relatório do Power BI convertido</h3>
  <p>O .pbix fictício foi lido fora do Power BI: tabelas extraídas, medidas DAX traduzidas para a camada de métricas e
  testadas contra o motor DAX, página remontada bloco a bloco. O que não traduz fica de fora, com o motivo.</p>
  <ul class="numeros">
    <li>{r["tabelas_iguais"]} de {r["tabelas"]} tabelas com linhas idênticas</li>
    <li>{r["traduzidas"]} de {r["medidas"]} medidas traduzidas</li>
    <li>{r["validadas"]} de {r["traduzidas"]} batem com o Power BI</li>
    <li>{r["visuais_convertidos"]} de {r["visuais_com_dado"]} visuais com dado convertidos</li>
  </ul>
  <div class="links"><a class="principal" href="power-bi/{e(primeira)}">Abrir a página convertida</a>
  <a href="power-bi/">{"Original e convertido, visual a visual" if not sem_link else "Visual a visual (o original entra quando for publicado)"}</a></div>
</article>""")
    gerado = datetime.now().strftime("%d/%m/%Y")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>bi-html</title>
<meta name="description" content="Dashboards e documentos de decisão em HTML em que nenhum número sai do modelo de linguagem.">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&amp;family=IBM+Plex+Sans:wght@400;500;600&amp;display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="miolo">
  <header class="abertura">
    <span class="olho">bi-html · plugin do Claude Code</span>
    <h1>Do dado ao BI, com cada número rastreável</h1>
    <p class="tese">Um plugin que fecha o ciclo planilha, análise, dashboard e documento de decisão dentro do Claude Code.
    O Claude desenha a página e escreve o texto; os valores vêm de uma camada de métricas determinística, com a definição
    de cada número ao lado dele.</p>
    <p class="regra">Nenhum número sai do modelo de linguagem.</p>
  </header>
  <section>
    <h2>Demonstrações</h2>
    <div class="grade">
{chr(10).join(cartoes)}
    </div>
  </section>
  <section>
    <h2>Como um número chega ao dashboard</h2>
    <ol class="etapas">
      <li><h3>Planilha ou .pbix</h3><p>O arquivo original fica guardado com hash; tipos, datas no formato brasileiro e dados pessoais são conferidos.</p></li>
      <li><h3>Camada de métricas</h3><p>Cada métrica tem definição escrita e linhagem; só ela calcula, no DuckDB.</p></li>
      <li><h3>Spec sem números</h3><p>O Claude escreve a spec do dashboard: blocos e métricas por id, sem valores. Um schema impede algarismos no texto.</p></li>
      <li><h3>HTML que só desenha</h3><p>O renderizador embute os números já calculados; cada bloco mostra "Como calculamos" e a tabela de apoio.</p></li>
    </ol>
  </section>
  <footer>
    <p>Todos os dados destas demonstrações são fictícios, gerados com semente fixa.</p>
    <p>Gerado em {gerado} pelo <code>vitrine/construir.py</code>.</p>
  </footer>
</div>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--link-power-bi", default=None, help="link de Publicar na Web do vendas.pbix fictício")
    args = ap.parse_args()
    feitos = montar_exemplos()
    pbix = converter_pbix(args.link_power_bi)
    copiar(feitos, pbix)
    (DOCS / "index.html").write_text(pagina_inicial(feitos, pbix), encoding="utf-8")
    total = sum(p.stat().st_size for p in DOCS.rglob("*") if p.is_file())
    print(f"vitrine: {DOCS.relative_to(RAIZ)}/ · {total / 1024:.0f} KB")


if __name__ == "__main__":
    main()
