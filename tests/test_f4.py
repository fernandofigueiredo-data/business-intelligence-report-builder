"""
Testes da fase F4: dashboard e publicação.

Critério de aceite: os três conjuntos renderizam sem erro; a spec não contém números
(inspeção do JSON); o HTML tem menos de 5 MB e respeita o contrato de página dos
Artifacts. A checagem visual a 375px foi feita no navegador (ver o PR); aqui fica o
que dá para conferir sem navegador, incluindo os números contra o cálculo manual.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import csv, json, re, shutil, sys, tempfile, unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
FIXTURES = RAIZ / "fixtures"
sys.path.insert(0, str(PLUGIN / "lib"))
sys.path.insert(0, str(RAIZ / "exemplos"))
from construir import construir  # noqa: E402
from bi_html.consulta import consultar  # noqa: E402
from bi_html.dashboard import ErroDeDashboard, TODOS, VAZIO, checar_spec, montar  # noqa: E402
from bi_html.design import aplicar_estilo  # noqa: E402
from bi_html.ingestao import ingerir  # noqa: E402
from bi_html.modelo import carregar, registrar_linhagem  # noqa: E402
from bi_html.perfil import perfilar  # noqa: E402
from bi_html.render import ECHARTS, renderizar  # noqa: E402

NOMES = ("vendas", "marketing", "financeiro")


def numeros_na_spec(spec):
    """Todo número ou algarismo da spec, fora a versão do formato."""
    achados = []

    def andar(no, caminho):
        if isinstance(no, dict):
            for k, v in no.items():
                if caminho == "" and k == "versao_spec":
                    continue
                andar(v, f"{caminho}.{k}")
        elif isinstance(no, list):
            for i, v in enumerate(no):
                andar(v, f"{caminho}[{i}]")
        elif isinstance(no, bool) or no is None:
            return
        elif isinstance(no, (int, float)) or re.search(r"\d", str(no)):
            achados.append((caminho, no))

    andar(spec, "")
    return achados


class Exemplos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.projetos, cls.resultados = {}, {}
        for nome in NOMES:
            p = Path(cls._tmp.name) / nome
            shutil.copytree(RAIZ / "exemplos" / nome / "modelo", p / "modelo")
            shutil.copytree(RAIZ / "exemplos" / nome / "dashboard", p / "dashboard")
            cls.projetos[nome] = p
            cls.resultados[nome] = construir(nome, p)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class TestCriteriosDeAceite(Exemplos):
    def test_tres_conjuntos_renderizam(self):
        for nome, r in self.resultados.items():
            self.assertTrue((self.projetos[nome] / r["html"]).is_file(), nome)
            self.assertTrue((self.projetos[nome] / r["artifact"]).is_file(), nome)
            self.assertEqual(r["avisos"], [], nome)
            self.assertEqual(r["publicacao_bloqueada"], [], nome)

    def test_spec_sem_numeros(self):
        for nome in NOMES:
            spec = json.loads((RAIZ / "exemplos" / nome / "dashboard" / "spec.json").read_text(encoding="utf-8"))
            self.assertEqual(numeros_na_spec(spec), [], nome)
        exemplo = json.loads((PLUGIN / "modelo" / "exemplos" / "spec-vendas.json").read_text(encoding="utf-8"))
        self.assertEqual(numeros_na_spec(exemplo), [])

    def test_abaixo_de_cinco_mega(self):
        for nome, r in self.resultados.items():
            self.assertTrue(r["dentro_da_meta"], nome)
            self.assertLess((self.projetos[nome] / r["html"]).stat().st_size, 5 * 1024 * 1024, nome)


class TestContratoDePagina(Exemplos):
    def test_fragmento_para_artifact(self):
        for nome, r in self.resultados.items():
            frag = (self.projetos[nome] / r["artifact"]).read_text(encoding="utf-8")
            self.assertTrue(frag.startswith("<title>"), nome)
            self.assertLess(frag.index("</title>"), 8192)
            for proibido in (r"<!doctype", r"<html[\s>]", r"<head[\s>]", r"<body[\s>]"):
                self.assertIsNone(re.search(proibido, frag.lower()), (nome, proibido))
            self.assertIn('<meta name="claude:viewport-fit-sides" content="cover">', frag)
            self.assertIn("padding-left: max(16px, env(safe-area-inset-left, 0px))", frag)
            self.assertIn(':root:not([data-theme="light"])', frag)
            self.assertIn(':root[data-theme="dark"]', frag)
            self.assertIn("body { margin: 0; background: var(--background)", frag)
            self.assertIn(f'<script src="{ECHARTS}"></script>', frag)
            externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', frag)
            for url in externos:
                self.assertTrue(url.startswith(("https://cdnjs.cloudflare.com/", "https://fonts.googleapis.com/")), url)

    def test_documento_completo_abre_sozinho(self):
        html = (self.projetos["vendas"] / self.resultados["vendas"]["html"]).read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn('<html lang="pt-BR">', html)
        self.assertIn("viewport-fit=cover", html)

    def test_dados_embutidos_nao_quebram_o_script(self):
        frag = (self.projetos["vendas"] / self.resultados["vendas"]["artifact"]).read_text(encoding="utf-8")
        bloco = frag.split('<script type="application/json" id="dados-bi">', 1)[1].split("</script>", 1)[0]
        self.assertNotIn("</", bloco)
        json.loads(bloco)


def vendas_csv():
    with open(FIXTURES / "vendas.csv", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for l in linhas:
        l["receita"] = Decimal(l["receita"].replace(",", "."))
    return linhas


class TestNumerosDoDashboard(Exemplos):
    """O que o navegador mostra é busca direta: confere contra o cálculo manual e contra consultar()."""

    def bloco(self, nome, bid):
        m = montar(self.projetos[nome])
        return next(b for b in m["blocos"] if b["id"] == bid), m

    def test_faturamento_total_e_com_filtros(self):
        vendas = vendas_csv()
        b, m = self.bloco("vendas", "faturamento")
        self.assertEqual([f["dimensao"] for f in m["filtros"]], ["canal", "regiao"])
        total = b["dados"][f"{TODOS}|{TODOS}"]["linhas"][0]["receita_total"]
        self.assertAlmostEqual(total, float(sum(l["receita"] for l in vendas)), places=2)
        site = b["dados"][f"Site|{TODOS}"]["linhas"][0]["receita_total"]
        self.assertAlmostEqual(site, float(sum(l["receita"] for l in vendas if l["canal"] == "Site")), places=2)
        sul_app = b["dados"]["App|Sul"]["linhas"][0]["receita_total"]
        self.assertAlmostEqual(sul_app, float(sum(l["receita"] for l in vendas if l["canal"] == "App" and l["regiao"] == "Sul")), places=2)
        sem_regiao = b["dados"][f"{TODOS}|{VAZIO}"]["linhas"][0]["receita_total"]
        self.assertAlmostEqual(sem_regiao, float(sum(l["receita"] for l in vendas if not l["regiao"])), places=2)

    def test_pedidos_distintos_nao_sao_somados_entre_filtros(self):
        vendas = vendas_csv()
        b, _ = self.bloco("vendas", "apoio")
        for canal in ("Loja física", "Site", "App"):
            esperado = len({l["pedido_id"] for l in vendas if l["canal"] == canal})
            self.assertEqual(b["dados"][f"{canal}|{TODOS}"]["linhas"][0]["pedidos"], esperado)

    def test_ranking_de_lojas_sem_centro_de_distribuicao(self):
        b, _ = self.bloco("vendas", "lojas")
        linhas = b["dados"][f"{TODOS}|{TODOS}"]["linhas"]
        self.assertNotIn("Centro de distribuição", [l["loja"] for l in linhas])
        self.assertEqual(len(linhas), 10)
        valores = [l["receita_total"] for l in linhas]
        self.assertEqual(valores, sorted(valores, reverse=True))

    def test_filtro_que_tambem_e_dimensao_do_bloco(self):
        b, _ = self.bloco("vendas", "regioes")
        linhas = b["dados"][f"{TODOS}|{TODOS}"]["linhas"]
        self.assertEqual({l["regiao"] for l in linhas}, {"Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte", VAZIO})
        self.assertEqual(set(b["dados"]), {f"{c}|{TODOS}" for c in (TODOS, "Loja física", "Site", "App")})

    def test_participacao_por_filtro_soma_um(self):
        b, _ = self.bloco("vendas", "regioes")
        for chave in (f"{TODOS}|{TODOS}", f"Site|{TODOS}"):
            soma = sum(l["participacao_receita"] for l in b["dados"][chave]["linhas"])
            self.assertAlmostEqual(soma, 1.0, places=9)
        total = b["dados"][f"{TODOS}|{TODOS}"]["total"]
        self.assertAlmostEqual(total["participacao_receita"], 1.0, places=9)

    def test_comparacao_bate_com_consultar(self):
        b, _ = self.bloco("marketing", "receita")
        linha = b["dados"][TODOS]["linhas"][0]
        r = consultar(self.projetos["marketing"], ["receita_atribuida"], periodo="ultimo_trimestre",
                      comparacao="periodo_anterior")["linhas"][0]
        self.assertAlmostEqual(linha["receita_atribuida"], float(r["receita_atribuida"]), places=2)
        self.assertAlmostEqual(linha["receita_atribuida__comparacao"], float(r["receita_atribuida__comparacao"]), places=2)
        self.assertAlmostEqual(linha["receita_atribuida__variacao_pct"], r["receita_atribuida__variacao_pct"], places=9)
        self.assertEqual(b["comparacao_periodo"], {"inicio": "01/07/2025", "fim": "30/09/2025"})

    def test_cascata_fecha_no_resultado(self):
        b, m = self.bloco("financeiro", "cascata")
        dados = b["dados"][TODOS]
        soma = sum(l["resultado_realizado"] for l in dados["linhas"])
        self.assertAlmostEqual(soma, dados["total"]["resultado_realizado"], places=2)
        self.assertEqual(m["periodo"]["rotulo"], "01/01/2025 a 31/12/2025")
        self.assertEqual(dados["linhas"][0]["grupo"], "Receita")

    def test_competencia_mensal_compara_com_o_ano_anterior(self):
        b, _ = self.bloco("financeiro", "resultado")
        self.assertEqual(b["comparacao_periodo"], {"inicio": "01/01/2024", "fim": "31/12/2024"})
        self.assertIsNotNone(b["dados"][TODOS]["linhas"][0]["resultado_realizado__comparacao"])

    def test_direcao_da_metrica_vai_para_a_pagina(self):
        _, m = self.bloco("marketing", "eficiencia")
        self.assertEqual(m["metricas"]["custo_por_conversao"]["melhor"], "menor")
        self.assertEqual(m["metricas"]["investimento"]["melhor"], "maior")


class TestSpecInvalida(Exemplos):
    def test_regras_de_forma_dos_blocos(self):
        modelo, _, _ = carregar(self.projetos["vendas"])
        spec = json.loads((RAIZ / "exemplos/vendas/dashboard/spec.json").read_text(encoding="utf-8"))
        spec["periodo"] = "tudo"
        spec["filtros_globais"] = ["mes", "nao_existe"]
        spec["blocos"][0]["comparacao"] = "meta"
        spec["blocos"][1]["dimensoes"] = ["regiao"]
        spec["blocos"][2]["dimensoes"] = ["regiao"]
        spec["blocos"][3]["comparacao"] = "periodo_anterior"
        texto = " | ".join(checar_spec(spec, modelo))
        for trecho in ("dimensão de tempo; use o período", "'nao_existe' não existe", "meta ainda não",
                       "faixa_kpis não leva dimensões", "deve ser de tempo", "precisa de um período definido"):
            self.assertIn(trecho, texto)

    def test_render_sem_spec_explica(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            shutil.copytree(RAIZ / "exemplos/vendas/modelo", p / "modelo")
            ingerir(p, FIXTURES / "vendas.csv")
            with self.assertRaises(ErroDeDashboard) as ctx:
                renderizar(p)
            self.assertIn("spec.json", ctx.exception.mensagem)


class TestPublicacaoBloqueada(unittest.TestCase):
    def test_dados_pessoais_bloqueiam_a_publicacao(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            ingerir(p, FIXTURES / "clientes_ficticios.csv")
            perfilar(p, "clientes_ficticios")
            (p / "modelo").mkdir()
            (p / "modelo/metricas.yaml").write_text(
                'versao: "0.1"\nfonte: {tabela: clientes_ficticios, coluna_data: data_cadastro}\n'
                "dimensoes:\n  uf: {coluna: uf, descricao: UF}\n"
                "metricas:\n  clientes: {descricao: Clientes, tipo: contagem, formato: inteiro}\n", encoding="utf-8")
            modelo, arquivo, _ = carregar(p)
            registrar_linhagem(p, modelo, arquivo)
            aplicar_estilo(p, "claro")
            (p / "dashboard").mkdir()
            (p / "dashboard/spec.json").write_text(json.dumps({
                "versao_spec": "0.1", "titulo": "Clientes por estado", "pergunta_negocio": "Onde estão os clientes?",
                "estilo": {"fonte": "padrao", "tokens": "design/tokens.json"}, "layout": "duas_colunas",
                "periodo": "tudo", "blocos": [{"id": "mapa", "tipo": "mapa_uf", "titulo": "Clientes por estado",
                                              "metricas": ["clientes"], "dimensoes": ["uf"]}]}), encoding="utf-8")
            r = renderizar(p)
            self.assertTrue(r["publicacao_bloqueada"])
            self.assertIn("cpf", r["publicacao_bloqueada"][0])


if __name__ == "__main__":
    unittest.main()
