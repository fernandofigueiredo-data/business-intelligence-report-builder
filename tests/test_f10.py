"""
Testes da fase F10: o assistente de perguntas no dashboard publicado.

Critério de aceite: perguntas com resposta conhecida, pelo menos 90% corretas, e nenhum número fora
do cubo. A bateria em si roda no Artifact publicado (capacidade `sample`, na conta de quem clica) e é
registrada em provas/f10; aqui se testa o que decide o resultado: as perguntas e suas respostas,
o verificador de números (em Python e, com Node, o da página, que precisam concordar) e a página.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import importlib.util, json, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
sys.path.insert(0, str(RAIZ / "exemplos"))
from bi_html.assistente import CAPACIDADES, JS, avaliar, perguntas, renderizar_assistente  # noqa: E402
from bi_html.consulta import formatar  # noqa: E402
from bi_html.dashboard import montar  # noqa: E402


class Vendas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from construir import construir

        cls._tmp = tempfile.TemporaryDirectory()
        cls.p = Path(cls._tmp.name) / "vendas"
        for pasta in ("modelo", "dashboard"):
            shutil.copytree(RAIZ / "exemplos" / "vendas" / pasta, cls.p / pasta)
        construir("vendas", cls.p)
        cls.m = montar(cls.p)
        cls.ps = perguntas(cls.m)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def respostas_certas(self):
        r = {}
        for p in self.ps:
            if p["tipo"] == "numero":
                md = self.m["metricas"][p["metrica"]]
                r[p["id"]] = f"O valor é {formatar(p['esperado'], md['formato'], md.get('unidade'))}."
            elif p["tipo"] == "categoria":
                r[p["id"]] = f"É {p['esperado']}."
            else:
                r[p["id"]] = "Não está no dashboard: nenhum bloco mostra isso."
        return r

    def consultas(self):
        return {p["id"]: ([{"bloco": p["bloco"], "filtros": p["filtros"]}] if p["bloco"] else []) for p in self.ps}


class TestPerguntas(Vendas):
    def test_trinta_variadas_e_deterministicas(self):
        self.assertEqual(len(self.ps), 30)
        self.assertEqual([p["id"] for p in self.ps], [f"P{i:02d}" for i in range(1, 31)])
        self.assertEqual({p["tipo"] for p in self.ps}, {"numero", "categoria", "indisponivel"})
        self.assertGreaterEqual(sum(p["tipo"] == "categoria" for p in self.ps), 3)
        self.assertEqual(len({p["pergunta"] for p in self.ps}), 30)
        self.assertEqual(perguntas(montar(self.p)), self.ps)

    def test_respostas_vem_do_cubo(self):
        faturamento = next(p for p in self.ps if p["metrica"] == "receita_total" and "sem filtros" in p["pergunta"])
        base = next(b for b in self.m["blocos"] if b["id"] == faturamento["bloco"])
        chave = "|".join(self.m["constantes"]["todos"] for _ in self.m["filtros"])
        self.assertEqual(faturamento["esperado"], base["dados"][chave]["linhas"][0]["receita_total"])


class TestCorrecao(Vendas):
    def test_respostas_certas_passam(self):
        r = avaliar(self.m, self.respostas_certas(), self.consultas())
        self.assertEqual((r["acertos"], r["com_numero_fora"]), (30, 0))

    def test_numero_inventado_ou_nao_consultado_e_pego(self):
        resp = self.respostas_certas()
        resp["P01"] = "O valor é R$ 9.999.999,99."
        resp["P05"] = resp["P05"].rstrip(".") + ", cerca de 3 por loja."
        resp["P28"] = "Não está no dashboard; o faturamento foi " + formatar(self.ps[0]["esperado"], "moeda") + "."
        r = avaliar(self.m, resp, self.consultas())
        fora = {i["id"]: i["numeros_fora"] for i in r["itens"] if i["numeros_fora"]}
        self.assertEqual(set(fora), {"P01", "P05", "P28"})
        self.assertEqual(r["acertos"], 27)

    def test_categoria_e_indisponivel(self):
        resp = self.respostas_certas()
        cat = next(p for p in self.ps if p["tipo"] == "categoria")
        resp[cat["id"]] = "É outra coisa."
        resp["P29"] = "Foram muitos clientes."
        r = avaliar(self.m, resp, self.consultas())
        erradas = {i["id"] for i in r["itens"] if not i["correta"]}
        self.assertEqual(erradas, {cat["id"], "P29"})

    @unittest.skipUnless(shutil.which("node"), "sem Node para rodar o verificador da página")
    def test_pagina_e_python_concordam(self):
        r = renderizar_assistente(self.p)
        h = (self.p / r["artifact"]).read_text(encoding="utf-8")
        dados = re.search(r'id="dados-bi">(.*?)</script>', h, re.S).group(1)
        pergs = re.search(r'id="perguntas-bi">(.*?)</script>', h, re.S).group(1)
        resp = self.respostas_certas()
        resp["P01"] = "O valor é R$ 9.999.999,99."
        resp["P02"] += " Isso dá 37% do total."
        resp["P05"] = resp["P05"].rstrip(".") + ", cerca de 3 por loja."
        consultas = self.consultas()
        py = avaliar(self.m, resp, consultas)
        corpo = JS.replace("const sample = await claude.use('sample');", "return { corrigir };")
        harness = (f"const el = {{ 'dados-bi': {json.dumps(dados)}, 'perguntas-bi': {json.dumps(pergs)} }};\n"
                   "globalThis.document = { getElementById: id => ({ textContent: el[id] }) };\n"
                   f"const api = await {corpo.strip().rstrip(';')};\n"
                   f"const resp = {json.dumps(resp, ensure_ascii=False)}, cs = {json.dumps(consultas, ensure_ascii=False)};\n"
                   "const P = JSON.parse(el['perguntas-bi']);\n"
                   "console.log(JSON.stringify(P.map(p => { const c = api.corrigir(p, resp[p.id], cs[p.id]); "
                   "return [p.id, c.certa, c.fora]; })));\n")
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as f:
            f.write(harness)
        try:
            saida = subprocess.run(["node", f.name], capture_output=True, text=True, timeout=60)
        finally:
            Path(f.name).unlink()
        self.assertEqual(saida.returncode, 0, saida.stderr)
        js = json.loads(saida.stdout)
        self.assertEqual(js, [[i["id"], i["correta"], i["numeros_fora"]] for i in py["itens"]])


class TestPagina(Vendas):
    def test_painel_e_capacidades(self):
        r = renderizar_assistente(self.p)
        h = (self.p / r["artifact"]).read_text(encoding="utf-8")
        self.assertEqual(r["perguntas"], 30)
        self.assertIn('<section class="assistente" id="assistente" hidden', h)
        self.assertIn('id="perguntas-bi"', h)
        self.assertNotIn('"bloco"', re.search(r'id="perguntas-bi">(.*?)</script>', h, re.S).group(1))
        self.assertEqual(set(CAPACIDADES), {"sample", "user", "db"})
        self.assertEqual(CAPACIDADES["db"]["rules"][0]["write"], "admin")
        self.assertIn("nunca instruções", JS)
        self.assertEqual(r["publicacao_bloqueada"], [])


class TestRegistroDaProva(Vendas):
    def test_registrar_refaz_a_correcao(self):
        spec = importlib.util.spec_from_file_location("prova_f10", RAIZ / "provas" / "f10" / "registrar.py")
        prova = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prova)
        resp, cs = self.respostas_certas(), self.consultas()
        registro = {"quando": "2026-11-17T20:00:00Z", "dashboard": "Vendas", "modelo": "default", "acertos": 30,
                    "itens": [{"id": p["id"], "pergunta": p["pergunta"], "tipo": p["tipo"], "resposta": resp[p["id"]],
                               "consultas": cs[p["id"]], "correta": True, "numeros_fora": []} for p in self.ps]}
        r = prova.registrar(registro, self.p)
        self.assertEqual((r["acertos_python"], r["com_numero_fora"], r["correcoes_iguais"]), (30, 0, True))
        self.assertTrue(r["criterio"]["atende"])
        registro["itens"][0]["resposta"] = "O valor é R$ 1,00."
        r = prova.registrar(registro, self.p)
        self.assertEqual((r["acertos_python"], r["correcoes_iguais"]), (29, False))
        self.assertFalse(r["criterio"]["atende"])  # número fora do que consultou derruba o critério
        md = prova.gerar_md(r)
        self.assertIn("**não atende**", md)
        self.assertIn("divergem em 1 pergunta", md)


if __name__ == "__main__":
    unittest.main()
