"""
Testes da fase F2: modelo de métricas, consulta, cubo e linhagem.

Critério de aceite: consultas batem com o cálculo manual (diferença zero) e cada
métrica tem definição e linhagem no manifesto. O cálculo manual lê o CSV
original com Decimal, sem passar pela ingestão nem pelo DuckDB.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import csv, hashlib, json, shutil, sys, tempfile, unittest
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
FIXTURES = RAIZ / "fixtures"
EXEMPLO = Path(__file__).resolve().parent / "dados" / "projeto_exemplo"
sys.path.insert(0, str(PLUGIN / "lib"))
from bi_html.ciclo import estado  # noqa: E402
from bi_html.consulta import consultar, exportar_cubo, formatar, periodo_de_comparacao, resolver_periodo  # noqa: E402
from bi_html.ingestao import ingerir, ler_manifesto  # noqa: E402
from bi_html.modelo import ErroDeModelo, carregar, propor, registrar_linhagem  # noqa: E402
from bi_html.perfil import perfilar  # noqa: E402

MODELO_VENDAS = """
versao: "0.1"
fonte: {tabela: vendas, coluna_data: data_pedido}
dimensoes:
  regiao: {coluna: regiao, descricao: Região da loja}
  canal: {coluna: canal, descricao: Canal de venda}
  categoria: {coluna: categoria, descricao: Categoria do produto}
  mes: {coluna: data_pedido, granularidade: mes, descricao: Mês do pedido}
  dia_da_semana: {coluna: data_pedido, granularidade: dia_semana, descricao: Dia da semana do pedido}
metricas:
  receita_total: {descricao: Receita dos pedidos, tipo: soma, coluna: receita, formato: moeda}
  receita_loja_fisica:
    descricao: Receita só da loja física
    tipo: soma
    coluna: receita
    formato: moeda
    filtro: [{coluna: canal, operador: igual, valor: Loja física}]
  registros: {descricao: Linhas, tipo: contagem, formato: inteiro}
  pedidos: {descricao: Pedidos diferentes, tipo: contagem_distinta, coluna: pedido_id, formato: inteiro}
  ticket_medio: {descricao: Receita por pedido, tipo: razao, numerador: receita_total, denominador: pedidos, formato: moeda}
  desconto_medio: {descricao: Desconto médio, tipo: media, coluna: desconto_pct, formato: numero, unidade: "%"}
  participacao_receita: {descricao: Fatia da receita, tipo: participacao, metrica: receita_total, formato: percentual}
  receita_por_dia: {descricao: Receita por dia, tipo: por_dia, metrica: receita_total, formato: moeda}
