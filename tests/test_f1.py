"""
Testes da fase F1: ingestão (CSV, Excel, texto colado) e perfil com os conjuntos fictícios.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl -m unittest discover -s tests -v
"""
import csv, json, os, shutil, subprocess, sys, tempfile, unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLUGIN = RAIZ / "plugins" / "bi-html"
FIXTURES = RAIZ / "fixtures"
sys.path.insert(0, str(PLUGIN / "lib"))
import duckdb  # noqa: E402
from bi_html.ciclo import estado  # noqa: E402
from bi_html.ingestao import ErroDeLeitura, ingerir, ingerir_texto, ler_manifesto  # noqa: E402
from bi_html.perfil import perfilar  # noqa: E402


def consulta(arquivo, sql):
    con = duckdb.connect()
    try:
        literal = "'" + str(arquivo).replace("'", "''") + "'"
        return con.execute(sql.replace("{t}", f"read_parquet({literal})")).fetchall()
    finally:
        con.close()


class Projeto(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.p = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def tipos(self, r):
        return {c["nome"]: c["tipo"] for c in r["colunas"]}

    def arquivo(self, nome, conteudo: bytes):
        f = self.p / "entrada" / nome
        f.parent.mkdir(exist_ok=True)
        f.write_bytes(conteudo)
        return f


class TestTresDominios(Projeto):
    """Critério de aceite: os três conjuntos geram qualidade.json com tipos e datas pt-BR corretos."""

    def test_vendas(self):
        r = ingerir(self.p, FIXTURES / "vendas.csv")
        self.assertEqual(r["leitura"]["separador"], ";")
        self.assertEqual(r["leitura"]["decimal"], ",")
        self.assertEqual(self.tipos(r), {
            "data_pedido": "data", "pedido_id": "texto", "uf": "texto", "regiao": "texto", "loja": "texto",
            "canal": "texto", "categoria": "texto", "produto": "texto", "quantidade": "inteiro",
            "preco_unitario": "decimal", "desconto_pct": "inteiro", "receita": "decimal"})
        pq = self.p / r["parquet"]
        with open(FIXTURES / "vendas.csv", encoding="utf-8") as f:
            linhas = list(csv.DictReader(f, delimiter=";"))
        soma = sum(Decimal(l["receita"].replace(",", ".")) for l in linhas)
        vazios = sum(1 for l in linhas if not l["uf"])
        (n, s, primeira, ultima, nulos), = consulta(
            pq, "SELECT count(*), sum(receita), min(data_pedido), max(data_pedido), count(*) - count(uf) FROM {t}")
        self.assertEqual(n, len(linhas))
        self.assertAlmostEqual(s, float(soma), places=2)
        self.assertEqual((primeira, ultima), (date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual(nulos, vazios)
        self.assertGreater(vazios, 0)
        rel = perfilar(self.p, "vendas")
        self.assertEqual(rel["situacao"], "ok")
        self.assertEqual(rel["chaves_candidatas"], ["pedido_id"])
        self.assertTrue((self.p / "saidas/bi/perfil/vendas.qualidade.json").is_file())

    def test_marketing_excel(self):
        r = ingerir(self.p, FIXTURES / "marketing.xlsx")
        self.assertEqual(r["leitura"]["aba"], "campanhas")
        self.assertEqual(r["leitura"]["outras_abas"], ["dicionario"])
        self.assertEqual(self.tipos(r)["data"], "data")
        self.assertEqual(self.tipos(r)["impressoes"], "inteiro")
        self.assertEqual(self.tipos(r)["investimento"], "decimal")
        (inicio, fim, n), = consulta(self.p / r["parquet"], "SELECT min(data), max(data), count(*) FROM {t}")
        self.assertEqual((inicio, fim, n), (date(2025, 1, 1), date(2025, 12, 31), 3285))
        self.assertEqual(perfilar(self.p, "marketing")["situacao"], "ok")

    def test_financeiro_competencia_mensal(self):
        r = ingerir(self.p, FIXTURES / "financeiro.csv")
        self.assertEqual(r["leitura"]["decimal"], ".")
        self.assertEqual(self.tipos(r)["competencia"], "mes")
        self.assertEqual(self.tipos(r)["valor"], "decimal")
        (inicio, fim, negativos), = consulta(self.p / r["parquet"],
                                            "SELECT min(competencia), max(competencia), count(*) FILTER (valor < 0) FROM {t}")
        self.assertEqual((inicio, fim), (date(2024, 1, 1), date(2025, 12, 1)))
        self.assertGreater(negativos, 0)
        self.assertEqual(perfilar(self.p, "financeiro")["situacao"], "ok")

    def test_original_copiado_para_dados_e_manifesto(self):
        ingerir(self.p, FIXTURES / "vendas.csv")
        self.assertTrue((self.p / "dados" / "vendas.csv").is_file())
        m = ler_manifesto(self.p)
        self.assertEqual(m["tabelas"]["vendas"]["origem"], "dados/vendas.csv")
        self.assertEqual(len(m["tabelas"]["vendas"]["sha256"]), 64)
        self.assertEqual(m["eventos"][-1]["evento"], "ingestao")


class TestDadosPessoais(Projeto):
    """Critério de aceite: o arquivo com CPF fictício é sinalizado e a publicação fica bloqueada."""

    def test_cpf_email_telefone(self):
        ingerir(self.p, FIXTURES / "clientes_ficticios.csv")
        rel = perfilar(self.p, "clientes_ficticios")
        tipos = {d["coluna"]: d["tipo"] for d in rel["dados_pessoais"]}
        self.assertEqual(tipos["cpf"], "cpf")
        self.assertEqual(tipos["email"], "email")
        self.assertEqual(tipos["telefone"], "telefone")
        self.assertTrue(rel["publicacao_bloqueada"])
        self.assertTrue(any("dados pessoais" in a for a in rel["alertas"]))

    def test_cpf_com_digito_errado_nao_conta_como_cpf(self):
        f = self.arquivo("cod.csv", b"codigo;valor\n" + b"".join(f"123.456.789-0{i};1\n".encode() for i in range(10)))
        ingerir(self.p, f)
        self.assertEqual(perfilar(self.p, "cod")["dados_pessoais"], [])


class TestErrosLegiveis(Projeto):
    """Critério de aceite: o arquivo malformado devolve erro legível, e nada é copiado."""

    def test_malformado(self):
        with self.assertRaises(ErroDeLeitura) as ctx:
            ingerir(self.p, FIXTURES / "malformado.csv")
        e = ctx.exception
        self.assertIn("número de colunas diferente", e.mensagem)
        self.assertEqual(e.detalhes, ["linha 3: 3 colunas, o cabeçalho tem 4", "linha 4: 5 colunas, o cabeçalho tem 4"])
        self.assertFalse((self.p / "dados").exists())

    def test_codificacao_misturada(self):
        f = self.arquivo("misto.csv", "a;b\nação;1\n".encode() + "pão;2\n".encode("latin-1"))
        with self.assertRaises(ErroDeLeitura) as ctx:
            ingerir(self.p, f)
        self.assertIn("linha 3", ctx.exception.mensagem)

    def test_arquivo_todo_em_latin1_e_lido(self):
        f = self.arquivo("antigo.csv", "produto;valor\nmaçã;1,50\npão;2,00\n".encode("cp1252"))
        r = ingerir(self.p, f)
        self.assertEqual(r["leitura"]["codificacao"], "cp1252")
        self.assertEqual(self.tipos(r)["valor"], "decimal")

    def test_cabecalho_repetido(self):
        with self.assertRaises(ErroDeLeitura) as ctx:
            ingerir(self.p, self.arquivo("rep.csv", b"valor;Valor\n1;2\n"))
        self.assertIn("repetidos", ctx.exception.mensagem)

    def test_formato_nao_suportado(self):
        with self.assertRaises(ErroDeLeitura) as ctx:
            ingerir(self.p, self.arquivo("r.pbix", b"PK"))
        self.assertIn("F6", " ".join(ctx.exception.detalhes))

    def test_nao_sobrescreve_original_diferente(self):
        ingerir(self.p, self.arquivo("x.csv", b"a;b\n1;2\n"))
        outro = self.p / "outra" / "x.csv"
        outro.parent.mkdir()
        outro.write_bytes(b"a;b\n9;9\n")
        with self.assertRaises(ErroDeLeitura):
            ingerir(self.p, outro)
        self.assertEqual((self.p / "dados" / "x.csv").read_bytes(), b"a;b\n1;2\n")

    def test_reingerir_o_mesmo_arquivo_funciona(self):
        f = self.arquivo("x.csv", b"a;b\n1;2\n")
        ingerir(self.p, f)
        ingerir(self.p, f)
        self.assertEqual(len(ler_manifesto(self.p)["eventos"]), 2)


class TestLeituraEAlertas(Projeto):
    def test_texto_colado_do_excel(self):
        r = ingerir_texto(self.p, "Região\tReceita\nSul\t1.234,50\nNorte\t980,00\n", "Receita por região")
        self.assertEqual(r["tabela"], "receita_por_regiao")
        self.assertEqual(self.tipos(r), {"regiao": "texto", "receita": "decimal"})
        (s,), = consulta(self.p / r["parquet"], "SELECT sum(receita) FROM {t}")
        self.assertAlmostEqual(s, 2214.50, places=2)

    def test_coluna_quase_numerica_vira_alerta(self):
        corpo = "".join(f"{i};{i},00\n" for i in range(30)) + "30;12x,00\n"
        ingerir(self.p, self.arquivo("q.csv", ("id;valor\n" + corpo).encode()))
        alertas = " ".join(perfilar(self.p, "q")["alertas"])
        self.assertIn("parece numérica", alertas)
        self.assertIn("12x,00", alertas)

    def test_data_ambigua_vira_alerta(self):
        ingerir(self.p, self.arquivo("d.csv", b"data;v\n01/02/2025;1\n03/04/2025;2\n"))
        self.assertIn("dd/mm/aaaa", " ".join(perfilar(self.p, "d")["alertas"]))

    def test_negativo_raro_vira_alerta(self):
        corpo = "".join(f"{i};{i + 1}\n" for i in range(200)) + "200;-5\n"
        ingerir(self.p, self.arquivo("n.csv", ("id;qtd\n" + corpo).encode()))
        self.assertIn("negativo", " ".join(perfilar(self.p, "n")["alertas"]))

    def test_sem_coluna_numerica_bloqueia(self):
        ingerir(self.p, self.arquivo("t.csv", b"nome_produto;cor\nA;azul\nB;verde\n"))
        rel = perfilar(self.p, "t")
        self.assertEqual(rel["situacao"], "bloqueado")
        self.assertTrue(rel["publicacao_bloqueada"])

    def test_zeros_a_esquerda_ficam_como_texto(self):
        r = ingerir(self.p, self.arquivo("cep.csv", b"cep;v\n01310100;1\n20040002;2\n"))
        self.assertEqual(self.tipos(r)["cep"], "texto")


class TestCicloComAtalho(Projeto):
    def test_ciclo_reconhece_o_atalho(self):
        ingerir(self.p, FIXTURES / "vendas.csv")
        self.assertEqual(estado(self.p)["etapa"], "perfil")
        perfilar(self.p, "vendas")
        e = estado(self.p)
        self.assertEqual(e["etapa"], "metricas")
        self.assertIn("sem análise prévia", e["proximo_passo"])


class TestServidorIngestao(unittest.TestCase):
    def test_ingerir_e_perfilar_pelo_mcp(self):
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(FIXTURES / "clientes_ficticios.csv", d)
            env = dict(os.environ, CLAUDE_PROJECT_DIR=d)
            msgs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                 "params": {"name": "ingerir", "arguments": {"caminho": "clientes_ficticios.csv"}}},
            ]
            proc = subprocess.Popen([sys.executable, str(PLUGIN / "mcp" / "servidor.py")], env=env, text=True,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                def enviar(m):
                    proc.stdin.write(json.dumps(m) + "\n")
                    proc.stdin.flush()

                def esperar(i):
                    while True:
                        m = json.loads(proc.stdout.readline())
                        if m.get("id") == i:
                            return json.loads(m["result"]["content"][0]["text"])

                for m in msgs:
                    enviar(m)
                ing = esperar(2)
                enviar({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "perfilar", "arguments": {"tabela": ing["tabela"]}}})
                rel = esperar(3)
                enviar({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "ingerir", "arguments": {"caminho": "nao_existe.csv"}}})
                erro = esperar(4)
            finally:
                proc.kill()
                proc.wait(timeout=10)
                proc.stdin.close()
                proc.stdout.close()
            self.assertTrue(ing["ok"])
            self.assertEqual(ing["linhas"], 200)
            self.assertTrue(rel["publicacao_bloqueada"])
            self.assertFalse(erro["ok"])
            self.assertIn("não encontrado", erro["erro"])


if __name__ == "__main__":
    unittest.main()
