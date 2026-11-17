"""
Testes da fase F0b: contrato entre o analise-dados e o bi-html.

Usa a cópia do projeto de exemplo do analise-dados em tests/dados/projeto_exemplo/
(5.000 vendas, análise com conclusão, dados tratados gravados pelo próprio notebook).

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb -m unittest discover -s tests -v
"""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
EXEMPLO = Path(__file__).resolve().parent / "dados" / "projeto_exemplo"
sys.path.insert(0, str(PLUGIN / "lib"))
from bi_html.ciclo import estado  # noqa: E402
from bi_html.contrato import checar, ler_contexto  # noqa: E402

TRES = ("contexto.md", "analise.ipynb", "saidas/dados_tratados.parquet")


class ProjetoTemporario(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = Path(self._tmp.name) / "projeto"
        shutil.copytree(EXEMPLO, self.p)
        # o notebook é gravado antes dos dados tratados, como acontece numa análise real
        os.utime(self.p / "analise.ipynb", (1, 1))

    def tearDown(self):
        self._tmp.cleanup()

    def editar_contexto(self, velho, novo):
        c = self.p / "contexto.md"
        c.write_text(c.read_text(encoding="utf-8").replace(velho, novo), encoding="utf-8")

    def estados(self, r):
        return {i["arquivo"]: i["estado"] for i in r["itens"]}


class TestExemploPronto(ProjetoTemporario):
    def test_exemplo_esta_pronto_para_o_bi(self):
        r = checar(self.p)
        self.assertTrue(r["pronto_para_bi"], r["faltando"])
        self.assertEqual(set(self.estados(r).values()), {"ok"}, r["itens"])

    def test_ciclo_vai_para_dashboard(self):
        self.assertEqual(estado(self.p)["etapa"], "dashboard")

    def test_reaproveita_o_contexto_sem_perguntar(self):
        ctx = checar(self.p)["contexto"]
        self.assertIn("onde está o faturamento de 2025", ctx["pergunta_negocio"])
        self.assertIn("diretoria comercial", ctx["publico"])
        self.assertIn("esforço comercial em 2026", ctx["decisao"])
        self.assertEqual(len(ctx["dicionario"]), 8)
        self.assertEqual(len(ctx["decisoes_tratamento"]), 2)

    def test_conclusao_e_esquema(self):
        r = checar(self.p)
        self.assertEqual(len(r["conclusao"]), 4)
        self.assertIn("Sudeste", r["conclusao"][0])
        self.assertEqual(r["esquema"]["linhas"], 5000)
        nomes = [c["coluna"] for c in r["esquema"]["colunas"]]
        self.assertIn("faturamento", nomes)
        self.assertTrue(r["design_system"])


class TestFaltaUmArquivo(ProjetoTemporario):
    """Critério de aceite da F0b: removido um dos três arquivos, a checagem aponta exatamente ele."""

    def verificar_falta(self, arquivo, trecho_correcao):
        (self.p / arquivo).unlink()
        r = checar(self.p)
        self.assertFalse(r["pronto_para_bi"])
        self.assertEqual(len(r["faltando"]), 1, r["faltando"])
        self.assertTrue(r["faltando"][0].startswith(arquivo), r["faltando"])
        self.assertIn(trecho_correcao, r["faltando"][0])
        e = estado(self.p)
        self.assertEqual(e["etapa"], "analise")
        self.assertIn(arquivo, e["proximo_passo"])

    def test_sem_parquet(self):
        self.verificar_falta("saidas/dados_tratados.parquet", "rode-o de novo")

    def test_sem_notebook(self):
        self.verificar_falta("analise.ipynb", "/analise")

    def test_sem_contexto(self):
        self.verificar_falta("contexto.md", "/analise")

    def test_sem_os_tres_pede_analise_do_zero(self):
        for a in TRES:
            (self.p / a).unlink()
        e = estado(self.p)
        self.assertEqual(e["etapa"], "analise")
        self.assertIsNone(e["contrato"])


class TestConteudoInvalido(ProjetoTemporario):
    def test_pergunta_sem_resposta_bloqueia(self):
        self.editar_contexto("onde está o faturamento de 2025 — por região, mês e canal?", "?")
        r = checar(self.p)
        self.assertEqual(self.estados(r)["contexto.md"], "invalido")
        self.assertIn("Pergunta de negócio", r["faltando"][0])

    def test_sem_decisao_e_alerta(self):
        self.editar_contexto("- **Decisão que a análise apoia:** onde concentrar esforço comercial em 2026.\n", "")
        r = checar(self.p)
        self.assertTrue(r["pronto_para_bi"])
        self.assertEqual(self.estados(r)["contexto.md"], "alerta")

    def test_notebook_sem_conclusao_bloqueia(self):
        nb_path = self.p / "analise.ipynb"
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        nb["cells"] = [c for c in nb["cells"] if "Conclusão" not in "".join(c["source"])]
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        os.utime(nb_path, (1, 1))
        r = checar(self.p)
        self.assertEqual(self.estados(r)["analise.ipynb"], "invalido")
        self.assertIn("conclusão", r["faltando"][0])

    def test_notebook_fora_de_ordem_e_alerta(self):
        nb_path = self.p / "analise.ipynb"
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        codigo = [c for c in nb["cells"] if c["cell_type"] == "code"]
        codigo[0]["execution_count"], codigo[1]["execution_count"] = 9, None
        nb_path.write_text(json.dumps(nb), encoding="utf-8")
        os.utime(nb_path, (1, 1))
        r = checar(self.p)
        self.assertTrue(r["pronto_para_bi"])
        self.assertEqual(self.estados(r)["analise.ipynb"], "alerta")

    def test_parquet_corrompido_bloqueia(self):
        (self.p / "saidas/dados_tratados.parquet").write_bytes(b"isto nao e parquet")
        r = checar(self.p)
        self.assertEqual(self.estados(r)["saidas/dados_tratados.parquet"], "invalido")

    def test_coluna_sem_definicao_e_notebook_mais_novo_viram_alerta(self):
        self.editar_contexto("criadas `faturamento` (quantidade × preço) e `lucro`", "criada uma coluna")
        os.utime(self.p / "analise.ipynb", None)
        r = checar(self.p)
        item = next(i for i in r["itens"] if i["arquivo"] == "saidas/dados_tratados.parquet")
        self.assertEqual(item["estado"], "alerta")
        self.assertIn("faturamento", item["detalhe"])
        self.assertIn("alterado depois", item["detalhe"])


class TestLeituraDoContexto(unittest.TestCase):
    def test_campos_com_interrogacao_viram_vazios(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("# Contexto\n\n## Objetivo\n- **Pergunta de negócio:** ?\n- **Quem lê o resultado:** ...\n")
        ctx = ler_contexto(Path(f.name))
        self.assertIsNone(ctx["pergunta_negocio"])
        self.assertIsNone(ctx["publico"])
        self.assertEqual(ctx["dicionario"], [])


class TestServidorNoExemplo(unittest.TestCase):
    """A ferramenta checar_contrato pelo MCP, com o projeto de exemplo como pasta do projeto."""

    def test_checar_contrato_pelo_mcp(self):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(EXEMPLO))
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "teste", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "checar_contrato", "arguments": {}}},
        ]
        proc = subprocess.Popen([sys.executable, str(PLUGIN / "mcp" / "servidor.py")], env=env, text=True,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            proc.stdin.write("".join(json.dumps(m) + "\n" for m in msgs))
            proc.stdin.flush()
            resposta = None
            while resposta is None:
                linha = proc.stdout.readline()
                if not linha:
                    break
                m = json.loads(linha)
                if m.get("id") == 2:
                    resposta = m
        finally:
            proc.kill()
            proc.wait(timeout=10)
            proc.stdin.close()
            proc.stdout.close()
        r = json.loads(resposta["result"]["content"][0]["text"])
        self.assertEqual(r["esquema"]["linhas"], 5000)
        self.assertEqual(len(r["conclusao"]), 4)


if __name__ == "__main__":
    unittest.main()