"""


def ler_vendas():
    with open(FIXTURES / "vendas.csv", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for l in linhas:
        l["receita"] = Decimal(l["receita"].replace(",", "."))
        l["data"] = date(int(l["data_pedido"][6:]), int(l["data_pedido"][3:5]), int(l["data_pedido"][:2]))
        l["regiao"] = l["regiao"] or None
    return linhas


VENDAS = ler_vendas()


def centavos(v):
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ProjetoVendas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.p = Path(cls._tmp.name)
        ingerir(cls.p, FIXTURES / "vendas.csv")
        perfilar(cls.p, "vendas")
        (cls.p / "modelo").mkdir()
        (cls.p / "modelo" / "metricas.yaml").write_text(MODELO_VENDAS, encoding="utf-8")
        modelo, arquivo, _ = carregar(cls.p)
        registrar_linhagem(cls.p, modelo, arquivo)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def por(self, resultado, dim):
        return {l[dim]: l for l in resultado["linhas"]}


class TestDezConsultas(ProjetoVendas):
    """As dez consultas do critério de aceite, cada uma contra o cálculo manual."""

    def test_1_receita_total(self):
        r = consultar(self.p, ["receita_total"])
        self.assertEqual(r["linhas"][0]["receita_total"], sum(l["receita"] for l in VENDAS))

    def test_2_receita_por_regiao_inclui_vazios(self):
        esperado = defaultdict(Decimal)
        for l in VENDAS:
            esperado[l["regiao"]] += l["receita"]
        r = self.por(consultar(self.p, ["receita_total"], ["regiao"]), "regiao")
        self.assertEqual({k: v["receita_total"] for k, v in r.items()}, dict(esperado))

    def test_3_pedidos_distintos_por_canal(self):
        esperado = defaultdict(set)
        for l in VENDAS:
            esperado[l["canal"]].add(l["pedido_id"])
        r = self.por(consultar(self.p, ["pedidos"], ["canal"]), "canal")
        self.assertEqual({k: v["pedidos"] for k, v in r.items()}, {k: len(v) for k, v in esperado.items()})

    def test_4_ticket_medio_por_canal(self):
        soma, pedidos = defaultdict(Decimal), defaultdict(set)
        for l in VENDAS:
            soma[l["canal"]] += l["receita"]
            pedidos[l["canal"]].add(l["pedido_id"])
        r = self.por(consultar(self.p, ["ticket_medio"], ["canal"]), "canal")
        for canal, linha in r.items():
            self.assertEqual(centavos(linha["ticket_medio"]), centavos(soma[canal] / len(pedidos[canal])))

    def test_5_participacao_por_categoria_soma_um(self):
        total = sum(l["receita"] for l in VENDAS)
        esperado = defaultdict(Decimal)
        for l in VENDAS:
            esperado[l["categoria"]] += l["receita"]
        r = self.por(consultar(self.p, ["participacao_receita"], ["categoria"]), "categoria")
        for cat, linha in r.items():
            self.assertAlmostEqual(linha["participacao_receita"], float(esperado[cat] / total), places=12)
        self.assertAlmostEqual(sum(l["participacao_receita"] for l in r.values()), 1.0, places=12)

    def test_6_receita_por_mes(self):
        esperado = defaultdict(Decimal)
        for l in VENDAS:
            esperado[l["data"].strftime("%Y-%m")] += l["receita"]
        r = consultar(self.p, ["receita_total"], ["mes"], ordenacao="cronologica")
        self.assertEqual([l["mes"] for l in r["linhas"]], sorted(esperado))
        self.assertEqual({l["mes"]: l["receita_total"] for l in r["linhas"]}, dict(esperado))

    def test_7_filtro_por_dimensao(self):
        esperado = defaultdict(int)
        for l in VENDAS:
            if l["canal"] in ("Site", "App"):
                esperado[l["data"].strftime("%Y-%m")] += 1
        r = consultar(self.p, ["registros"], ["mes"],
                      filtros=[{"dimensao": "canal", "operador": "em", "valores": ["Site", "App"]}])
        self.assertEqual({l["mes"]: l["registros"] for l in r["linhas"]}, dict(esperado))

    def test_8_trimestre_contra_trimestre_anterior(self):
        r = consultar(self.p, ["receita_total"], periodo="ultimo_trimestre", comparacao="periodo_anterior")
        self.assertEqual((r["periodo"]["inicio"], r["periodo"]["fim"]), ("2025-10-01", "2025-12-31"))
        self.assertEqual((r["comparacao"]["inicio"], r["comparacao"]["fim"]), ("2025-07-01", "2025-09-30"))
        atual = sum(l["receita"] for l in VENDAS if l["data"] >= date(2025, 10, 1))
        antes = sum(l["receita"] for l in VENDAS if date(2025, 7, 1) <= l["data"] <= date(2025, 9, 30))
        linha = r["linhas"][0]
        self.assertEqual(linha["receita_total"], atual)
        self.assertEqual(linha["receita_total__comparacao"], antes)
        self.assertEqual(linha["receita_total__variacao"], atual - antes)
        self.assertAlmostEqual(linha["receita_total__variacao_pct"], float((atual - antes) / antes), places=12)

    def test_9_receita_por_dia_por_mes(self):
        soma, dias = defaultdict(Decimal), defaultdict(list)
        for l in VENDAS:
            m = l["data"].strftime("%Y-%m")
            soma[m] += l["receita"]
            dias[m].append(l["data"])
        r = consultar(self.p, ["receita_por_dia"], ["mes"])
        for linha in r["linhas"]:
            n = (max(dias[linha["mes"]]) - min(dias[linha["mes"]])).days + 1
            self.assertEqual(centavos(linha["receita_por_dia"]), centavos(soma[linha["mes"]] / n))

    def test_10_metrica_com_filtro_e_media(self):
        r = consultar(self.p, ["receita_loja_fisica", "desconto_medio"])
        fisica = sum(l["receita"] for l in VENDAS if l["canal"] == "Loja física")
        media = Decimal(sum(int(l["desconto_pct"]) for l in VENDAS)) / len(VENDAS)
        self.assertEqual(r["linhas"][0]["receita_loja_fisica"], fisica)
        self.assertAlmostEqual(r["linhas"][0]["desconto_medio"], float(media), places=12)


class TestConsultaDetalhes(ProjetoVendas):
    def test_formatado_em_pt_br(self):
        r = consultar(self.p, ["receita_total", "pedidos", "participacao_receita"])
        f = r["formatado"][0]
        self.assertRegex(f["receita_total"], r"^R\$ \d{1,3}(\.\d{3})*,\d{2}$")
        self.assertRegex(f["pedidos"], r"^\d{1,3}(\.\d{3})*$")
        self.assertEqual(f["participacao_receita"], "100,0%")

    def test_dia_da_semana_em_ordem(self):
        r = consultar(self.p, ["registros"], ["dia_da_semana"], ordenacao="cronologica")
        self.assertEqual([l["dia_da_semana"] for l in r["linhas"]][:2], ["segunda", "terça"])
        esperado = defaultdict(int)
        for l in VENDAS:
            esperado[l["data"].isoweekday()] += 1
        self.assertEqual([l["registros"] for l in r["linhas"]], [esperado[i] for i in range(1, 8)])

    def test_maior_primeiro_e_limite(self):
        r = consultar(self.p, ["receita_total"], ["regiao"], ordenacao="maior_primeiro", limite=2)
        self.assertEqual(len(r["linhas"]), 2)
        self.assertGreaterEqual(r["linhas"][0]["receita_total"], r["linhas"][1]["receita_total"])

    def test_pedidos_invalidos_viram_mensagem(self):
        with self.assertRaises(ErroDeModelo) as ctx:
            consultar(self.p, ["nao_existe"], ["mes"], periodo="tudo", comparacao="periodo_anterior")
        texto = " ".join(ctx.exception.detalhes)
        self.assertIn("não existe no modelo", texto)
        self.assertIn("período definido", texto)
        self.assertIn("dimensão de tempo", texto)

    def test_definicao_acompanha_o_resultado(self):
        r = consultar(self.p, ["ticket_medio"])
        self.assertEqual(r["definicoes"]["ticket_medio"]["definicao"], "receita_total dividido por pedidos")


class TestLinhagem(ProjetoVendas):
    def test_cada_metrica_tem_definicao_e_origem(self):
        m = ler_manifesto(self.p)
        sha = hashlib.sha256((self.p / "saidas/bi/tabelas/vendas.parquet").read_bytes()).hexdigest()
        modelo_sha = hashlib.sha256((self.p / "modelo/metricas.yaml").read_bytes()).hexdigest()
        self.assertEqual(set(m["metricas"]), {"receita_total", "receita_loja_fisica", "registros", "pedidos",
                                              "ticket_medio", "desconto_medio", "participacao_receita",
                                              "receita_por_dia"})
        for nome, l in m["metricas"].items():
            self.assertTrue(l["definicao"], nome)
            self.assertTrue(l["descricao"], nome)
            self.assertEqual(l["fonte"]["sha256"], sha, nome)
            self.assertEqual(l["modelo_sha256"], modelo_sha, nome)
        self.assertEqual(m["metricas"]["receita_loja_fisica"]["definicao"], "soma de receita onde canal = Loja física")
        self.assertEqual(m["metricas"]["ticket_medio"]["colunas"], ["pedido_id", "receita"])
        self.assertEqual(m["eventos"][-1]["evento"], "modelo_validado")


class TestCubo(ProjetoVendas):
    def test_cubo_reagrega_igual_a_consulta(self):
        info = exportar_cubo(self.p, "vendas", ["receita_total", "ticket_medio", "participacao_receita"],
                             ["regiao", "canal", "mes"])
        self.assertTrue(info["dentro_da_meta"])
        self.assertEqual(info["nao_reagregaveis"], ["ticket_medio"])
        cubo = json.loads((self.p / info["arquivo"]).read_text(encoding="utf-8"))
        soma = defaultdict(float)
        for l in cubo["linhas"]:
            soma[l["regiao"]] += l["receita_total__soma"]
        r = self.por(consultar(self.p, ["receita_total"], ["regiao"]), "regiao")
        for regiao, linha in r.items():
            self.assertEqual(centavos(soma[regiao]), centavos(linha["receita_total"]))
        self.assertEqual(cubo["metricas"]["participacao_receita"]["receita"]["operacao"], "participacao")
        self.assertNotIn("valor", json.dumps(cubo["metricas"]["receita_total"]["receita"]))

    def test_cubo_com_comparacao_marca_os_periodos(self):
        info = exportar_cubo(self.p, "trimestre", ["receita_total"], ["regiao"], "ultimo_trimestre", "periodo_anterior")
        cubo = json.loads((self.p / info["arquivo"]).read_text(encoding="utf-8"))
        self.assertEqual({l["_periodo"] for l in cubo["linhas"]}, {"atual", "comparacao"})
        self.assertEqual(cubo["periodo"]["comparacao"], {"inicio": "2025-07-01", "fim": "2025-09-30"})


class TestValidacaoDoModelo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = Path(self._tmp.name)
        ingerir(self.p, FIXTURES / "vendas.csv")
        (self.p / "modelo").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def problemas(self, yaml_texto):
        (self.p / "modelo" / "metricas.yaml").write_text(yaml_texto, encoding="utf-8")
        with self.assertRaises(ErroDeModelo) as ctx:
            carregar(self.p)
        return " | ".join(ctx.exception.detalhes)

    def test_erros_comuns(self):
        texto = self.problemas("""
