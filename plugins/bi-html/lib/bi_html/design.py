"""
Design do dashboard: tokens, estilos base, importação de design system e
inferência de domínio.

Saída: `design/tokens.json` e `design/tokens.css` na pasta do projeto. Os
tokens seguem os nomes semânticos do shadcn/ui (`--background`, `--primary`,
`--chart-1`…), acrescidos de estados (`--positivo`, `--negativo`, `--alerta`),
nos modos claro e escuro. Antes de gravar, todo par de cor usado como texto é
conferido contra o critério AA da WCAG (4,5:1) e toda cor de gráfico contra o
fundo do cartão (3:1, componente não textual); o que não passa é ajustado só na
luminosidade, e cada ajuste fica registrado.

Duas entradas:
- **enviado**: DESIGN.md (formato aberto do Google Labs), tema JSON do Power BI,
  CSS com variáveis, tokens.json ou o `estilos/design-system.md` do analise-dados;
- **inferido**: o domínio dos dados (marketing, vendas, financeiro…) escolhe dois
  estilos base com acento e uma seleção de blocos típicos.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import cores
from .cores import ErroDeCor
from .ingestao import MANIFESTO, ErroDeLeitura, ler_manifesto

PASTA = Path("design")
VERSAO = "0.1"
PAPEIS = ("background", "foreground", "card", "card_foreground", "muted", "muted_foreground", "border",
          "primary", "primary_foreground", "positivo", "negativo", "alerta")
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]
PILHA_SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
PILHA_MONO = "ui-monospace, 'SFMono-Regular', Menlo, monospace"

# Pares conferidos: (papel da frente, papel do fundo, razão mínima)
PARES_TEXTO = [("foreground", "background", 4.5), ("card_foreground", "card", 4.5),
               ("muted_foreground", "card", 4.5), ("muted_foreground", "background", 4.5),
               ("primary_foreground", "primary", 4.5), ("primary", "card", 3.0),
               ("positivo", "card", 4.5), ("negativo", "card", 4.5), ("alerta", "card", 4.5)]
MINIMO_GRAFICO = 3.0


class ErroDeDesign(ErroDeLeitura):
    pass


# ---------------------------------------------------------------- estilos base

ESTILOS = {
    "claro": {"descricao": "Fundo branco, texto quase preto, um acento", "modo": "claro",
              "cores": {"background": "#ffffff", "foreground": "#0f172a", "primary": "#2563eb"},
              "fonte": "Inter", "raio": "10px", "borda": "1px"},
    "escuro": {"descricao": "Fundo escuro azulado, para telas e apresentações", "modo": "escuro",
               "cores": {"background": "#0b1120", "foreground": "#e2e8f0", "primary": "#60a5fa"},
               "fonte": "Inter", "raio": "10px", "borda": "1px"},
    "corporativo": {"descricao": "Sóbrio, azul-marinho, cantos discretos", "modo": "claro",
                    "cores": {"background": "#f8fafc", "foreground": "#0f172a", "primary": "#1e3a5f",
                              "card": "#ffffff"},
                    "fonte": "IBM Plex Sans", "raio": "4px", "borda": "1px"},
    "alto_contraste": {"descricao": "Preto e branco com bordas fortes, para impressão e acessibilidade",
                       "modo": "claro",
                       "cores": {"background": "#ffffff", "foreground": "#000000", "primary": "#000000",
                                 "border": "#000000", "muted_foreground": "#333333"},
                       "grafico": ["#000000", "#0057b8", "#c1121f", "#2a7d2e", "#6b3fa0"],
                       "fonte": "Atkinson Hyperlegible", "raio": "2px", "borda": "2px"},
}
ACENTOS = {"marketing": ("violeta", "#7c3aed"), "vendas": ("verde-azulado", "#0f766e"),
           "financeiro": ("azul-marinho", "#1e3a5f"), "operacoes": ("laranja", "#c2410c"),
           "rh": ("magenta", "#be185d"), "outro": ("azul", "#2563eb")}
PROPOSTAS = {"marketing": [("claro", True), ("escuro", True)],
             "vendas": [("claro", True), ("corporativo", False)],
             "financeiro": [("corporativo", False), ("alto_contraste", False)],
             "operacoes": [("claro", True), ("corporativo", False)],
             "rh": [("claro", True), ("corporativo", False)],
             "outro": [("claro", True), ("escuro", True)]}


# ---------------------------------------------------------------- completar e conferir

def completar(parcial: dict, modo: str | None = None) -> dict:
    """Paleta completa de um modo a partir das cores que vieram (o resto é derivado)."""
    p = {k: cores.normalizar(v) for k, v in parcial.items() if k in PAPEIS and v}
    fundo = p.get("background")
    if modo is None:
        modo = "escuro" if fundo and cores.eh_escuro(fundo) else "claro"
    escuro = modo == "escuro"
    fundo = fundo or ("#0b1120" if escuro else "#ffffff")
    frente = p.get("foreground") or ("#e2e8f0" if escuro else "#0f172a")
    primaria = p.get("primary") or ("#60a5fa" if escuro else "#2563eb")
    card = p.get("card") or (cores.misturar(fundo, frente, 0.05) if escuro else fundo)
    completa = {
        "background": fundo,
        "foreground": frente,
        "card": card,
        "card_foreground": p.get("card_foreground") or frente,
        "muted": p.get("muted") or cores.misturar(card, frente, 0.06),
        "muted_foreground": p.get("muted_foreground") or cores.misturar(frente, card, 0.38),
        "border": p.get("border") or cores.misturar(card, frente, 0.14),
        "primary": primaria,
        "primary_foreground": p.get("primary_foreground") or cores.melhor_texto_sobre(primaria),
        "positivo": p.get("positivo") or ("#4ade80" if escuro else "#15803d"),
        "negativo": p.get("negativo") or ("#f87171" if escuro else "#b91c1c"),
        "alerta": p.get("alerta") or ("#fbbf24" if escuro else "#b45309"),
    }
    grafico = [cores.normalizar(c) for c in parcial.get("grafico") or []]
    if not grafico:
        grafico = [primaria] + [c for c in OKABE_ITO if c.lower() != primaria.lower()]
    reserva = [c for c in OKABE_ITO if c.lower() not in {g.lower() for g in grafico}]
    completa["grafico"] = [cores.normalizar(c) for c in (grafico + reserva)[:5]]
    return completa


def conferir(paleta: dict, modo: str) -> tuple[dict, list[dict], list[dict]]:
    """Garante AA em todos os pares; devolve a paleta ajustada, os ajustes e o relatório de contraste."""
    p = dict(paleta)
    p["grafico"] = list(paleta["grafico"])
    ajustes, relatorio = [], []
    for frente, fundo, minimo in PARES_TEXTO:
        antes = p[frente]
        if frente == "primary_foreground" and cores.contraste(antes, p[fundo]) < minimo:
            depois = cores.melhor_texto_sobre(p[fundo])
            depois = depois if cores.contraste(depois, p[fundo]) >= minimo else cores.ajustar_contraste(antes, p[fundo], minimo)
        else:
            depois = cores.ajustar_contraste(antes, p[fundo], minimo)
        if depois != antes:
            ajustes.append({"modo": modo, "papel": frente, "sobre": fundo, "antes": antes, "depois": depois,
                            "contraste_antes": round(cores.contraste(antes, p[fundo]), 2)})
            p[frente] = depois
        relatorio.append({"modo": modo, "frente": frente, "fundo": fundo, "minimo": minimo,
                          "contraste": round(cores.contraste(p[frente], p[fundo]), 2)})
    for i, cor in enumerate(p["grafico"]):
        nova = cores.ajustar_contraste(cor, p["card"], MINIMO_GRAFICO)
        if nova != cor:
            ajustes.append({"modo": modo, "papel": f"grafico_{i + 1}", "sobre": "card", "antes": cor, "depois": nova,
                            "contraste_antes": round(cores.contraste(cor, p["card"]), 2)})
            p["grafico"][i] = nova
        relatorio.append({"modo": modo, "frente": f"grafico_{i + 1}", "fundo": "card", "minimo": MINIMO_GRAFICO,
                          "contraste": round(cores.contraste(p["grafico"][i], p["card"]), 2)})
    return p, ajustes, relatorio


def modo_oposto(paleta: dict, modo_origem: str) -> dict:
    """Deriva o outro modo mantendo a identidade (matiz da primária e das cores de gráfico)."""
    primaria = paleta["primary"]
    _, _, H = cores.rgb_para_oklch(cores.para_rgb(primaria))
    if modo_origem == "claro":
        fundo = cores.hex_de(cores.oklch_para_rgb(0.18, 0.02, H))
        return completar({"background": fundo, "card": cores.hex_de(cores.oklch_para_rgb(0.22, 0.02, H)),
                          "foreground": "#e5e7eb", "primary": cores.com_luminosidade(primaria, 0.72),
                          "grafico": [cores.com_luminosidade(c, 0.72) for c in paleta["grafico"]]}, "escuro")
    return completar({"background": "#ffffff", "foreground": "#0f172a",
                      "primary": cores.com_luminosidade(primaria, 0.5),
                      "grafico": [cores.com_luminosidade(c, 0.55) for c in paleta["grafico"]]}, "claro")


def montar_tokens(parcial: dict, nome: str, fonte: str, origem: dict, tipografia: dict | None = None,
                  forma: dict | None = None) -> dict:
    modo = "escuro" if parcial.get("background") and cores.eh_escuro(cores.normalizar(parcial["background"])) else "claro"
    base = completar(parcial, modo)
    outro = modo_oposto(base, modo)
    claro, escuro = (base, outro) if modo == "claro" else (outro, base)
    claro, aj1, rel1 = conferir(claro, "claro")
    escuro, aj2, rel2 = conferir(escuro, "escuro")
    tipografia = tipografia or {}
    forma = forma or {}
    return {
        "versao": VERSAO,
        "nome": nome,
        "fonte": fonte,
        "origem": origem,
        "modo_padrao": modo,
        "claro": claro,
        "escuro": escuro,
        "tipografia": {"sans": tipografia.get("sans") or "Inter", "titulo": tipografia.get("titulo") or tipografia.get("sans") or "Inter",
                       "mono": tipografia.get("mono") or "JetBrains Mono"},
        "forma": {"raio": forma.get("raio") or "10px", "borda": forma.get("borda") or "1px"},
        "ajustes_de_contraste": aj1 + aj2,
        "contraste": rel1 + rel2,
        "aa": all(r["contraste"] >= r["minimo"] for r in rel1 + rel2),
    }


# ---------------------------------------------------------------- CSS

def _vars(paleta: dict, recuo: str = "  ") -> list[str]:
    linhas = [f"{recuo}--{papel.replace('_', '-')}: {paleta[papel]};" for papel in PAPEIS]
    return linhas + [f"{recuo}--chart-{i + 1}: {c};" for i, c in enumerate(paleta["grafico"])]


def css(tokens: dict) -> str:
    """CSS de tokens no contrato de tema dos Artifacts.

    O modo padrão fica em :root; o outro entra pela preferência do sistema, guardado por
    :root:not([data-theme=...]), e de novo por :root[data-theme=...], para a escolha explícita
    do leitor vencer nos dois sentidos.
    """
    t, f = tokens["tipografia"], tokens["forma"]
    padrao = tokens["modo_padrao"]
    outro = "escuro" if padrao == "claro" else "claro"
    tema = {"claro": "light", "escuro": "dark"}
    linhas = [f"/* Tokens do bi-html: {tokens['nome']} ({tokens['fonte']}). Gerado; não edite à mão. */",
              ":root {", *_vars(tokens[padrao]),
              f"  --font-sans: '{t['sans']}', {PILHA_SANS};",
              f"  --font-titulo: '{t['titulo']}', {PILHA_SANS};",
              f"  --font-mono: '{t['mono']}', {PILHA_MONO};",
              f"  --radius: {f['raio']};",
              f"  --border-width: {f['borda']};",
              f"  color-scheme: {tema[padrao]};",
              "}",
              f"@media (prefers-color-scheme: {tema[outro]}) {{",
              f"  :root:not([data-theme=\"{tema[padrao]}\"]) {{", *_vars(tokens[outro], "    "),
              f"    color-scheme: {tema[outro]};", "  }", "}",
              f":root[data-theme=\"{tema[outro]}\"] {{", *_vars(tokens[outro]), f"  color-scheme: {tema[outro]};", "}"]
    return "\n".join(linhas) + "\n"


def gravar(projeto: Path, tokens: dict) -> dict:
    projeto = Path(projeto)
    pasta = projeto / PASTA
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tokens.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (pasta / "tokens.css").write_text(css(tokens), encoding="utf-8")
    manifesto = ler_manifesto(projeto)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifesto["design"] = {"nome": tokens["nome"], "fonte": tokens["fonte"], "origem": tokens["origem"],
                           "aa": tokens["aa"], "ajustes": len(tokens["ajustes_de_contraste"]), "gravado_em": agora}
    manifesto["eventos"].append({"quando": agora, "evento": "design", "nome": tokens["nome"], "fonte": tokens["fonte"]})
    (projeto / MANIFESTO).parent.mkdir(parents=True, exist_ok=True)
    (projeto / MANIFESTO).write_text(json.dumps(manifesto, ensure_ascii=False, indent=2, default=str) + "\n",
                                     encoding="utf-8")
    return {"tokens": str(PASTA / "tokens.json"), "css": str(PASTA / "tokens.css"), "nome": tokens["nome"],
            "fonte": tokens["fonte"], "aa": tokens["aa"], "ajustes_de_contraste": tokens["ajustes_de_contraste"],
            "modo_padrao": tokens["modo_padrao"], "claro": tokens["claro"], "escuro": tokens["escuro"],
            "tipografia": tokens["tipografia"], "forma": tokens["forma"]}


# ---------------------------------------------------------------- estilos

def tokens_de_estilo(estilo: str, dominio: str | None = None, com_acento: bool = True) -> dict:
    if estilo not in ESTILOS:
        raise ErroDeDesign(f"estilo {estilo!r} não existe", [f"estilos: {', '.join(ESTILOS)}"])
    e = ESTILOS[estilo]
    parcial = dict(e["cores"])
    nome = estilo
    if dominio and com_acento:
        rotulo, acento = ACENTOS.get(dominio, ACENTOS["outro"])
        parcial["primary"] = acento if e["modo"] == "claro" else cores.com_luminosidade(acento, 0.72)
        nome = f"{estilo} com acento {rotulo}"
    if "grafico" in e:
        parcial["grafico"] = e["grafico"]
    return montar_tokens(parcial, nome, "inferido" if dominio else "padrao",
                         {"estilo": estilo, "dominio": dominio}, {"sans": e["fonte"], "titulo": e["fonte"]},
                         {"raio": e["raio"], "borda": e["borda"]})


# ---------------------------------------------------------------- importação

def _yaml_frontmatter(texto: str) -> dict:
    import yaml

    blocos = []
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", texto, re.DOTALL)
    if m:
        blocos.append(m.group(1))
    blocos += re.findall(r"```ya?ml\s*\n(.*?)```", texto, re.DOTALL)
    dados = {}
    for b in blocos:
        try:
            parte = yaml.safe_load(b)
        except yaml.YAMLError:
            raise ErroDeDesign("o DESIGN.md tem YAML inválido", ["confira o bloco entre as linhas ---"]) from None
        if isinstance(parte, dict):
            dados.update(parte)
    return dados


SINONIMOS = {
    "background": ("background", "surface", "canvas", "neutral", "paper", "bg"),
    "foreground": ("on-surface", "on-background", "ink", "text", "foreground", "on-neutral", "on-canvas"),
    "card": ("surface-container", "card", "surface-raised", "panel"),
    "muted_foreground": ("on-surface-variant", "muted", "text-secondary", "ink-muted", "secondary-text", "subtle"),
    "border": ("outline", "border", "hairline", "divider", "stroke"),
    "primary": ("primary", "brand", "accent"),
    "primary_foreground": ("on-primary", "on-brand", "on-accent"),
    "positivo": ("success", "positive", "good"),
    "negativo": ("error", "danger", "negative", "bad", "destructive"),
    "alerta": ("warning", "caution"),
}


def _de_design_md(texto: str) -> tuple[dict, dict, dict, str]:
    dados = _yaml_frontmatter(texto)
    paleta_bruta = dados.get("colors") or {}
    if not isinstance(paleta_bruta, dict) or "primary" not in paleta_bruta:
        raise ErroDeDesign("o DESIGN.md não define colors.primary",
                           ["o formato exige pelo menos a cor primary no bloco YAML do topo"])
    validas = {}
    for k, v in paleta_bruta.items():
        try:
            validas[str(k).lower()] = cores.normalizar(str(v))
        except ErroDeCor:
            continue
    parcial, usados = {}, set()
    for papel, nomes in SINONIMOS.items():
        for n in nomes:
            if n in validas and papel not in parcial:
                parcial[papel] = validas[n]
                usados.add(n)
                break
    # Cores de gráfico: a primária, depois secondary/tertiary e as demais cores saturadas (croma
    # alto) que não têm papel estrutural; tons neutros de fundo e texto ficam de fora.
    extras = [c for n, c in validas.items() if n in ("secondary", "tertiary")]
    extras += [c for n, c in validas.items() if n not in usados and not n.startswith("on-")
               and n not in ("secondary", "tertiary") and cores.rgb_para_oklch(cores.para_rgb(c))[1] >= 0.08]
    unicas = []
    for c in [parcial["primary"]] + extras:
        if c not in unicas:
            unicas.append(c)
    parcial["grafico"] = unicas[:5]
    tipos = dados.get("typography") or {}
    def familia(chaves):
        for k, t in tipos.items():
            if isinstance(t, dict) and t.get("fontFamily") and any(c in str(k).lower() for c in chaves):
                return str(t["fontFamily"]).split(",")[0].strip("'\" ")
        return None
    tipografia = {"sans": familia(("body", "text", "paragraph")) or familia(("",)),
                  "titulo": familia(("h1", "display", "headline", "title", "heading"))}
    raios = dados.get("rounded") or {}
    forma = {"raio": str(raios.get("md") or raios.get("sm") or next(iter(raios.values()), "") or "") or None}
    return parcial, tipografia, forma, str(dados.get("name") or "DESIGN.md")


def _de_tema_powerbi(dados: dict) -> tuple[dict, dict, dict, str]:
    parcial = {
        "background": dados.get("background"),
        "foreground": dados.get("foreground") or dados.get("firstLevelElements"),
        "muted_foreground": dados.get("secondLevelElements") or dados.get("foregroundNeutralSecondary"),
        "border": dados.get("thirdLevelElements") or dados.get("backgroundLight"),
        "primary": dados.get("tableAccent") or (dados.get("dataColors") or [None])[0],
        "positivo": dados.get("good"),
        "negativo": dados.get("bad"),
        "grafico": dados.get("dataColors") or [],
    }
    if not parcial["primary"]:
        raise ErroDeDesign("o tema do Power BI não tem tableAccent nem dataColors", ["sem cor de destaque, não há o que aplicar"])
    fonte = (((dados.get("textClasses") or {}).get("label") or {}).get("fontFace"))
    return {k: v for k, v in parcial.items() if v}, {"sans": fonte, "titulo": fonte}, {}, str(dados.get("name") or "tema do Power BI")


def _de_css(texto: str) -> tuple[dict, dict, dict, str]:
    blocos = re.findall(r"(:root|\.dark|\[data-[^\]]+\])\s*\{([^}]*)\}", texto)
    if not blocos:
        raise ErroDeDesign("não encontrei variáveis CSS (:root { --nome: valor; })")
    variaveis = dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+);", blocos[0][1]))
    parcial = {}
    for nome, valor in variaveis.items():
        papel = nome.replace("-", "_")
        if papel in PAPEIS:
            parcial[papel] = valor.strip()
    if "destructive" in variaveis:
        parcial.setdefault("negativo", variaveis["destructive"].strip())
    graf = [variaveis[f"chart-{i}"].strip() for i in range(1, 6) if f"chart-{i}" in variaveis]
    if graf:
        parcial["grafico"] = graf
    if "primary" not in parcial:
        raise ErroDeDesign("o CSS não define --primary")
    raio = variaveis.get("radius", "").strip() or None
    return parcial, {}, {"raio": raio}, "CSS enviado"


def _de_design_system_analise(texto: str) -> tuple[dict, dict, dict, str]:
    """`estilos/design-system.md` do analise-dados: tabela Papel | Cor | Hex e lista categórica."""
    papeis = {}
    for papel, hx in re.findall(r"^\|\s*([^|]+?)\s*\|[^|]*\|\s*`?(#[0-9A-Fa-f]{3,8})`?\s*\|", texto, re.MULTILINE):
        papeis[papel.lower()] = hx
    primaria = next((h for p, h in papeis.items() if "primária" in p or "primaria" in p), None)
    if not primaria:
        raise ErroDeDesign("o design-system.md não tem a cor primária na tabela de paleta")
    secao = re.search(r"categ[óo]rica[^\n]*\n+(.*?)(\n##|\Z)", texto, re.DOTALL | re.IGNORECASE)
    categorica = re.findall(r"#[0-9A-Fa-f]{6}", secao.group(1)) if secao else []
    destaque = next((h for p, h in papeis.items() if "destaque" in p), None)
    grafico = [primaria] + ([destaque] if destaque else []) + [c for c in categorica if c not in (primaria, destaque)]
    return {"primary": primaria, "grafico": grafico}, {}, {}, "design-system.md do analise-dados"


def importar(projeto: Path, caminho: str) -> dict:
    """Lê um design system enviado e grava design/tokens.json e tokens.css com contraste AA."""
    projeto = Path(projeto)
    arquivo = Path(caminho).expanduser()
    if not arquivo.is_absolute():
        arquivo = projeto / arquivo
    if not arquivo.is_file():
        raise ErroDeDesign(f"arquivo não encontrado: {caminho}")
    sufixo = arquivo.suffix.lower()
    if sufixo not in (".json", ".css", ".md", ".markdown"):
        raise ErroDeDesign(f"formato {sufixo or 'sem extensão'} não suportado",
                           ["envie DESIGN.md, tema JSON do Power BI, CSS ou tokens.json; para imagem ou PDF de "
                            "guia de marca, o Claude extrai as cores para um DESIGN.md primeiro"])
    try:
        texto = arquivo.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise ErroDeDesign(f"{arquivo.name} não é um arquivo de texto UTF-8") from None
    try:
        if sufixo == ".json":
            dados = json.loads(texto)
            if isinstance(dados, dict) and "claro" in dados and "escuro" in dados:
                parcial, tip, forma, nome = dados["claro"], dados.get("tipografia", {}), dados.get("forma", {}), dados.get("nome", "tokens")
                formato = "tokens.json"
            elif isinstance(dados, dict) and ("dataColors" in dados or "tableAccent" in dados):
                parcial, tip, forma, nome = _de_tema_powerbi(dados)
                formato = "tema do Power BI"
            else:
                raise ErroDeDesign("JSON não reconhecido", ["esperado: tema do Power BI (dataColors) ou tokens.json do bi-html"])
        elif sufixo == ".css":
            parcial, tip, forma, nome = _de_css(texto)
            formato = "CSS"
        elif sufixo in (".md", ".markdown"):
            if texto.lstrip().startswith("---") or "```yaml" in texto:
                parcial, tip, forma, nome = _de_design_md(texto)
                formato = "DESIGN.md"
            else:
                parcial, tip, forma, nome = _de_design_system_analise(texto)
                formato = "design-system.md (analise-dados)"
    except json.JSONDecodeError as e:
        raise ErroDeDesign(f"JSON inválido na linha {e.lineno}") from None
    except ErroDeCor as e:
        raise ErroDeDesign("cor inválida no design system", [str(e)]) from None
    origem = {"arquivo": str(arquivo.relative_to(projeto)) if arquivo.is_relative_to(projeto) else str(arquivo),
              "formato": formato}
    tokens = montar_tokens(parcial, nome, "enviado", origem, tip, forma)
    return gravar(projeto, tokens)


# ---------------------------------------------------------------- domínio e blocos

PALAVRAS = {
    "marketing": {"impressao": 3, "impressoes": 3, "clique": 3, "cliques": 3, "ctr": 3, "cpc": 3, "cpm": 3,
                  "campanha": 3, "conversao": 2, "conversoes": 2, "investimento": 2, "midia": 3, "anuncio": 3,
                  "alcance": 2, "sessoes": 2, "leads": 3, "roas": 3, "utm": 3, "atribuida": 2},
    "vendas": {"pedido": 3, "venda": 3, "vendas": 3, "faturamento": 2, "produto": 2, "sku": 3, "loja": 2,
               "ticket": 2, "quantidade": 1, "cliente": 1, "categoria": 1, "desconto": 2, "preco": 2, "receita": 1},
    "financeiro": {"conta": 2, "dre": 3, "competencia": 3, "centro_custo": 3, "custo": 1, "orcado": 3,
                   "realizado": 3, "cenario": 2, "despesa": 3, "lancamento": 3, "saldo": 3, "ebitda": 3,
                   "resultado": 2, "valor": 1, "grupo": 1},
    "operacoes": {"estoque": 3, "entrega": 3, "frete": 2, "prazo": 2, "ordem": 2, "producao": 3, "lote": 3,
                  "armazem": 3, "atraso": 3},
    "rh": {"funcionario": 3, "colaborador": 3, "salario": 3, "cargo": 3, "admissao": 3, "desligamento": 3,
           "turnover": 3, "headcount": 3, "departamento": 2},
}
BLOCOS = {
    "vendas": [("numero_destaque", "receita do período, com comparação"),
               ("faixa_kpis", "pedidos, ticket médio e desconto"),
               ("linha_tempo", "receita ao longo do tempo"),
               ("barras_ranking", "receita por loja ou região"),
               ("rosca", "mix de categorias"),
               ("mapa_uf", "receita por estado"),
               ("tabela", "produtos ou lojas com os números de apoio")],
    "marketing": [("numero_destaque", "investimento ou receita atribuída"),
                  ("faixa_kpis", "cliques, conversões e custo por resultado"),
                  ("funil", "impressões → cliques → conversões"),
                  ("barras_agrupadas", "resultados por canal"),
                  ("linha_tempo", "investimento e conversões ao longo do tempo"),
                  ("tabela", "campanhas com os números de apoio")],
    "financeiro": [("numero_destaque", "resultado do período, com comparação"),
                   ("cascata", "da receita bruta ao resultado, por grupo de conta"),
                   ("barras_agrupadas", "realizado vs. orçado por grupo"),
                   ("linha_tempo", "resultado mês a mês"),
                   ("tabela", "contas com realizado, orçado e diferença")],
    "operacoes": [("numero_destaque", "indicador principal de operação"), ("faixa_kpis", "prazos e volumes"),
                  ("linha_tempo", "evolução no tempo"), ("barras_ranking", "unidades ou rotas"), ("mapa_calor", "carga por hora e dia"),
                  ("tabela", "itens com os números de apoio")],
    "rh": [("numero_destaque", "quadro de pessoas"), ("faixa_kpis", "admissões, desligamentos e turnover"),
           ("barras_ranking", "pessoas por departamento"), ("linha_tempo", "evolução do quadro"), ("tabela", "departamentos")],
    "outro": [("numero_destaque", "a métrica principal"), ("linha_tempo", "evolução no tempo"),
              ("barras_ranking", "comparação entre grupos"), ("tabela", "detalhe com os números de apoio")],
}


def _tokens_de_nome(nome: str) -> list[str]:
    import unicodedata

    base = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    partes = re.split(r"[^a-z]+", base)
    juntas = ["_".join(partes[i:i + 2]) for i in range(len(partes) - 1)]
    return [p for p in partes + juntas if p]


def inferir_dominio(colunas: list[str], textos: list[str] | None = None) -> dict:
    """Domínio dos dados pelos nomes de coluna (peso cheio) e por textos de contexto (meio peso)."""
    pontos = {d: 0.0 for d in PALAVRAS}
    evidencias = {d: [] for d in PALAVRAS}
    for col in colunas:
        for t in set(_tokens_de_nome(col)):
            for d, pal in PALAVRAS.items():
                if t in pal:
                    pontos[d] += pal[t]
                    evidencias[d].append(col)
    for texto in textos or []:
        for t in set(_tokens_de_nome(texto)):
            for d, pal in PALAVRAS.items():
                if t in pal:
                    pontos[d] += pal[t] / 2
    ordem = sorted(pontos, key=pontos.get, reverse=True)
    melhor, segundo = ordem[0], ordem[1]
    if pontos[melhor] < 3:
        return {"dominio": "outro", "confianca": "baixa", "pontos": pontos, "evidencias": []}
    folga = pontos[melhor] - pontos[segundo]
    confianca = "alta" if folga >= 4 else ("media" if folga >= 1.5 else "baixa")
    return {"dominio": melhor, "confianca": confianca, "pontos": pontos,
            "evidencias": sorted(set(evidencias[melhor]))}


def blocos_sugeridos(dominio: str, colunas: list[str]) -> list[dict]:
    nomes = {c.lower() for c in colunas}
    tem_uf = bool(nomes & {"uf", "estado", "sigla_uf"})
    tem_data = any(any(p in c for p in ("data", "competencia", "mes", "dia")) for c in nomes)
    blocos = []
    for tipo, papel in BLOCOS.get(dominio, BLOCOS["outro"]):
        if tipo == "mapa_uf" and not tem_uf:
            continue
        if tipo == "linha_tempo" and not tem_data:
            continue
        blocos.append({"tipo": tipo, "papel": papel})
    return blocos


def colunas_do_projeto(projeto: Path, tabela: str | None = None) -> tuple[list[str], list[str]]:
    """Colunas da fonte (modelo, análise ou tabela ingerida) e textos de contexto para a inferência."""
    from .contrato import ler_contexto
    from .modelo import arquivo_da_fonte, esquema

    projeto = Path(projeto)
    textos = []
    if (projeto / "contexto.md").is_file():
        ctx = ler_contexto(projeto / "contexto.md")
        textos += [ctx.get("pergunta_negocio") or "", ctx.get("decisao") or ""]
        textos += [c["significado"] for c in ctx["dicionario"]]
    if tabela:
        arquivo = arquivo_da_fonte(projeto, {"tabela": tabela})
    elif (projeto / "saidas" / "dados_tratados.parquet").is_file():
        arquivo = projeto / "saidas" / "dados_tratados.parquet"
    else:
        tabelas = list(ler_manifesto(projeto)["tabelas"])
        if len(tabelas) != 1:
            raise ErroDeDesign("não sei de quais dados inferir o domínio",
                               [f"tabelas ingeridas: {', '.join(tabelas) or 'nenhuma'}; informe 'tabela'"])
        arquivo = arquivo_da_fonte(projeto, {"tabela": tabelas[0]})
    return list(esquema(arquivo)), textos


def propor_estilos(projeto: Path, tabela: str | None = None) -> dict:
    """Domínio inferido, duas opções de estilo e os blocos típicos do domínio."""
    colunas, textos = colunas_do_projeto(projeto, tabela)
    dominio = inferir_dominio(colunas, textos)
    opcoes = []
    for estilo, com_acento in PROPOSTAS[dominio["dominio"]]:
        t = tokens_de_estilo(estilo, dominio["dominio"], com_acento)
        opcoes.append({"estilo": estilo, "com_acento": com_acento, "nome": t["nome"],
                       "descricao": ESTILOS[estilo]["descricao"], "primaria": t[t["modo_padrao"]]["primary"],
                       "grafico": t[t["modo_padrao"]]["grafico"], "aa": t["aa"]})
    return {**dominio, "opcoes": opcoes, "blocos": blocos_sugeridos(dominio["dominio"], colunas),
            "design_system_do_analise": (Path(projeto) / "estilos" / "design-system.md").is_file()}


def aplicar_estilo(projeto: Path, estilo: str, dominio: str | None = None, com_acento: bool = True) -> dict:
    return gravar(projeto, tokens_de_estilo(estilo, dominio, com_acento))
