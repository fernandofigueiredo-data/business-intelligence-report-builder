"""
Testes da fase F7: conversão de .pbix em importação (Fluxo 2, via (a)).

Critério de aceite: contagem de linhas idêntica por tabela; todas as medidas classificadas; as
traduzidas batem com a avaliação de referência numa amostra de contextos; relatório de fidelidade
por visual.

- Tradutor de DAX, textos sem algarismos e leitura do relatório (PBIR e legado): sem dependências.
- Conversão de ponta a ponta do .pbix fictício (fixtures/vendas.pbix) e recusa do DirectQuery: roda
  o processo de leitura (pbix-mcp e pbixray, via uv); pula se o uv não estiver instalado.
- Resultado com os arquivos reais (provas/f7): confere o que executar.py gravou.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import json, re, shutil, sys, tempfile, unittest, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
sys.path.insert(0, str(PLUGIN / "lib"))
from bi_html import dax  # noqa: E402
from bi_html.conversao import ErroDeConversao, Nomes, converter, ident, ler_relatorio, sem_algarismos  # noqa: E402

COLUNAS = {"Vendas": {"receita": "Float64", "pedido": "string", "canal": "string", "qtd": "Int64", "preco": "Float64",
                      "loja": "string", "custo": "Float64"},
           "Lojas": {"loja": "string", "uf": "string", "regiao": "string"},
           "Metas": {"meta": "Float64"}}


def alcance(t):
    return {"Vendas": {"Vendas", "Lojas"}, "Lojas": {"Lojas"}, "Metas": {"Metas"}}[t]


def traduzir(expressao, extras=None):
    medidas = {"Receita": "SUM(Vendas[receita])", "Pedidos": "DISTINCTCOUNT(Vendas[pedido])", **(extras or {}),
               "X": expressao}
    return dax.Tradutor(medidas, COLUNAS, alcance).traduzir("X")


class TestTradutor(unittest.TestCase):
    def test_agregacoes(self):
        for expr, tipo in (("SUM(Vendas[receita])", "soma"), ("AVERAGE(Vendas[receita])", "media"),
                           ("MIN(Vendas[receita])", "minimo"), ("MAX(Vendas[receita])", "maximo"),
                           ("DISTINCTCOUNT(Vendas[pedido])", "contagem_distinta"), ("COUNTROWS(Vendas)", "contagem")):
            r = traduzir(expr)
            self.assertEqual(r["classe"], "traduzida", expr)
            self.assertEqual((r["no"]["no"], r["no"]["tipo"], r["no"]["fato"]), ("base", tipo, "Vendas"))

    def test_razao_e_escala(self):
        r = traduzir("DIVIDE([Receita], [Pedidos])")
        self.assertEqual(r["no"]["no"], "razao")
        self.assertEqual((r["no"]["num"]["ref"], r["no"]["den"]["ref"]), ("Receita", "Pedidos"))
        r = traduzir("DIVIDE([Receita], 1000)")
        self.assertEqual((r["no"]["no"], r["no"]["fator"], r["no"]["base"]["ref"]), ("escala", 0.001, "Receita"))
        self.assertEqual(traduzir("[Receita] * 100")["no"]["fator"], 100.0)
        self.assertEqual(traduzir("DIVIDE([Receita], [Pedidos], 0)")["classe"], "nao_traduzida")

    def test_calculate_vira_filtro(self):
        r = traduzir('CALCULATE([Receita], Vendas[canal] = "Site", Lojas[uf] IN {"SP", "RJ"}, NOT ISBLANK(Vendas[qtd]))')
        self.assertEqual(r["classe"], "traduzida")
        self.assertEqual(r["no"]["filtro"], [
            {"coluna": "Vendas.canal", "operador": "igual", "valor": "Site"},
            {"coluna": "Lojas.uf", "operador": "em", "valores": ["SP", "RJ"]},
            {"coluna": "Vendas.qtd", "operador": "preenchido"}])
        self.assertIn(dax.RESSALVA_CALCULATE, r["ressalvas"])
        sem = traduzir('CALCULATE([Receita], KEEPFILTERS(Vendas[canal] <> "Site"), 0 < Vendas[qtd])')
        self.assertEqual([f["operador"] for f in sem["no"]["filtro"]], ["diferente", "maior"])
        self.assertEqual(traduzir("CALCULATE([Receita], Metas[meta] > 0)")["classe"], "nao_traduzida")

    def test_iteradores_e_soma_de_medidas(self):
        r = traduzir("SUMX(Vendas, Vendas[qtd] * Vendas[preco])")
        self.assertEqual(r["no"]["calc"], '("Vendas.qtd" * "Vendas.preco")')
        r = traduzir("AVERAGEX(FILTER(Vendas, Vendas[qtd] > 0), DIVIDE(Vendas[receita], Vendas[qtd]))")
        self.assertEqual((r["no"]["tipo"], r["no"]["filtro"][0]["operador"]), ("media", "maior"))
        self.assertIn("NULLIF", r["no"]["calc"])
        r = traduzir("[Receita] - SUM(Vendas[custo])")
        self.assertIn("COALESCE", r["no"]["calc"])
        self.assertEqual(traduzir("[Receita] - [Pedidos]")["classe"], "nao_traduzida")

    def test_participacao_guarda_o_eixo(self):
        r = traduzir("DIVIDE([Receita], CALCULATE([Receita], ALLSELECTED(Lojas[uf])))")
        self.assertEqual((r["no"]["no"], r["no"]["eixo"]), ("participacao", ["Lojas.uf"]))
        self.assertEqual(traduzir("CALCULATE([Receita], ALLSELECTED(Vendas))")["classe"], "nao_traduzida")

    def test_var_return(self):
        r = traduzir("VAR total = [Receita] VAR n = [Pedidos] RETURN DIVIDE(total, n)")
        self.assertEqual(r["no"]["no"], "razao")

    def test_texto_e_motivos(self):
        self.assertEqual(traduzir('FORMAT([Receita], "#,0")')["classe"], "texto")
        self.assertEqual(traduzir('IF([Receita] > 0, "#00AA00", "#AA0000")')["classe"], "texto")
        r = traduzir("CALCULATE([Receita], REMOVEFILTERS(Lojas))")
        self.assertEqual(r["classe"], "nao_traduzida")
        self.assertIn("REMOVEFILTERS", r["motivo"])
        r = traduzir("RANKX(ALLSELECTED(Lojas[loja]), [Receita])")
        self.assertIn("RANKX", r["motivo"])
        r = traduzir("DIVIDE([Fora], [Pedidos])", {"Fora": "TOTALYTD([Receita], Vendas[canal])"})
        self.assertEqual(r["motivo"], "depende de [Fora], que não foi traduzida")
        self.assertEqual(traduzir("SUM(Vendas[inexistente])")["classe"], "nao_traduzida")

    def test_analisador(self):
        arvore = dax.analisar("-- comentário\nCALCULATE ( [M], 'Tabela X'[Col] = \"a\"\"b\" ) /* fim */")
        self.assertEqual(arvore[0:2], ("call", "CALCULATE"))
        self.assertEqual(arvore[2][1], ("bin", "=", ("col", "Tabela X", "Col"), ("str", 'a"b')))
        with self.assertRaises(dax.ErroDeDax):
            dax.analisar("SUM(Vendas[receita]")


class TestTextos(unittest.TestCase):
    def test_sem_algarismos(self):
        self.assertEqual(sem_algarismos("Do 1º ao 2º turno"), "Do primeiro ao segundo turno")
        self.assertEqual(sem_algarismos("Top 10 lojas"), "Top dez lojas")
        self.assertEqual(sem_algarismos("Lab1"), "Lab um")
        self.assertEqual(sem_algarismos("Eleição 2022"), "Eleição dois mil e vinte e dois")
        self.assertNotRegex(sem_algarismos("Receita 1.234 (R$ 56)"), r"\d")

    def test_ids(self):
        self.assertEqual(ident("% Votos Válidos 1º Turno"), "pct_votos_validos_primeiro_turno")
        nomes = Nomes()
        self.assertEqual([nomes.novo("Receita"), nomes.novo("receita"), nomes.novo("Receita!")],
                         ["receita", "receita_b", "receita_c"])
        for i in ("x", "Ativo Total(R$ mil)", "123"):
            self.assertRegex(ident(i), r"^[a-z][a-z_]{0,47}$")


def _pbir_minimo(destino: Path) -> Path:
    visual = {"name": "v1", "position": {"x": 0, "y": 0, "width": 600, "height": 300}, "visual": {
        "visualType": "clusteredBarChart",
        "query": {"queryState": {
            "Category": {"projections": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Vendas"}},
                                                               "Property": "loja"}}}]},
            "Y": {"projections": [{"field": {"Aggregation": {"Expression": {"Column": {
                "Expression": {"SourceRef": {"Entity": "Vendas"}}, "Property": "receita"}}, "Function": 0}}}]}},
            "sortDefinition": {"sort": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Vendas"}},
                                                              "Property": "loja"}}, "direction": "Ascending"}]}},
        "visualContainerObjects": {"title": [{"properties": {"text": {"expr": {"Literal": {"Value": "'Receita por loja'"}}}}}]}}}
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("Report/definition/report.json", json.dumps({"themeCollection": {
            "customTheme": {"name": "Meu tema.json", "type": "RegisteredResources"}}}))
        z.writestr("Report/StaticResources/RegisteredResources/Meu tema.json", json.dumps({"name": "Meu tema",
                                                                                             "dataColors": ["#123456"]}))
        z.writestr("Report/definition/pages/pages.json", json.dumps({"pageOrder": ["p1", "p2"]}))
        z.writestr("Report/definition/pages/p1/page.json", json.dumps({"displayName": "Página 1", "width": 1200}))
        z.writestr("Report/definition/pages/p1/visuals/v1/visual.json", json.dumps(visual))
        z.writestr("Report/definition/pages/p2/page.json", json.dumps({"displayName": "Dica", "type": "Tooltip"}))
    return destino


class TestRelatorio(unittest.TestCase):
    def test_pbir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = ler_relatorio(_pbir_minimo(Path(tmp) / "r.pbix"))
        self.assertEqual(r["formato"], "PBIR")
        self.assertEqual([p["nome"] for p in r["paginas"]], ["Página 1", "Dica"])
        self.assertTrue(r["paginas"][1]["oculta"])
        v = r["paginas"][0]["visuais"][0]
        self.assertEqual((v["tipo"], v["titulo"], v["ordem"]), ("clusteredBarChart", "Receita por loja",
                                                                {"por": "eixo", "descendente": False}))
        self.assertEqual(v["campos"][1], {"papel": "Y", "tipo": "agregacao", "tabela": "Vendas", "coluna": "receita",
                                          "funcao": 0})
        self.assertEqual(r["tema"]["nome"], "Meu tema.json")
        self.assertIn("#123456", r["tema"]["json"])

    def test_legado(self):
        r = ler_relatorio(RAIZ / "fixtures" / "vendas.pbix")
        self.assertEqual(r["formato"], "legado (Report/Layout)")
        visuais = r["paginas"][0]["visuais"]
        self.assertEqual(len(visuais), 11)
        tabela = next(v for v in visuais if v["tipo"] == "tableEx")
        self.assertEqual([c["tipo"] for c in tabela["campos"]], ["coluna", "medida", "medida", "agregacao"])
        self.assertEqual(tabela["campos"][3]["funcao"], 1)
        self.assertEqual(next(v for v in visuais if v["tipo"] == "filledMap")["campos"][0]["tabela"], "Lojas")


@unittest.skipUnless(shutil.which("uv"), "a conversão de ponta a ponta precisa do uv (processo de leitura do .pbix)")
class TestConversaoDePontaAPonta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.p = Path(cls._tmp.name) / "projeto"
        cls.p.mkdir()
        cls.r = converter(cls.p, RAIZ / "fixtures" / "vendas.pbix")
        cls.rel = json.loads((cls.p / "saidas" / "bi" / "pbix" / "conversao.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_linhas_identicas_por_tabela(self):
        self.assertTrue(self.r["tabelas_iguais"])
        vendas = next(t for t in self.rel["tabelas"] if t["tabela"] == "Vendas")
        self.assertEqual((vendas["linhas_metadados"], vendas["linhas_extraidas"], vendas["linhas_no_plano"]),
                         (16254, 16254, 16254))

    def test_todas_as_medidas_classificadas(self):
        classes = {m["medida"]: m["classe"] for m in self.rel["medidas"]}
        self.assertEqual(sum(1 for c in classes.values() if c != "implicita"), 14)
        self.assertEqual(classes["Receita de Todas as Lojas"], "nao_traduzida")
        self.assertEqual(classes["Receita Acumulada no Ano"], "nao_traduzida")
        self.assertEqual(classes["Rótulo da Receita"], "texto")
        self.assertEqual(classes["Média de desconto_pct"], "implicita")
        for m in self.rel["medidas"]:
            if m["classe"] in ("texto", "nao_traduzida"):
                self.assertTrue(m["motivo"], m["medida"])

    def test_traduzidas_batem_com_o_power_bi(self):
        por_medida = self.rel["equivalencia"]["por_medida"]
        traduzidas = [m["medida"] for m in self.rel["medidas"] if m["classe"] == "traduzida"]
        self.assertEqual(len(traduzidas), 11)
        validadas = sorted(n for n in traduzidas if por_medida[n]["validada"])
        self.assertEqual(sorted(set(traduzidas) - set(validadas)), ["Receita Site"])
        self.assertGreaterEqual(sum(por_medida[n]["contextos"] for n in traduzidas), 40)
        # a divergência é a ressalva do CALCULATE: o filtro de canal do leitor não é substituído
        caso = next(c for c in self.rel["equivalencia"]["casos"] if c["medida"] == "Receita Site" and not c["bate"])
        self.assertIn("Vendas.canal", caso["contexto"])
        self.assertIn("Receita Site (não validada)", (self.p / "modelo" / "metricas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(por_medida["Participação da UF"]["contextos"], 2)
        self.assertTrue(por_medida["Receita (R$ mil)"]["validada"])

    def test_fidelidade_por_visual(self):
        visuais = self.rel["paginas"][0]["visuais"]
        self.assertEqual(len(visuais), 11)
        status = {v["titulo"]: v["status"] for v in visuais if v["titulo"]}
        self.assertEqual(status["Faturamento"], "convertido")
        self.assertEqual(status["Receita por UF"], "convertido")
        self.assertEqual(status["Receita acumulada"], "nao_convertido")
        self.assertTrue(all(v["status"] for v in visuais))
        md = (self.p / "saidas" / "bi" / "pbix" / "fidelidade.md").read_text(encoding="utf-8")
        self.assertIn("usa TOTALYTD", md)

    def test_specs_e_paginas(self):
        from bi_html.dashboard import checar_spec
        from bi_html.modelo import carregar

        modelo, _, _ = carregar(self.p)
        spec = json.loads((self.p / "dashboard" / "spec.json").read_text(encoding="utf-8"))
        self.assertEqual(checar_spec(spec, modelo), [])
        self.assertEqual(spec["origem"], "pbix")
        self.assertEqual(spec["filtros_globais"], ["regiao"])
        textos = [spec[k] for k in ("titulo", "subtitulo", "pergunta_negocio", "notas")] + [b["titulo"] for b in spec["blocos"]]
        self.assertFalse([t for t in textos if re.search(r"\d", t)])
        self.assertTrue((self.p / "saidas" / "bi" / "dashboard.html").is_file())
        self.assertTrue((self.p / "saidas" / "bi" / "paginas" / "visao_geral.html").is_file())
        self.assertEqual(self.r["publicacao_bloqueada"], [])

    def test_directquery_recusado(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ErroDeConversao) as e:
            converter(Path(tmp), RAIZ / "fixtures" / "vendas_directquery.pbix")
        self.assertIn("DirectQuery", e.exception.mensagem)
        self.assertTrue(any("via (b)" in d for d in e.exception.detalhes))

    def test_modelo_que_nao_veio_da_conversao_e_protegido(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "modelo").mkdir()
            (Path(tmp) / "modelo" / "metricas.yaml").write_text("versao: '0.1'\n", encoding="utf-8")
            with self.assertRaises(ErroDeConversao):
                converter(Path(tmp), RAIZ / "fixtures" / "vendas.pbix")


class TestPublicacao(unittest.TestCase):
    def test_dados_pessoais_do_pbix_bloqueiam(self):
        from bi_html.render import bloqueio_de_publicacao

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "saidas" / "bi").mkdir(parents=True)
            (p / "saidas" / "bi" / "manifesto.json").write_text(json.dumps({
                "versao": 1, "tabelas": {}, "eventos": [],
                "pbix": {"dados_pessoais": [{"coluna": "Clientes.email", "tipo": "email"}]}}), encoding="utf-8")
            self.assertEqual(bloqueio_de_publicacao(p), ["o .pbix convertido tem dados pessoais (Clientes.email)"])


PROVA = RAIZ / "provas" / "f7"


class TestProvaComArquivosReais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util

        # carregado pelo caminho: tests/test_f6.py já importa outro executar.py (o da prova da F6)
        spec = importlib.util.spec_from_file_location("prova_f7", PROVA / "executar.py")
        cls.prova = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.prova)
        cls.R = json.loads((PROVA / "resultados.json").read_text(encoding="utf-8"))

    def test_criterios_de_aceite(self):
        reais = {a: i for a, i in self.R["arquivos"].items() if not a.endswith("_ficticio")}
        self.assertEqual(set(reais), {"ifdata", "eleicoes", "lab1"})
        for a, info in reais.items():
            r = info["resumo"]
            self.assertEqual(r["tabelas_com_linhas_iguais"], r["tabelas"], a)
            self.assertEqual(r["medidas_classificadas"], r["medidas"], a)
            self.assertEqual(r["traduzidas_validadas"], r["traduzidas"], a)
            self.assertEqual(r["contextos_que_batem"], r["contextos_testados"], a)
            self.assertEqual(r["visuais_com_status"], r["visuais"], a)
            self.assertGreater(r["contextos_testados"], 0, a)
            self.assertGreater(info["tempo_s"], 0)
            self.assertGreater(info["pico_rss_mb"], 0)
        self.assertGreaterEqual(sum(i["resumo"]["traduzidas"] for i in reais.values()), 30)
        self.assertFalse(self.R["arquivos"]["directquery_ficticio"]["ok"])

    def test_resumo_reproduzivel_e_md_em_dia(self):
        for a, info in self.R["arquivos"].items():
            if info["ok"]:
                rel = json.loads((PROVA / "saidas" / a / "conversao.json").read_text(encoding="utf-8"))
                self.assertEqual(self.prova.criterios(rel), info["resumo"], a)
        self.assertEqual((PROVA / "RESULTADO.md").read_text(encoding="utf-8"), self.prova.gerar_md(self.R))

    def test_sem_caminhos_locais(self):
        proibido = re.compile(r"/Users/|/private/|[A-Za-z]:\\\\(?:Users|Mac)\\\\|OneDrive")
        for arq in [PROVA / "resultados.json", *sorted(p for p in (PROVA / "saidas").rglob("*") if p.is_file())]:
            texto = arq.read_text(encoding="utf-8")
            self.assertIsNone(proibido.search(texto), arq.name)
            self.assertNotIn(str(Path.home()), texto, arq.name)


if __name__ == "__main__":
    unittest.main()
