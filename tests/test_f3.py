"""
Testes da fase F3: design enviado ou inferido.

Critério de aceite: um DESIGN.md de exemplo e um tema do Power BI viram tokens.json
com contraste AA; os três conjuntos fictícios são classificados no domínio certo e
recebem estilos e blocos coerentes.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import json, shutil, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
FIXTURES = RAIZ / "fixtures"
EXEMPLO = Path(__file__).resolve().parent / "dados" / "projeto_exemplo"
sys.path.insert(0, str(PLUGIN / "lib"))
from bi_html import cores  # noqa: E402
from bi_html.ciclo import estado  # noqa: E402
from bi_html.design import (ACENTOS, ESTILOS, ErroDeDesign, aplicar_estilo, importar, inferir_dominio,  # noqa: E402
                            propor_estilos, tokens_de_estilo)
from bi_html.ingestao import ingerir, ler_manifesto  # noqa: E402
from bi_html.modelo import carregar, propor, registrar_linhagem  # noqa: E402
from bi_html.perfil import perfilar  # noqa: E402


def todos_os_pares_passam(tokens):
    return all(r["contraste"] >= r["minimo"] for r in tokens["contraste"])


def recalcular(tokens):
    """Confere o contraste de novo, direto das cores gravadas, sem confiar no relatório."""
    falhas = []
    for modo in ("claro", "escuro"):
        p = tokens[modo]
        for frente, fundo, minimo in [("foreground", "background", 4.5), ("card_foreground", "card", 4.5),
                                      ("muted_foreground", "card", 4.5), ("primary_foreground", "primary", 4.5),
                                      ("positivo", "card", 4.5), ("negativo", "card", 4.5), ("alerta", "card", 4.5)]:
            if cores.contraste(p[frente], p[fundo]) < minimo:
                falhas.append((modo, frente))
        for i, c in enumerate(p["grafico"]):
            if cores.contraste(c, p["card"]) < 3.0:
                falhas.append((modo, f"grafico_{i + 1}"))
    return falhas


class TestCores(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(cores.normalizar("#FFF"), "#ffffff")
        self.assertEqual(cores.normalizar("#1f6f5cff"), "#1f6f5c")
        self.assertEqual(cores.normalizar("rgb(255, 0, 0)"), "#ff0000")
        self.assertEqual(cores.normalizar("hsl(0 0% 100%)"), "#ffffff")
        self.assertEqual(cores.normalizar("oklch(1 0 0)"), "#ffffff")
        self.assertEqual(cores.normalizar("oklch(0% 0 0)"), "#000000")
        with self.assertRaises(cores.ErroDeCor):
            cores.normalizar("azul-bonito")

    def test_contraste_wcag(self):
        self.assertAlmostEqual(cores.contraste("#000000", "#ffffff"), 21.0, places=2)
        self.assertAlmostEqual(cores.contraste("#777777", "#ffffff"), 4.48, places=2)
        ajustada = cores.ajustar_contraste("#777777", "#ffffff", 4.5)
        self.assertGreaterEqual(cores.contraste(ajustada, "#ffffff"), 4.5)
        clareada = cores.ajustar_contraste("#333333", "#0b1120", 4.5)
        self.assertGreaterEqual(cores.contraste(clareada, "#0b1120"), 4.5)

    def test_ida_e_volta_oklch(self):
        for h in ("#1f6f5c", "#c2621b", "#3e5ba9", "#e8789a"):
            self.assertEqual(cores.hex_de(cores.oklch_para_rgb(*cores.rgb_para_oklch(cores.para_rgb(h)))), h)


class ProjetoTemp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def tokens(self):
        return json.loads((self.p / "design" / "tokens.json").read_text(encoding="utf-8"))


class TestDesignEnviado(ProjetoTemp):
    """Critério de aceite: DESIGN.md e tema do Power BI viram tokens.json com contraste AA."""

    def test_design_md(self):
        r = importar(self.p, FIXTURES / "design" / "DESIGN.md")
        t = self.tokens()
        self.assertTrue(t["aa"])
        self.assertEqual(recalcular(t), [])
        self.assertEqual(t["fonte"], "enviado")
        self.assertEqual(t["origem"]["formato"], "DESIGN.md")
        self.assertEqual(t["claro"]["background"], "#fbfaf7")
        self.assertEqual(t["claro"]["primary"], "#1f6f5c")
        self.assertEqual(t["claro"]["negativo"], "#b3261e")
        self.assertEqual(t["tipografia"]["sans"], "Source Sans 3")
        self.assertEqual(t["tipografia"]["titulo"], "Fraunces")
        self.assertEqual(t["forma"]["raio"], "6px")
        self.assertEqual(t["claro"]["grafico"][:3], ["#1f6f5c", "#c2621b", "#3e5ba9"])
        ajuste = next(a for a in r["ajustes_de_contraste"] if a["papel"] == "muted_foreground" and a["modo"] == "claro")
        self.assertEqual(ajuste["antes"], "#8a877f")
        self.assertLess(ajuste["contraste_antes"], 4.5)

    def test_tema_powerbi(self):
        r = importar(self.p, FIXTURES / "design" / "tema_powerbi.json")
        t = self.tokens()
        self.assertTrue(t["aa"])
        self.assertEqual(recalcular(t), [])
        self.assertEqual(t["origem"]["formato"], "tema do Power BI")
        self.assertEqual(t["claro"]["primary"], "#9b1b30")
        self.assertEqual(t["tipografia"]["sans"], "Segoe UI")
        texto = next(a for a in r["ajustes_de_contraste"] if a["papel"] == "foreground" and a["modo"] == "claro")
        self.assertEqual(texto["antes"], "#e8789a")
        self.assertLess(texto["contraste_antes"], 4.5)

    def test_css_em_oklch(self):
        importar(self.p, FIXTURES / "design" / "tokens.css")
        t = self.tokens()
        self.assertTrue(t["aa"])
        self.assertEqual(recalcular(t), [])
        self.assertEqual(t["claro"]["primary"], cores.normalizar("oklch(0.55 0.2 300)"))
        self.assertEqual(t["forma"]["raio"], "0.625rem")

    def test_design_system_do_analise(self):
        importar(self.p, EXEMPLO / "estilos" / "design-system.md")
        t = self.tokens()
        self.assertEqual(t["claro"]["primary"], "#0072b2")
        self.assertEqual(recalcular(t), [])

    def test_arquivos_e_manifesto(self):
        importar(self.p, FIXTURES / "design" / "DESIGN.md")
        css = (self.p / "design" / "tokens.css").read_text(encoding="utf-8")
        for trecho in (":root {", "--primary: #1f6f5c;", "--chart-5:", "prefers-color-scheme: dark",
                       ':root[data-tema="escuro"]', "--font-sans: 'Source Sans 3'", "--radius: 6px;"):
            self.assertIn(trecho, css)
        m = ler_manifesto(self.p)
        self.assertEqual(m["design"]["fonte"], "enviado")
        self.assertTrue(m["design"]["aa"])
        self.assertEqual(m["eventos"][-1]["evento"], "design")

    def test_entradas_invalidas(self):
        sem_primaria = self.p / "x.md"
        sem_primaria.write_text("---\nname: x\ncolors:\n  surface: \"#ffffff\"\n---\n", encoding="utf-8")
        with self.assertRaises(ErroDeDesign) as ctx:
            importar(self.p, sem_primaria)
        self.assertIn("primary", ctx.exception.mensagem)
        json_estranho = self.p / "y.json"
        json_estranho.write_text('{"cores": []}', encoding="utf-8")
        with self.assertRaises(ErroDeDesign):
            importar(self.p, json_estranho)
        imagem = self.p / "marca.png"
        imagem.write_bytes(b"\x89PNG")
        with self.assertRaises(ErroDeDesign) as ctx:
            importar(self.p, imagem)
        self.assertIn("imagem", " ".join(ctx.exception.detalhes))


class TestEstilosBase(unittest.TestCase):
    def test_todo_estilo_com_todo_acento_passa_no_aa(self):
        for estilo in ESTILOS:
            for dominio in list(ACENTOS) + [None]:
                t = tokens_de_estilo(estilo, dominio)
                self.assertTrue(t["aa"], (estilo, dominio))
                self.assertEqual(recalcular(t), [], (estilo, dominio))
                self.assertEqual(len(t["claro"]["grafico"]), 5)

    def test_modo_escuro_e_escuro(self):
        t = tokens_de_estilo("claro", "vendas")
        self.assertTrue(cores.eh_escuro(t["escuro"]["background"]))
        self.assertFalse(cores.eh_escuro(t["claro"]["background"]))


class TestDominioInferido(ProjetoTemp):
    """Critério de aceite: os três conjuntos caem no domínio certo e recebem estilos e blocos coerentes."""

    def preparar(self):
        for arq in ("vendas.csv", "marketing.xlsx", "financeiro.csv"):
            ingerir(self.p, FIXTURES / arq)

    def test_tres_dominios(self):
        self.preparar()
        esperado = {"vendas": ("vendas", "mapa_uf"), "marketing": ("marketing", "funil"),
                    "financeiro": ("financeiro", "cascata")}
        for tabela, (dominio, bloco) in esperado.items():
            r = propor_estilos(self.p, tabela)
            self.assertEqual(r["dominio"], dominio, tabela)
            self.assertEqual(r["confianca"], "alta", tabela)
            self.assertIn(bloco, [b["tipo"] for b in r["blocos"]], tabela)
            self.assertEqual(len(r["opcoes"]), 2)
            self.assertTrue(all(o["aa"] for o in r["opcoes"]))
        self.assertEqual(propor_estilos(self.p, "financeiro")["opcoes"][0]["estilo"], "corporativo")
        self.assertEqual(propor_estilos(self.p, "marketing")["opcoes"][0]["primaria"], ACENTOS["marketing"][1])

    def test_sem_sinal_de_dominio_vira_outro(self):
        r = inferir_dominio(["codigo", "descricao", "quantidade_x"])
        self.assertEqual(r["dominio"], "outro")
        self.assertEqual(r["confianca"], "baixa")

    def test_projeto_da_analise_usa_contexto(self):
        p = self.p / "projeto"
        shutil.copytree(EXEMPLO, p)
        r = propor_estilos(p)
        self.assertEqual(r["dominio"], "vendas")
        self.assertNotIn("mapa_uf", [b["tipo"] for b in r["blocos"]])
        self.assertTrue(r["design_system_do_analise"])

    def test_aplicar_estilo_grava_tokens(self):
        r = aplicar_estilo(self.p, "corporativo", "financeiro", com_acento=False)
        self.assertTrue(r["aa"])
        self.assertEqual(self.tokens()["claro"]["primary"], "#1e3a5f")
        self.assertEqual(self.tokens()["fonte"], "inferido")


class TestCicloComDesign(ProjetoTemp):
    def test_design_entra_depois_das_metricas(self):
        ingerir(self.p, FIXTURES / "vendas.csv")
        perfilar(self.p, "vendas")
        propor(self.p, "vendas")
        modelo, arquivo, _ = carregar(self.p)
        registrar_linhagem(self.p, modelo, arquivo)
        self.assertEqual(estado(self.p)["etapa"], "design")
        aplicar_estilo(self.p, "claro", "vendas")
        self.assertEqual(estado(self.p)["etapa"], "dashboard")


if __name__ == "__main__":
    unittest.main()
