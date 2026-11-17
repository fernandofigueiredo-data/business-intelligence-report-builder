"""
Documento de decisão em HTML.

Só renderiza depois que o verificador aprova o `decisao/documento.md` (todo
número rastreado). O texto é do Claude; o apêndice de método é gerado aqui,
sem passar pelo modelo de linguagem: origem dos dados (com hash), período,
qualidade, definição de cada métrica citada, a reprodução da conclusão da
análise e o resultado da verificação dos números.

Formato pensado para caber em até duas páginas A4 na impressão.
Gera `saidas/bi/decisao.html` e `saidas/bi/decisao.artifact.html`.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .achados import ler as ler_achados
from .conclusao import ARQUIVO as ARQUIVO_REPRODUCAO
from .design import css as css_tokens
from .ingestao import ler_manifesto
from .render import SAIDA, _link_fontes, documento as documento_completo
from .verificador import ErroDeDocumento, ler_documento, separar, verificar

CSS = r"""
body { margin: 0; background: var(--background); color: var(--foreground); font-family: var(--font-sans);
  font-size: 15px; line-height: 1.55; }
.folha { max-width: 760px; margin: 0 auto; padding-block: 32px 56px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 18px; }
.olho { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; color: var(--muted-foreground); letter-spacing: .05em;
  text-transform: uppercase; align-items: center; }
.chip { display: inline-flex; padding: 1px 9px; border-radius: 999px; border: var(--border-width) solid var(--border);
  font-size: 12px; text-transform: none; letter-spacing: 0; }
.chip.positivo { color: var(--positivo); border-color: currentColor; }
.chip.alerta { color: var(--alerta); border-color: currentColor; }
h1 { font-family: var(--font-titulo); font-size: clamp(26px, 4.4vw, 34px); line-height: 1.15; margin: 0; text-wrap: balance; }
.pergunta { margin: 0; color: var(--muted-foreground); }
.resposta { margin: 0; font-size: 18px; line-height: 1.5; padding: 14px 16px; background: var(--muted);
  border-radius: var(--radius); }
h2 { font-family: var(--font-titulo); font-size: 17px; margin: 8px 0 0; padding-top: 10px; border-top: 1px solid var(--border); }
.achado { display: flex; flex-direction: column; gap: 4px; break-inside: avoid; }
.achado h3 { font-size: 15.5px; margin: 0; line-height: 1.35; text-wrap: balance; }
.achado p, .secao p { margin: 0; }
ul { margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; }
.ref { display: inline-block; font-family: var(--font-mono); font-size: 11px; padding: 0 5px; border-radius: 4px;
  background: var(--muted); color: var(--muted-foreground); vertical-align: 1px; white-space: nowrap; }
