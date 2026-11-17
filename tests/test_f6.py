"""
Testes da fase F6: prova de conceito com .pbix reais.

Critério de aceite: cada célula da matriz 5.1 marcada como testada (ou com o motivo de não
ter sido), com a saída da ferramenta anexada; tempo e memória registrados. Os .pbix não
ficam no repositório, então os testes conferem o resultado gravado por provas/f6/executar.py,
e não rodam o pbix-mcp (que exige mcp<2, incompatível com o servidor bi-dados).

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import json, re, sys, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROVA = RAIZ / "provas" / "f6"
sys.path.insert(0, str(PROVA))
import executar  # noqa: E402

R = json.loads((PROVA / "resultados.json").read_text(encoding="utf-8"))
ELEMENTOS = [e for e, _ in executar.ELEMENTOS]
MODOS = [m for m, _ in executar.MODOS]


class TestCriteriosDeAceite(unittest.TestCase):
    def test_matriz_completa(self):
        """Toda célula elemento × modo tem um estado, e as não testadas dizem por quê."""
        self.assertEqual(set(R["matriz"]), set(ELEMENTOS))
        for e in ELEMENTOS:
            self.assertEqual(set(R["matriz"][e]), set(MODOS))
            for m in MODOS:
                c = R["matriz"][e][m]
                self.assertIn(c["status"], {"testada", "sem_elemento", "nao_testada"}, (e, m))
                if c["status"] == "testada":
                    self.assertIn(c["classificacao"], {"I", "P", "N"}, (e, m))
                    self.assertTrue(c["testada_em"])
                else:
                    self.assertTrue(c["motivo"], (e, m))

    def test_importacao_testada(self):
        """Com três arquivos em importação, cada elemento presente neles foi testado."""
        self.assertEqual({i["modo"] for i in R["arquivos"].values()}, {"importacao"})
        testadas = {e for e in ELEMENTOS if R["matriz"][e]["importacao"]["status"] == "testada"}
        self.assertEqual(testadas, set(ELEMENTOS) - {"visuais_personalizados", "rls"})
        for e in ("visuais_personalizados", "rls"):
            self.assertEqual(R["matriz"][e]["importacao"]["status"], "sem_elemento")

    def test_saida_anexada(self):
        """Cada resultado por arquivo cita a saída das ferramentas, e o arquivo existe."""
        for a, info in R["arquivos"].items():
            for e in ELEMENTOS:
                r = info["elementos"][e]
                self.assertNotEqual(r["status"], "erro", (a, e, r.get("resumo")))
                self.assertTrue(r["anexos"], (a, e))
                for anexo in r["anexos"]:
                    self.assertTrue((PROVA / anexo).is_file(), anexo)

    def test_tempo_e_memoria(self):
        for a, info in R["arquivos"].items():
            for r in [info["deteccao_do_modo"]] + [info["elementos"][e] for e in ELEMENTOS]:
                self.assertGreater(r["tempo_processo_s"], 0, a)
                self.assertGreater(r["tempo_abrir_s"], 0, a)
                self.assertGreater(r["pico_rss_mb"], 0, a)

    def test_ambiente_registrado(self):
        amb = R["ambiente"]
        for chave in ("python", "pbix-mcp", "pbixray", "duckdb", "maquina"):
            self.assertTrue(amb[chave], chave)
        for info in R["arquivos"].values():
            self.assertRegex(info["sha256"], r"^[0-9a-f]{64}$")


class TestResultados(unittest.TestCase):
    def test_dados_iguais_nos_dois_leitores(self):
        for a, info in R["arquivos"].items():
            comparacao = json.loads((PROVA / "saidas" / a / "dados__comparacao.json").read_text(encoding="utf-8"))
            for t in comparacao:
                self.assertTrue(t["iguais"], (a, t["tabela"]))
                self.assertEqual(t["linhas_metadados"], t["linhas_pbixray"])

    def test_paridade_dax(self):
        """Cada conferência compara o pbix-mcp com SQL independente; todas batem."""
        total = 0
        for a, info in R["arquivos"].items():
            arq = PROVA / "saidas" / a / "dax_calculo__paridade.json"
            if not arq.is_file():
                continue
            for c in json.loads(arq.read_text(encoding="utf-8")):
                total += 1
                self.assertTrue(c["bate"], (a, c["medida"]))
                self.assertTrue(executar._comparar(c["pbix_mcp"], c["referencia_sql"]))
        self.assertGreaterEqual(total, 20)

    def test_matriz_md_em_dia(self):
        """MATRIZ.md é gerado de resultados.json e não foi editado à mão."""
        self.assertEqual((PROVA / "MATRIZ.md").read_text(encoding="utf-8"), executar.gerar_matriz(R))

    def test_consolidacao_reproduzivel(self):
        self.assertEqual(executar.consolidar(R), R["matriz"])


class TestPrivacidade(unittest.TestCase):
    def test_anexos_sem_caminhos_nem_ids(self):
        proibido = re.compile(r"/Users/|[A-Za-z]:\\\\(?:Users|Mac)\\\\|OneDrive|\"(?:DatasetId|ReportId)\"\s*:\s*\"[0-9a-f]")
        for arq in [PROVA / "resultados.json", *sorted((PROVA / "saidas").rglob("*"))]:
            if arq.is_file():
                texto = arq.read_text(encoding="utf-8")
                self.assertIsNone(proibido.search(texto), arq.name)
                self.assertNotIn(str(Path.home()), texto, arq.name)

    def test_anexos_sem_dados_embutidos(self):
        """Dados em base64 nas consultas M são omitidos; tabelas só como contagem e hash."""
        b64 = re.compile(r"Binary\.FromText\(\\?\"[A-Za-z0-9+/=]{80,}")
        for arq in sorted(p for p in (PROVA / "saidas").rglob("*") if p.is_file()):
            self.assertIsNone(b64.search(arq.read_text(encoding="utf-8")), arq.name)
            json.loads(arq.read_text(encoding="utf-8"))  # todo anexo é JSON válido
        permitido = {"tabela", "linhas_metadados", "linhas_pbix_mcp", "linhas_pbixray", "colunas",
                     "colunas_divergentes", "erro_pbixray", "iguais"}
        for arq in (PROVA / "saidas").rglob("dados__comparacao.json"):
            for t in json.loads(arq.read_text(encoding="utf-8")):
                self.assertLessEqual(set(t), permitido, arq.parent.name)

    def test_ocultar(self):
        texto = json.dumps({"m": 'Csv.Document(File.Contents("C:\\Users\\alguem\\dados\\eleicoes.csv"))',
                            "t": "Medidas:\n  ifdata: Excel", "b": 'Binary.FromText("' + "A" * 100 + '")'})
        saida = executar.ocultar(texto, [])
        self.assertIn("<caminho omitido>\\\\eleicoes.csv", saida)
        self.assertNotIn("alguem", saida)
        self.assertIn("Medidas:\\n  ifdata", saida)
        self.assertIn("base64 omitido: 100 caracteres", saida)
        json.loads(saida)

    def test_normalizar(self):
        from datetime import date, datetime
        self.assertEqual(executar.normalizar(3.0), "3")
        self.assertEqual(executar.normalizar(float("nan")), None)
        self.assertEqual(executar.normalizar(True), "true")
        self.assertEqual(executar.normalizar(date(2026, 6, 30)), executar.normalizar(datetime(2026, 6, 30)))
        a = executar.hash_de_colunas(["x"], [(1,), (2,)])
        b = executar.hash_de_colunas(["x"], [(2.0,), (1.0,)])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
