"""
Testes da fase F9: a vitrine pública do portfólio (site estático em docs/).

Critério de aceite: página pública com os dashboards de demonstração e o comparativo (a) vs. (b).
O site é gerado por vitrine/construir.py e publicado pelo usuário (GitHub Pages servindo docs/);
aqui se confere o que foi gerado: cada link da página inicial leva a um arquivo do site, a
comparação está lá, nada aponta para caminhos locais e os números da página inicial são os do
relatório da conversão.

    uv run --no-project --python 3.12 --with jsonschema --with "mcp>=2.3,<3" --with duckdb --with openpyxl --with pyyaml -m unittest discover -s tests -v
"""
import re, unittest
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOCS = RAIZ / "docs"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for chave in ("href", "src"):
            if a.get(chave):
                self.links.append(a[chave])


def links(caminho: Path) -> list[str]:
    p = Links()
    p.feed(caminho.read_text(encoding="utf-8"))
    return p.links


class TestVitrine(unittest.TestCase):
    def test_paginas_de_demonstracao(self):
        for pagina in ("index.html", "vendas/index.html", "marketing/index.html", "financeiro/index.html",
                       "ciclo/index.html", "ciclo/decisao.html", "power-bi/index.html", "power-bi/convertido.html"):
            self.assertTrue((DOCS / pagina).is_file(), pagina)
        self.assertTrue((DOCS / ".nojekyll").is_file())

    def test_links_internos_resolvem(self):
        for pagina in (DOCS / "index.html", DOCS / "power-bi" / "index.html"):
            for link in links(pagina):
                if link.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                alvo = (pagina.parent / link)
                alvo = alvo / "index.html" if link.endswith("/") else alvo
                self.assertTrue(alvo.is_file(), f"{pagina.name}: {link}")

    def test_externos_so_dos_hosts_esperados(self):
        permitidos = ("https://fonts.googleapis.com/", "https://cdnjs.cloudflare.com/ajax/libs/echarts/",
                      "https://app.powerbi.com/")
        for arq in DOCS.rglob("*.html"):
            for link in links(arq):
                if link.startswith(("http://", "https://")):
                    self.assertTrue(link.startswith(permitidos), f"{arq.relative_to(DOCS)}: {link}")

    def test_sem_caminhos_locais(self):
        for arq in DOCS.rglob("*"):
            if arq.is_file():
                texto = arq.read_text(encoding="utf-8", errors="ignore")
                self.assertNotIn("/Users/", texto, arq.name)
                self.assertNotIn("/private/", texto, arq.name)

    def test_comparativo_e_numeros_da_conversao(self):
        indice = (DOCS / "index.html").read_text(encoding="utf-8")
        comparativo = (DOCS / "power-bi" / "index.html").read_text(encoding="utf-8")
        # os mesmos números saem do relatório da conversão nas duas páginas
        for trecho in re.findall(r"(\d+ de \d+) medidas traduzidas", indice):
            self.assertIn(f"<strong>{trecho}</strong> medidas traduzidas", comparativo)
        self.assertIn("No Power BI", comparativo)
        self.assertIn("No bi-html", comparativo)
        self.assertIn("fictícios", indice)


if __name__ == "__main__":
    unittest.main()
