"""
Testes da fase F11: o dashboard num HTML autocontido, para envio.

Critério de aceite: o arquivo abre offline; com dados pessoais, a exportação é recusada.
A abertura sem internet foi conferida no navegador (uma única requisição, a do próprio arquivo);
aqui se confere que nada no arquivo aponta para fora e que o ECharts embutido é o da versão fixa.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import json, os, re, shutil, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
sys.path.insert(0, str(RAIZ / "exemplos"))
from bi_html import exportacao  # noqa: E402
from bi_html.exportacao import EXTERNO, ErroDeExportacao, autocontido, exportar  # noqa: E402
from bi_html.render import ECHARTS  # noqa: E402

FRAG = (f'<title>T</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter&amp;display=swap">\n'
        f'<style></style><footer class="rodape"><p>x</p></footer>\n<script src="{ECHARTS}"></script>\n<script>/*js*/</script>\n')


class TestAutocontido(unittest.TestCase):
    def test_embute_e_tira_o_que_vem_da_internet(self):
        h = autocontido(FRAG, "var echarts = {}; // </script> no meio", "Cópia para envio")
        self.assertNotIn("cdnjs", h)
        self.assertNotIn("fonts.googleapis", h)
        self.assertIn("var echarts = {};", h)
        self.assertIn("<\\/script> no meio", h)
        self.assertIn("<strong>Cópia para envio</strong>", h)
        self.assertEqual(EXTERNO.findall(h), [])

    def test_recusa_o_que_continua_dependendo_da_internet(self):
        with self.assertRaises(ErroDeExportacao):
            autocontido(FRAG + '<img src="https://exemplo.com/x.png">', "var e;", "aviso")
        with self.assertRaises(ErroDeExportacao):
            autocontido("<p>sem echarts</p>", "var e;", "aviso")

    def test_echarts_conferido_pelo_hash(self):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write("// não é o echarts")
        antes = os.environ.get("BI_HTML_ECHARTS")
        os.environ["BI_HTML_ECHARTS"] = f.name
        try:
            with self.assertRaises(ErroDeExportacao):
                exportacao.echarts()
        finally:
            os.environ.pop("BI_HTML_ECHARTS") if antes is None else os.environ.__setitem__("BI_HTML_ECHARTS", antes)
            Path(f.name).unlink()

    def test_dados_pessoais_recusam(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "saidas" / "bi").mkdir(parents=True)
            (p / "saidas" / "bi" / "manifesto.json").write_text(json.dumps({
                "versao": 1, "tabelas": {}, "eventos": [],
                "pbix": {"dados_pessoais": [{"coluna": "Clientes.cpf", "tipo": "cpf"}]}}), encoding="utf-8")
            with self.assertRaises(ErroDeExportacao) as e:
                exportar(p)
            self.assertIn("Clientes.cpf", " ".join(e.exception.detalhes))


@unittest.skipUnless(exportacao._cache().is_file() or os.environ.get("BI_HTML_ECHARTS"),
                     "sem o ECharts no cache (a primeira exportação baixa do cdnjs)")
class TestExportacaoReal(unittest.TestCase):
    def test_vendas(self):
        from construir import construir

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "vendas"
            for pasta in ("modelo", "dashboard"):
                shutil.copytree(RAIZ / "exemplos" / "vendas" / pasta, p / pasta)
            construir("vendas", p)
            r = exportar(p)
            h = (p / r["html"]).read_text(encoding="utf-8")
        self.assertGreater(r["bytes"], 1_000_000)
        self.assertEqual(EXTERNO.findall(h), [])
        self.assertIn("Licensed to the Apache Software Foundation", h)
        self.assertIn('"5.6.0"', h)
        self.assertNotIn("cdnjs.cloudflare.com/ajax/libs/echarts", h)
        self.assertRegex(h, r"Cópia para envio, gerada em \d{2}/\d{2}/\d{4}")
        self.assertTrue(re.search(r'<script type="application/json" id="dados-bi">', h))


if __name__ == "__main__":
    unittest.main()
