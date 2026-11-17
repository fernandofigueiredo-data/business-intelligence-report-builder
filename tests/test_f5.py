"""
Testes da fase F5: documento de decisão.

Critério de aceite: 100% dos números do texto rastreados a achados; cada achado da
conclusão do notebook aparece como reproduzido ou não reproduzido pela camada de
métricas; a seção de limites existe; o documento cabe em até duas páginas A4 (medido
no navegador, ver o PR). A releitura pelo subagente revisor do analise-dados é feita
fora dos testes.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import json, shutil, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
sys.path.insert(0, str(PLUGIN / "lib"))
sys.path.insert(0, str(RAIZ / "exemplos"))
from construir import construir  # noqa: E402
from bi_html.achados import gerar  # noqa: E402
from bi_html.conclusao import reproduzir  # noqa: E402
from bi_html.documento import renderizar_documento  # noqa: E402
from bi_html.numeros import extrair  # noqa: E402
from bi_html.verificador import ErroDeDocumento, verificar  # noqa: E402

DOC = (RAIZ / "exemplos" / "ciclo" / "decisao" / "documento.md").read_text(encoding="utf-8")


def novo_ciclo(destino: Path) -> Path:
    p = destino / "ciclo"
    for pasta in ("modelo", "dashboard", "decisao"):
        shutil.copytree(RAIZ / "exemplos" / "ciclo" / pasta, p / pasta)
    construir("ciclo", p)
    return p


class Ciclo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.p = novo_ciclo(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def escrever(self, texto):
        (self.p / "decisao" / "documento.md").write_text(texto, encoding="utf-8")

    def tearDown(self):
        self.escrever(DOC)


class TestCriteriosDeAceite(Ciclo):
    def test_todos_os_numeros_rastreados(self):
        r = verificar(self.p)
        self.assertTrue(r["ok"], r["problemas"])
        self.assertEqual(r["cobertura_pct"], 100.0)
        self.assertGreaterEqual(r["total_de_numeros"], 15)
        self.assertTrue(all(n["origens"] for n in r["numeros"]))

    def test_cada_item_da_conclusao_tem_estado(self):
        r = json.loads((self.p / "saidas/bi/reproducao.json").read_text(encoding="utf-8"))
        estados = [i["estado"] for i in r["itens"]]
        self.assertEqual(estados, ["reproduzido", "reproduzido", "reproduzido", "sem_numero"])
        sudeste = r["itens"][0]["verificacoes"][0]["observado"][0]
        self.assertEqual(sudeste["formatado"], "39,3%")
        self.assertEqual([o["formatado"] for o in r["itens"][1]["verificacoes"][0]["observado"]], ["63,3%", "64,2%"])

    def test_documento_tem_limites_e_apendice(self):
        html = (self.p / "saidas/bi/decisao.html").read_text(encoding="utf-8")
        for trecho in ("O que os dados não permitem afirmar", "Opções de decisão", "Próximas perguntas",
                       "Apêndice de método", "Conclusão da análise, reproduzida pela camada de métricas",
                       "Como cada métrica citada é calculada", "@page { size: A4",
                       "<strong>Decisão:</strong>"):
            self.assertIn(trecho, html)
        import re
        total = re.search(r"(\d+) de (\d+) números do texto", html)
        self.assertEqual(total.group(1), total.group(2))

    def test_lider_traz_a_contagem_e_amplitude_ignora_nao_informado(self):
        from bi_html.achados import ler
        a = {x["id"]: x for x in ler(self.p)["achados"]}
        self.assertEqual(a["A6"]["formatado"]["contagem"], "1.933")
        self.assertEqual(a["A6"]["formatado"]["contagem_total"], "5.000")
        self.assertEqual(a["A8"]["valores"]["grupos"], 5)
        self.assertNotEqual(a["A8"]["formatado"]["grupo_menor"], "Não informada")
        self.assertEqual(a["A10"]["formatado"]["mes_2025-10"], "outubro de 2025: R$ 71.503,46")

    def test_documento_e_curto(self):
        r = renderizar_documento(self.p)
        self.assertLess(r["palavras"], 900)


class TestVerificadorPegaErros(Ciclo):
    def test_numero_inventado(self):
        self.escrever(DOC.replace("O Sudeste soma R$ 9,8 milhões", "O Sudeste soma R$ 9,9 milhões"))
        r = verificar(self.p)
        self.assertFalse(r["ok"])
        self.assertIn("R$ 9,9 milhões", " ".join(r["problemas"]))

    def test_percentual_arredondado_errado(self):
        self.escrever(DOC.replace("875 vendas e 17,5% do faturamento", "875 vendas e 21% do faturamento"))
        self.assertIn("21%", " ".join(verificar(self.p)["problemas"]))

    def test_arredondamento_honesto_passa(self):
        self.escrever(DOC.replace("39,3% do faturamento, com", "39% do faturamento, com").replace("R$ 9,8 milhões", "R$ 10 milhões")
                      .replace("R$ 71.503,46", "R$ 72 mil").replace("(63,3% e 64,2%", "(63% e 64%"))
        r = verificar(self.p)
        self.assertTrue(r["ok"], r["problemas"])

    def test_arredondamento_para_baixo_errado_e_pego(self):
        # R$ 71.503,46 arredonda para R$ 72 mil (meio para cima), não para R$ 71 mil
        self.escrever(DOC.replace("R$ 71.503,46", "R$ 71 mil"))
        self.assertIn("R$ 71 mil", " ".join(verificar(self.p)["problemas"]))

    def test_ano_fora_dos_dados(self):
        self.escrever(DOC.replace("Trazer as vendas do ano anterior", "Trazer as vendas de 2026"))
        self.assertIn("2026", " ".join(verificar(self.p)["problemas"]))

    def test_ano_citado_pela_conclusao_reproduzida_vale(self):
        self.escrever(DOC.replace("Trazer as vendas do ano anterior", "Trazer as vendas de 2024"))
        self.assertTrue(verificar(self.p)["ok"])

    def test_secao_de_limites_obrigatoria(self):
        inicio = DOC.index("## O que os dados não permitem afirmar")
        fim = DOC.index("## Opções de decisão")
        self.escrever(DOC[:inicio] + DOC[fim:])
        self.assertIn("O que os dados não permitem afirmar", " ".join(verificar(self.p)["problemas"]))

    def test_referencia_inexistente(self):
        self.escrever(DOC.replace("[A6] [A8] [C1]", "[A99] [C1]"))
        self.assertIn("[A99]", " ".join(verificar(self.p)["problemas"]))

    def test_render_recusa_documento_com_problema(self):
        self.escrever(DOC.replace("R$ 35.747,96", "R$ 36.000,00"))
        with self.assertRaises(ErroDeDocumento):
            renderizar_documento(self.p)


class TestReproducao(Ciclo):
    def verificacoes(self, texto):
        (self.p / "decisao" / "verificacoes.yaml").write_text(texto, encoding="utf-8")
        try:
            return reproduzir(self.p)
        finally:
            shutil.copy(RAIZ / "exemplos/ciclo/decisao/verificacoes.yaml", self.p / "decisao/verificacoes.yaml")
            reproduzir(self.p)

    def test_numero_que_nao_confere_nao_e_reproduzido(self):
        r = self.verificacoes("""
