"""
Testes da fase F0: schema da spec, detecção do ciclo, dados fictícios e o servidor MCP.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import csv, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
FIXTURES = RAIZ / "fixtures"
sys.path.insert(0, str(PLUGIN / "lib"))
from bi_html.ciclo import estado  # noqa: E402
from bi_html.spec import validar, validar_arquivo  # noqa: E402

EXEMPLO = PLUGIN / "modelo" / "exemplos" / "spec-vendas.json"


def spec_exemplo():
    return json.loads(EXEMPLO.read_text(encoding="utf-8"))


class TestSpec(unittest.TestCase):
    def test_exemplo_valido(self):
        self.assertEqual(validar_arquivo(EXEMPLO), [])

    def test_exemplo_invalido_aponta_os_tres_problemas(self):
        problemas = validar_arquivo(PLUGIN / "modelo" / "exemplos" / "spec-invalida.json")
        self.assertEqual(len(problemas), 3, problemas)

    def test_numero_no_titulo_e_recusado(self):
        s = spec_exemplo()
        s["blocos"][0]["titulo"] = "Faturamento de R$ 2,1 mi"
        self.assertIn("número literal", " ".join(validar(s)))

    def test_campo_de_valor_e_recusado(self):
        s = spec_exemplo()
        s["blocos"][0]["valor"] = 2148900
        self.assertIn("campo não previsto: valor", " ".join(validar(s)))

    def test_marcador_de_metrica_de_outro_bloco_e_recusado(self):
        s = spec_exemplo()
        s["blocos"][1]["achado"] = "Ticket de {receita_total}."
        self.assertIn("não é métrica deste bloco", " ".join(validar(s)))

    def test_id_de_bloco_repetido(self):
        s = spec_exemplo()
        s["blocos"][1]["id"] = s["blocos"][0]["id"]
        self.assertIn("id repetido", " ".join(validar(s)))

    def test_metrica_fora_do_modelo(self):
        problemas = validar(spec_exemplo(), {"receita_total"})
        self.assertTrue(any("'pedidos' não existe" in p for p in problemas))

    def test_json_quebrado_vira_mensagem(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write("{ quebrado")
        self.assertIn("JSON inválido", validar_arquivo(f.name)[0])


class TestCiclo(unittest.TestCase):
    def test_pasta_vazia_pede_planilha(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(estado(Path(d))["etapa"], "planilha")

    def test_dados_sem_analise_pede_analise(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "dados").mkdir()
            (Path(d) / "dados" / "vendas.csv").write_text("a;b\n1;2\n")
            self.assertEqual(estado(Path(d))["etapa"], "analise")

    def test_so_pbix(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "relatorio.pbix").write_bytes(b"PK")
            self.assertEqual(estado(Path(d))["etapa"], "pbix")


class TestFixtures(unittest.TestCase):
    def linhas(self, nome, sep):
        with open(FIXTURES / nome, encoding="utf-8", newline="") as f:
            return list(csv.reader(f, delimiter=sep))

    def test_tres_dominios_existem(self):
        for nome in ("vendas.csv", "marketing.xlsx", "financeiro.csv"):
            self.assertTrue((FIXTURES / nome).is_file(), nome)

    def test_vendas_no_formato_brasileiro(self):
        linhas = self.linhas("vendas.csv", ";")
        self.assertEqual(len(linhas) - 1, 16254)
        self.assertRegex(linhas[1][0], r"^\d{2}/\d{2}/2025$")
        self.assertIn(",", linhas[1][-1])
        self.assertTrue(any(l[3] == "" for l in linhas[1:]), "deveria haver região ausente")

    def test_cpfs_ficticios_tem_digitos_corretos(self):
        for linha in self.linhas("clientes_ficticios.csv", ";")[1:]:
            d = [int(c) for c in linha[2] if c.isdigit()]
            for n in (9, 10):
                resto = sum(x * p for x, p in zip(d[:n], range(n + 1, 1, -1))) % 11
                self.assertEqual(d[n], 0 if resto < 2 else 11 - resto, linha[2])

    def test_malformado_nao_e_utf8(self):
        with self.assertRaises(UnicodeDecodeError):
            (FIXTURES / "malformado.csv").read_text(encoding="utf-8")


class TestServidorMCP(unittest.TestCase):
    """Sobe o servidor como o Claude Code sobe (stdio) e chama as ferramentas."""

    def test_lista_e_chama_ferramentas(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_PROJECT_DIR=d)
            msgs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "teste", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "estado_do_ciclo", "arguments": {}}},
            ]
            proc = subprocess.Popen([sys.executable, str(PLUGIN / "mcp" / "servidor.py")], env=env, text=True,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                proc.stdin.write("".join(json.dumps(m) + "\n" for m in msgs))
                proc.stdin.flush()
                respostas = {}
                while len(respostas) < 3:  # o servidor responde em paralelo; espera as três antes de fechar
                    linha = proc.stdout.readline()
                    if not linha:
                        break
                    m = json.loads(linha)
                    if "id" in m:
                        respostas[m["id"]] = m
            finally:
                proc.kill()
                proc.wait(timeout=10)
                proc.stdin.close()
                proc.stdout.close()
            nomes = {t["name"] for t in respostas[2]["result"]["tools"]}
            self.assertEqual(nomes, {"saude", "validar_spec", "estado_do_ciclo", "checar_contrato", "ingerir", "ingerir_texto", "perfilar",
                                     "propor_modelo", "validar_modelo", "consultar", "exportar_cubo",
                                     "propor_estilos", "aplicar_estilo", "importar_design",
                                     "renderizar_dashboard", "gerar_achados", "reproduzir_conclusao",
                                     "verificar_documento", "renderizar_documento", "converter_pbix"})
            texto = respostas[3]["result"]["content"][0]["text"]
            self.assertEqual(json.loads(texto)["etapa"], "planilha")


if __name__ == "__main__":
    unittest.main()
