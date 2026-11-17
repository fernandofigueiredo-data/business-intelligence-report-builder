"""
Testes da fase F7b: o relatório original do Power BI ao lado do convertido (Fluxo 2, via (b)).

Critério de aceite: relatório de exemplo visível em página pública ou no Artifact, com o caminho
escolhido conforme a licença; teste do iframe no Artifact registrado. A publicação no serviço do
Power BI é do usuário (conta Free: Publicar na Web, que depende do administrador do tenant); aqui
se testa o caminho por licença, a página de comparação e o registro do teste do iframe.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import importlib.util, json, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
from bi_html.incorporacao import ErroDeIncorporacao, montar_comparativo, validar_link  # noqa: E402

PUBLICO = "https://app.powerbi.com/view?r=eyJrIjoiZmljdGljaW8ifQ"
SEGURO = "https://app.powerbi.com/reportEmbed?reportId=0b7c4ea3-8f18-462d-a41d-a57fdeaec6fe&autoAuth=true"


class TestLink(unittest.TestCase):
    def test_publicar_na_web(self):
        r = validar_link(PUBLICO, "free")
        self.assertEqual(r["via"], "publicar_na_web")
        self.assertTrue(any("qualquer pessoa" in a for a in r["avisos"]))

    def test_incorporacao_segura_conforme_licenca(self):
        self.assertEqual(validar_link(SEGURO, "pro")["avisos"], [])
        free = validar_link(SEGURO, "free")
        self.assertEqual(free["via"], "incorporacao_segura")
        self.assertTrue(any("Pro ou PPU" in a for a in free["avisos"]))

    def test_recusa(self):
        for url in ("http://app.powerbi.com/view?r=x", "https://app.powerbi.com.exemplo.com/view?r=x",
                    "https://powerbi.com/view?r=x", "https://app.powerbi.com/home", "https://app.powerbi.com/view",
                    "https://app.powerbi.com/reportEmbed?reportId=nao-e-guid", "javascript:alert(1)", ""):
            with self.assertRaises(ErroDeIncorporacao, msg=url):
                validar_link(url, "free")
        with self.assertRaises(ErroDeIncorporacao):
            validar_link(PUBLICO, "premium")


def _projeto(destino: Path) -> Path:
    """Projeto com uma conversão mínima: relatório, página renderizada e tokens."""
    (destino / "saidas" / "bi" / "pbix").mkdir(parents=True)
    (destino / "saidas" / "bi" / "paginas").mkdir(parents=True)
    (destino / "design").mkdir()
    (destino / "design" / "tokens.css").write_text(":root { --background: #fff; }\n", encoding="utf-8")
    (destino / "saidas" / "bi" / "paginas" / "visao_geral.html").write_text("<p>convertido</p>", encoding="utf-8")
    rel = {
        "arquivo": {"nome": "vendas.pbix"},
        "tabelas": [{"tabela": "Vendas", "iguais": True}, {"tabela": "Lojas", "iguais": True}],
        "medidas": [{"medida": "Faturamento", "classe": "traduzida", "equivalencia": {"validada": True}},
                    {"medida": "Receita Site", "classe": "traduzida", "equivalencia": {"validada": False}},
                    {"medida": "Rótulo", "classe": "texto"},
                    {"medida": "Soma de x", "classe": "implicita", "equivalencia": {"validada": True}}],
        "paginas": [{"nome": "Visão geral", "html": "saidas/bi/paginas/visao_geral.html", "visuais": [
            {"titulo": "Faturamento", "tipo_power_bi": "card", "status": "convertido", "motivos": []},
            {"titulo": None, "tipo_power_bi": "textbox", "status": "decorativo", "motivos": ["texto"]},
            {"titulo": "Mapa <de> lojas", "tipo_power_bi": "azureMap", "status": "nao_convertido",
             "motivos": ["o mapa não é por UF"]}]}],
    }
    (destino / "saidas" / "bi" / "pbix" / "conversao.json").write_text(json.dumps(rel), encoding="utf-8")
    return destino


class TestComparativo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = _projeto(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def html(self):
        return (self.p / "saidas" / "bi" / "comparativo" / "index.html").read_text(encoding="utf-8")

    def test_sem_link_mostra_o_passo_a_passo(self):
        r = montar_comparativo(self.p)
        self.assertIsNone(r["via"])
        h = self.html()
        self.assertIn("Publicar na Web", h)
        self.assertNotIn("app.powerbi.com/view?r=", h.split("<ol>")[0])
        self.assertTrue((self.p / "saidas" / "bi" / "comparativo" / "convertido.html").is_file())
        self.assertTrue((self.p / "saidas" / "bi" / "comparativo" / "tokens.css").is_file())
        self.assertTrue(h.startswith("<!doctype html>"))
        self.assertIn("<title>Original e convertido</title>", h.split("</head>")[0])

    def test_com_link_e_numeros_do_relatorio(self):
        r = montar_comparativo(self.p, PUBLICO, "free")
        self.assertEqual(r["via"], "publicar_na_web")
        h = self.html()
        self.assertIn(f'src="{PUBLICO}"', h)
        self.assertIn('src="convertido.html"', h)
        # números saem do relatório da conversão (implícitas fora da contagem de medidas)
        self.assertIn("<strong>2 de 3</strong> medidas traduzidas", h)
        self.assertIn("<strong>1 de 2</strong> traduzidas batem com o Power BI", h)
        self.assertIn("<strong>1 de 2</strong> visuais com dado convertidos", h)
        self.assertIn("Receita Site", h)
        self.assertIn("Mapa &lt;de&gt; lojas", h)
        manifesto = json.loads((self.p / "saidas" / "bi" / "manifesto.json").read_text(encoding="utf-8"))
        self.assertEqual((manifesto["incorporacao"]["via"], manifesto["incorporacao"]["licenca"]), ("publicar_na_web", "free"))
        self.assertIn("Artifact", manifesto["incorporacao"]["artifact"])

    def test_link_com_aspas_nao_quebra_o_atributo(self):
        montar_comparativo(self.p, 'https://app.powerbi.com/view?r=a"onload="alert(1)', "free")
        self.assertNotIn('"onload="', self.html())

    def test_erros(self):
        with self.assertRaises(ErroDeIncorporacao):
            montar_comparativo(self.p, pagina="Outra")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ErroDeIncorporacao):
            montar_comparativo(Path(tmp))


class TestTesteDoIframe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prova = RAIZ / "provas" / "f7b"
        spec = importlib.util.spec_from_file_location("prova_f7b", prova / "executar.py")
        cls.prova = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.prova)
        cls.R = json.loads((prova / "resultados.json").read_text(encoding="utf-8"))
        cls.md = (prova / "RESULTADO.md").read_text(encoding="utf-8")

    def test_registrado(self):
        casos = {c["via"]: c for c in self.R["casos"]}
        self.assertTrue(casos["publicar_na_web"]["incorporavel"])
        self.assertTrue(casos["incorporacao_segura"]["incorporavel"])
        self.assertFalse(casos["servico"]["incorporavel"])
        self.assertFalse(self.R["artifact"]["incorporavel"])
        self.assertTrue(self.R["navegador"]["verificado"])

    def test_md_em_dia(self):
        self.assertEqual(self.md, self.prova.gerar_md(self.R))

    def test_regra_de_bloqueio(self):
        b = self.prova.bloqueio
        self.assertIsNone(b({}))
        self.assertIsNotNone(b({"x-frame-options": "DENY"}))
        self.assertIsNotNone(b({"content-security-policy": "default-src 'self'; frame-ancestors 'self'"}))
        self.assertIsNone(b({"content-security-policy": "frame-ancestors *"}))


if __name__ == "__main__":
    unittest.main()