- {item: 1, numero: "39%", metrica: participacao_faturamento, dimensoes: [regiao], onde: {regiao: Sul}, afirmacao: aproximado}
""")
        self.assertEqual(r["itens"][0]["estado"], "nao_reproduzido")
        self.assertEqual(r["itens"][1]["estado"], "nao_reproduzido")
        self.assertEqual(r["itens"][1]["sem_verificacao"], ["60%"])

    def test_numero_que_nao_esta_no_texto_e_recusado(self):
        r = self.verificacoes("""
- {item: 1, numero: "40%", metrica: participacao_faturamento, dimensoes: [regiao], onde: {regiao: Sudeste}, afirmacao: aproximado}
""")
        self.assertEqual(r["verificacoes_invalidas"][0]["problemas"], ["o número '40%' não está escrito no item 1"])

    def test_item_nao_reproduzido_nao_pode_ser_citado(self):
        self.verificacoes("[]")  # roda sem verificações e restaura no fim
        (self.p / "decisao" / "verificacoes.yaml").write_text("[]", encoding="utf-8")
        reproduzir(self.p)
        try:
            r = verificar(self.p)
            self.assertIn("[C1] não foi reproduzido", " ".join(r["problemas"]))
        finally:
            shutil.copy(RAIZ / "exemplos/ciclo/decisao/verificacoes.yaml", self.p / "decisao/verificacoes.yaml")
            reproduzir(self.p)


class TestAchadosComSinal(unittest.TestCase):
    def test_financeiro_usa_composicao_e_nao_participacao(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "financeiro"
            for pasta in ("modelo", "dashboard"):
                shutil.copytree(RAIZ / "exemplos" / "financeiro" / pasta, p / pasta)
            construir("financeiro", p)
            r = gerar(p)
            tipos = {a["tipo"] for a in r["achados"]}
            self.assertIn("composicao", tipos)
            self.assertNotIn("lider", tipos)
            versus = next(a for a in r["achados"] if a["tipo"] == "comparacao_metricas")
            self.assertEqual(versus["metricas"], ["resultado_realizado", "resultado_orcado"])
            cob = next(a for a in r["achados"] if a["tipo"] == "cobertura")
            self.assertEqual(cob["formatado"]["fim"], "31/12/2025")


class TestNumeros(unittest.TestCase):
    def test_leitura_pt_br(self):
        n = {x.texto: x for x in extrair("R$ 4,1 milhões, R$ 380 mil, 39,3%, 3,2 p.p., 12,10×, 16.254, 2025 [A12]")}
        self.assertEqual(n["R$ 4,1 milhões"].escala, 1e6)
        self.assertEqual(n["R$ 380 mil"].valor, 380000)
        self.assertAlmostEqual(n["39,3%"].valor, 0.393)
        self.assertEqual(n["3,2 p.p."].tipo, "pp")
        self.assertEqual(n["12,10×"].tipo, "mult")
        self.assertEqual(n["16.254"].valor, 16254)
        self.assertEqual(n["2025"].tipo, "ano")
        self.assertNotIn("12", n)
        self.assertTrue(n["R$ 4,1 milhões"].bate_com(4076230.52, "moeda"))
        self.assertFalse(n["R$ 4,1 milhões"].bate_com(4176230.52, "moeda"))


if __name__ == "__main__":
    unittest.main()