versao: "0.1"
fonte: {tabela: vendas}
dimensoes:
  mes: {coluna: canal, granularidade: mes}
metricas:
  receita_2025: {descricao: x, tipo: soma, coluna: receita, formato: moeda}
  soma_texto: {descricao: x, tipo: soma, coluna: canal, formato: moeda}
  sem_descricao: {tipo: contagem, formato: inteiro}
  coluna_errada: {descricao: x, tipo: soma, coluna: faturamento, formato: moeda}
  a: {descricao: x, tipo: razao, numerador: b, denominador: soma_texto, formato: decimal}
  b: {descricao: x, tipo: razao, numerador: a, denominador: soma_texto, formato: decimal}
  por_dia_sem_data: {descricao: x, tipo: por_dia, metrica: soma_texto, formato: moeda}
""")
        for trecho in ("sem algarismos", "precisa de coluna numérica", "descricao: obrigatória",
                       "'faturamento' não existe", "referência circular", "granularidade só vale",
                       "precisa de fonte.coluna_data"):
            self.assertIn(trecho, texto)

    def test_yaml_quebrado(self):
        (self.p / "modelo" / "metricas.yaml").write_text("versao: [", encoding="utf-8")
        with self.assertRaises(ErroDeModelo) as ctx:
            carregar(self.p)
        self.assertIn("YAML válido", ctx.exception.mensagem)


class TestProposta(unittest.TestCase):
    def test_rascunhos_dos_tres_dominios_validam(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            for arq in ("vendas.csv", "marketing.xlsx", "financeiro.csv"):
                ingerir(p, FIXTURES / arq)
            for tabela in ("vendas", "marketing", "financeiro"):
                r = propor(p, tabela, sobrescrever=True)
                self.assertEqual(r["problemas"], [], tabela)
                carregar(p)
            r = propor(p, "vendas", sobrescrever=True)
            self.assertIn("preco_unitario_medio", r["metricas"])
            self.assertNotIn("preco_unitario_total", r["metricas"])
            self.assertIn("participacao_receita_total", r["metricas"])
            with self.assertRaises(ErroDeModelo):
                propor(p, "vendas")


class TestCicloComAnalise(unittest.TestCase):
    """Projeto da análise: reproduz um achado da conclusão pela camada de métricas."""

    def test_modelo_sobre_os_dados_tratados(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "projeto"
            shutil.copytree(EXEMPLO, p)
            self.assertEqual(estado(p)["etapa"], "metricas")
            r = propor(p)
            self.assertEqual(r["fonte"], {"arquivo": "saidas/dados_tratados.parquet", "coluna_data": "data"})
            modelo, arquivo, _ = carregar(p)
            self.assertEqual(modelo["dimensoes"]["regiao"]["descricao"], "região do cliente")
            registrar_linhagem(p, modelo, arquivo)
            self.assertEqual(estado(p)["etapa"], "design")
            # a conclusão diz "o Sudeste concentra cerca de 39% do faturamento"
            linhas = {l["regiao"]: l for l in consultar(p, ["participacao_faturamento_total"], ["regiao"])["linhas"]}
            self.assertEqual(round(100 * linhas["Sudeste"]["participacao_faturamento_total"]), 39)


class TestPeriodos(unittest.TestCase):
    def test_janelas(self):
        fim = date(2025, 12, 31)
        self.assertEqual(resolver_periodo("ultimo_mes", fim), (date(2025, 12, 1), fim))
        self.assertEqual(resolver_periodo("ultimo_ano_completo", fim), (date(2025, 1, 1), fim))
        self.assertEqual(resolver_periodo("ultimo_ano_completo", date(2025, 6, 30)), (date(2024, 1, 1), date(2024, 12, 31)))
        self.assertEqual(resolver_periodo("ultimos_trinta_dias", fim), (date(2025, 12, 2), fim))
        self.assertEqual(periodo_de_comparacao("ultimo_mes", (date(2025, 3, 1), date(2025, 3, 31)), "periodo_anterior"),
                         (date(2025, 2, 1), date(2025, 2, 28)))
        self.assertEqual(periodo_de_comparacao("ultimo_mes", (date(2025, 3, 1), date(2025, 3, 15)), "periodo_anterior"),
                         (date(2025, 2, 1), date(2025, 2, 15)))
        self.assertEqual(periodo_de_comparacao("ano_corrente", (date(2025, 1, 1), date(2025, 8, 10)),
                                               "mesmo_periodo_ano_anterior"), (date(2024, 1, 1), date(2024, 8, 10)))

    def test_formatar(self):
        self.assertEqual(formatar(2148900.5, "moeda"), "R$ 2.148.900,50")
        self.assertEqual(formatar(-1234.5, "moeda"), "-R$ 1.234,50")
        self.assertEqual(formatar(0.3912, "percentual"), "39,1%")
        self.assertEqual(formatar(16254, "inteiro"), "16.254")
        self.assertEqual(formatar(4.5, "numero", "%"), "4,5 %")
        self.assertEqual(formatar(None, "moeda"), "—")


if __name__ == "__main__":
    unittest.main()
