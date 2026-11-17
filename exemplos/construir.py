#!/usr/bin/env python3
"""
construir.py — monta os dashboards de exemplo a partir dos dados fictícios.

    uv run --no-project --python 3.12 --with duckdb --with openpyxl --with pyyaml --with jsonschema exemplos/construir.py [nome ...]

Para cada exemplo (vendas, marketing, financeiro): ingere o arquivo de fixtures/, gera o
perfil, valida o modelo revisado (modelo/metricas.yaml), aplica a primeira opção de estilo
proposta pelo domínio e renderiza a spec (dashboard/spec.json). O modelo e a spec ficam no
git; dados/, saidas/ e design/ são gerados e ignorados.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "plugins" / "bi-html" / "lib"))
from bi_html.design import aplicar_estilo, propor_estilos  # noqa: E402
from bi_html.ingestao import ingerir  # noqa: E402
from bi_html.modelo import carregar, registrar_linhagem  # noqa: E402
from bi_html.perfil import perfilar  # noqa: E402
from bi_html.render import renderizar  # noqa: E402

EXEMPLOS = {"vendas": "vendas.csv", "marketing": "marketing.xlsx", "financeiro": "financeiro.csv"}


def construir(nome: str, projeto: Path | None = None) -> dict:
    """Monta o exemplo `nome` em `projeto` (padrão: exemplos/<nome>), que já tem modelo/ e dashboard/."""
    projeto = Path(projeto or RAIZ / "exemplos" / nome)
    tabela = ingerir(projeto, RAIZ / "fixtures" / EXEMPLOS[nome])["tabela"]
    perfilar(projeto, tabela)
    modelo, arquivo, _ = carregar(projeto)
    registrar_linhagem(projeto, modelo, arquivo)
    proposta = propor_estilos(projeto, tabela)
    opcao = proposta["opcoes"][0]
    aplicar_estilo(projeto, opcao["estilo"], proposta["dominio"], opcao["com_acento"])
    return renderizar(projeto)


if __name__ == "__main__":
    for nome in sys.argv[1:] or EXEMPLOS:
        r = construir(nome)
        print(f"{nome}: {r['html']} · {r['blocos']} blocos · {r['bytes'] / 1024:.0f} KB"
              + (f" · avisos: {r['avisos']}" if r["avisos"] else ""))
