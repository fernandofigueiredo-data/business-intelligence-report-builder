"""
Testes da fase F8: o fluxo completo num caso real, sem publicação.

Critério de aceite: fluxo completo sem publicação; problemas encontrados viram issues do plugin.
O caso real fica fora do repositório (casos/, ignorado pelo git), então aqui se confere o registro
da prova (cada etapa ok, nada publicado, nenhum caminho local) e a correção feita durante a F8:
a conversão com a pasta do projeto em caminho relativo.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import importlib.util, json, os, re, shutil, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROVA = RAIZ / "provas" / "f8"
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))


class TestRegistro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = json.loads((PROVA / "resultados.json").read_text(encoding="utf-8"))

    def test_fluxo_completo_sem_publicacao(self):
        self.assertFalse(self.R["publicado"])
        etapas = {e["etapa"]: e for e in self.R["etapas"]}
        self.assertEqual(set(etapas), {"ingestao", "perfil", "modelo", "design", "dashboard", "achados", "documento",
                                       "offline", "assistente", "conversao", "comparativo", "ciclo"})
        self.assertTrue(all(e["ok"] for e in etapas.values()), [e for e in etapas.values() if not e["ok"]])
        self.assertEqual(etapas["ciclo"]["estado_do_ciclo"], "concluido")
        self.assertRegex(etapas["documento"]["verificacao"], r"^(\d+)/\1 números rastreados$")
        self.assertEqual(etapas["conversao"]["traduzidas_que_batem"], etapas["conversao"]["traduzidas_testadas"])
        self.assertIsNone(etapas["comparativo"]["via"])  # nenhum link público: nada publicado

    def test_md_em_dia(self):
        spec = importlib.util.spec_from_file_location("prova_f8", PROVA / "executar.py")
        prova = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prova)
        self.assertEqual((PROVA / "RESULTADO.md").read_text(encoding="utf-8"), prova.gerar_md(self.R))

    def test_issues_registradas(self):
        texto = (PROVA / "ISSUES.md").read_text(encoding="utf-8")
        issues = re.findall(r"^### (\d+)\. ", texto, re.M)
        self.assertEqual(issues, [str(i) for i in range(1, len(issues) + 1)])
        self.assertGreaterEqual(len(issues), 10)
        for secao in ("## Alta", "## Média", "## Baixa", "## Corrigida durante a F8"):
            self.assertIn(secao, texto)

    def test_sem_caminhos_locais_nem_caso_no_git(self):
        for arq in PROVA.iterdir():
            if arq.is_file():
                texto = arq.read_text(encoding="utf-8")
                self.assertNotIn("/Users/", texto, arq.name)
                self.assertNotIn(str(Path.home()), texto, arq.name)
        self.assertIn("casos/", (RAIZ / ".gitignore").read_text(encoding="utf-8").split())


@unittest.skipUnless(shutil.which("uv"), "a conversão precisa do uv (processo de leitura do .pbix)")
class TestCaminhoRelativo(unittest.TestCase):
    def test_conversao_com_projeto_relativo_renderiza(self):
        from bi_html.conversao import converter

        with tempfile.TemporaryDirectory() as tmp:
            antes = os.getcwd()
            os.chdir(tmp)
            try:
                Path("projeto").mkdir()
                r = converter(Path("projeto"), RAIZ / "fixtures" / "vendas.pbix")
            finally:
                os.chdir(antes)
            self.assertTrue(r["tema"]["importado"], r["tema"])
            self.assertEqual(r["avisos"], [])
            self.assertEqual(r["dashboard"], "saidas/bi/dashboard.html")
            self.assertTrue((Path(tmp) / "projeto" / "saidas" / "bi" / "dashboard.html").is_file())


if __name__ == "__main__":
    unittest.main()