.num { font-variant-numeric: tabular-nums; }
.apendice { font-size: 13px; color: var(--muted-foreground); display: flex; flex-direction: column; gap: 10px; }
.apendice h2 { color: var(--foreground); }
.apendice h3 { font-size: 13px; color: var(--foreground); margin: 4px 0 0; }
.apendice table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.apendice th, .apendice td { text-align: left; padding: 5px 6px; border-bottom: 1px solid var(--border); vertical-align: top; }
.apendice th { font-weight: 600; color: var(--foreground); }
.apendice code { font-family: var(--font-mono); font-size: 11.5px; overflow-wrap: anywhere; }
.tabela-rolagem { overflow-x: auto; }
.estado-reproduzido { color: var(--positivo); font-weight: 600; }
.estado-nao_reproduzido { color: var(--negativo); font-weight: 600; }
@page { size: A4; margin: 14mm 15mm; }
@media print {
  :root { color-scheme: light; }
  body { font-size: 9.4pt; line-height: 1.3; background: #fff; color: #111; }
  .folha { max-width: none; padding: 0; gap: 5px; }
  .olho { font-size: 7.5pt; } .chip { font-size: 7.5pt; }
  h1 { font-size: 16pt; } h2 { font-size: 10.5pt; margin-top: 2px; padding-top: 4px; }
  .pergunta { font-size: 9.4pt; }
  .resposta { font-size: 10pt; padding: 5px 8px; }
  .achado { gap: 1px; } .achado h3 { font-size: 9.8pt; } ul { gap: 1px; padding-left: 16px; }
  .ref { font-size: 7pt; }
  .apendice { font-size: 7.6pt; gap: 3px; } .apendice table { font-size: 7.4pt; } .apendice h3 { font-size: 8pt; }
  .apendice th, .apendice td { padding: 1px 3px; }
}
"""


def _inline(texto: str, titulos: dict[str, str]) -> str:
    """Markdown de linha (negrito, itálico, links https e referências [A3]) para HTML seguro."""
    e = html.escape(texto).replace("R$ ", "R$\u00a0")
    e = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e)
    e = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", e)
    e = re.sub(r"\[([^\]]+)\]\((https://[^)\s]+)\)", r'<a href="\2">\1</a>', e)
    e = re.sub(r"\[([AC]\d+)\]", lambda m: f'<span class="ref" title="{html.escape(titulos.get(m.group(1), ""))}">{m.group(1)}</span>', e)
    return e


def _blocos(texto: str, titulos: dict[str, str]) -> str:
    saida, lista = [], []
    for linha in texto.splitlines() + [""]:
        item = re.match(r"^\s*[-*]\s+(.*)$", linha)
        if item:
            lista.append(f"<li>{_inline(item.group(1), titulos)}</li>")
            continue
        if lista:
            saida.append("<ul>" + "".join(lista) + "</ul>")
            lista = []
        if linha.strip():
            saida.append(f"<p>{_inline(linha.strip(), titulos)}</p>")
    return "\n".join(saida)


def _apendice(projeto: Path, achados: dict, verificacao: dict, citados: set[str]) -> str:
    e = html.escape
    manifesto = ler_manifesto(projeto)
    usados = sorted({m for a in achados["achados"] if a["id"] in citados for m in a["metricas"]})
    fonte = next(iter((manifesto.get("metricas") or {}).values()), {}).get("fonte", {})
    cobertura = next((a for a in achados["achados"] if a["tipo"] == "cobertura"), None)
    linhas = []
    linhas.append("<h2>Apêndice de método</h2>")
    origem = (f"<p>Fonte: <code>{e(fonte.get('arquivo', '—'))}</code> · sha256 <code>{e((fonte.get('sha256') or '')[:16])}…</code>"
              + (f" · {e(cobertura['formatado']['registros'])} registros de {e(cobertura['formatado'].get('inicio', '—'))} "
                 f"a {e(cobertura['formatado'].get('fim', '—'))}" if cobertura else "")
              + f" · achados calculados em {e(achados['gerado_em'][:10])}.</p>")
    linhas.append(origem)
    if usados:
        linhas.append("<h3>Como cada métrica citada é calculada</h3><div class=\"tabela-rolagem\"><table>"
                      "<tr><th>Métrica</th><th>Definição</th></tr>"
                      + "".join(f"<tr><td>{e(achados['definicoes'][m]['descricao'])}</td><td>{e(achados['definicoes'][m]['definicao'])}</td></tr>"
                                for m in usados if m in achados["definicoes"])
                      + "</table></div>")
    if (projeto / ARQUIVO_REPRODUCAO).is_file():
        rep = json.loads((projeto / ARQUIVO_REPRODUCAO).read_text(encoding="utf-8"))
        nomes = {"reproduzido": "reproduzido", "nao_reproduzido": "não reproduzido", "sem_numero": "sem número"}
        linhas.append("<h3>Conclusão da análise, reproduzida pela camada de métricas</h3><div class=\"tabela-rolagem\"><table>"
                      "<tr><th>Item</th><th>O que a análise afirmou</th><th>Estado</th><th>Calculado agora</th></tr>"
                      + "".join(
                          f"<tr><td>C{i['item']}</td><td>{_inline(i['texto'], {})}</td>"
                          f"<td class=\"estado-{i['estado']}\">{nomes[i['estado']]}</td>"
                          f"<td class=\"num\">{e(', '.join(o['formatado'] for v in i['verificacoes'] for o in v.get('observado', [])) or '—')}</td></tr>"
                          for i in rep["itens"])
                      + "</table></div>")
    qualidade = []
    for nome, t in manifesto.get("tabelas", {}).items():
        if t.get("qualidade") and (projeto / t["qualidade"]).is_file():
            rel = json.loads((projeto / t["qualidade"]).read_text(encoding="utf-8"))
            qualidade += rel.get("alertas", []) + rel.get("bloqueios", [])
    if (projeto / "contexto.md").is_file():
        from .contrato import checar

        c = checar(projeto)
        qualidade += [f"{i['arquivo']}: {i['detalhe']}" for i in c["itens"] if i["estado"] != "ok"]
        qualidade += [f"tratamento: {d}" for d in (c.get("contexto") or {}).get("decisoes_tratamento", [])]
    if qualidade:
        linhas.append("<h3>Qualidade e tratamento dos dados</h3><ul>" + "".join(f"<li>{_inline(q, {})}</li>" for q in qualidade) + "</ul>")
    linhas.append(f"<p>Verificação dos números: {verificacao['rastreados']} de {verificacao['total_de_numeros']} números do texto "
                  "vêm de um valor calculado pela camada de métricas (achados ou conclusão reproduzida).</p>")
    return "\n".join(linhas)


def renderizar_documento(projeto: Path) -> dict:
    projeto = Path(projeto)
    verificacao = verificar(projeto)
    if not verificacao["ok"]:
        raise ErroDeDocumento("o documento não passou na verificação", verificacao["problemas"])
    doc = separar(ler_documento(projeto))
    achados = ler_achados(projeto)
    titulos = {a["id"]: a["titulo"] for a in achados["achados"]}
    if (projeto / ARQUIVO_REPRODUCAO).is_file():
        rep = json.loads((projeto / ARQUIVO_REPRODUCAO).read_text(encoding="utf-8"))
        titulos |= {f"C{i['item']}": i["texto"] for i in rep["itens"]}
    citados = {r for a in doc["achados"] for r in a["refs"]} | set(re.findall(r"\[(A\d+)\]", ler_documento(projeto)))
    tokens_path = projeto / "design" / "tokens.json"
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    spec_path = projeto / "dashboard" / "spec.json"
    origem = json.loads(spec_path.read_text(encoding="utf-8")).get("origem") if spec_path.is_file() else None
    e = html.escape
    chip = ('<span class="chip positivo">Análise revisada antes da decisão</span>' if origem == "analise" else
            '<span class="chip alerta">Sem análise prévia</span>')
    periodo = achados.get("periodo") or {}
    cob = next((a for a in achados["achados"] if a["tipo"] == "cobertura"), None)
    rotulo = (f"{periodo['inicio'][8:10]}/{periodo['inicio'][5:7]}/{periodo['inicio'][:4]} a "
              f"{periodo['fim'][8:10]}/{periodo['fim'][5:7]}/{periodo['fim'][:4]}") if periodo.get("inicio") else (
              f"{cob['formatado'].get('inicio')} a {cob['formatado'].get('fim')}" if cob else "")
    secoes = doc["secoes"]
    corpo_achados = "\n".join(
        f'<section class="achado"><h3>{_inline(a["titulo"], titulos)}</h3>{_blocos(a["texto"], titulos)}</section>'
        for a in doc["achados"])
    frag = f"""<title>{e(doc["titulo"])}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<meta name="description" content="{e(doc["pergunta"])}">
{_link_fontes(tokens["tipografia"])}
<style>
{css_tokens(tokens)}{CSS}
</style>
<article class="folha">
  <div class="olho"><span>Documento de decisão</span><span class="chip">{e(rotulo)}</span>{chip}</div>
  <h1>{e(doc["titulo"])}</h1>
  <p class="pergunta"><strong>Pergunta:</strong> {_inline(doc["pergunta"], titulos)}</p>
  {f'<p class="pergunta"><strong>Decisão:</strong> {_inline(doc["decisao"], titulos)}</p>' if doc.get("decisao") else ""}
  <p class="resposta">{_inline(" ".join(secoes["Resposta"].split()), titulos)}</p>
  <h2>Achados</h2>
  {corpo_achados}
  <h2>O que os dados não permitem afirmar</h2>
  <div class="secao">{_blocos(secoes["O que os dados não permitem afirmar"], titulos)}</div>
  <h2>Opções de decisão</h2>
  <div class="secao">{_blocos(secoes["Opções de decisão"], titulos)}</div>
  <h2>Próximas perguntas</h2>
  <div class="secao">{_blocos(secoes["Próximas perguntas"], titulos)}</div>
  <section class="apendice">{_apendice(projeto, achados, verificacao, citados)}</section>
</article>
"""
    pasta = projeto / SAIDA
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "decisao.artifact.html").write_text(frag, encoding="utf-8")
    (pasta / "decisao.html").write_text(documento_completo(frag), encoding="utf-8")
    palavras = len(re.findall(r"\w+", ler_documento(projeto)))
    return {"html": str(SAIDA / "decisao.html"), "artifact": str(SAIDA / "decisao.artifact.html"),
            "titulo": doc["titulo"], "palavras": palavras,
            "verificacao": f"{verificacao['rastreados']}/{verificacao['total_de_numeros']} números rastreados"}
