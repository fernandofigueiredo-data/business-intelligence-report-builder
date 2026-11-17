# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3", "jsonschema>=4.21"]
# ///
"""
servidor.py — servidor MCP `bi-dados` do plugin bi-html.

É o único caminho para números no sistema: nas próximas fases, ingestão,
perfil, métricas e achados entram aqui como ferramentas tipadas. Na F0 ele
expõe só o necessário para provar a ligação com o Claude Code:

- `saude`: versão do plugin e pasta do projeto vista pelo servidor;
- `validar_spec`: confere uma spec de dashboard contra o schema e as regras;
- `estado_do_ciclo`: diz em que etapa do ciclo Planilha → Análise → Dashboard → BI
  a pasta do projeto está.

Roda com `uv run --script`, que instala as dependências declaradas acima.
"""
import os, sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "lib"))
import bi_html  # noqa: E402
from bi_html.ciclo import estado  # noqa: E402
from bi_html.spec import validar_arquivo  # noqa: E402

mcp = MCPServer("bi-dados")


def projeto() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()


@mcp.tool()
def saude() -> dict:
    """Versão do plugin bi-html e pasta do projeto que o servidor está usando."""
    return {"plugin": "bi-html", "versao": bi_html.__version__, "projeto": str(projeto())}


@mcp.tool()
def validar_spec(caminho: str, metricas: list[str] | None = None) -> dict:
    """Valida uma spec de dashboard (JSON). `caminho` é relativo à pasta do projeto.
    `metricas`, se informado, é a lista de ids do modelo de métricas: métricas fora dela viram problema."""
    alvo = (projeto() / caminho).resolve()
    problemas = validar_arquivo(alvo, set(metricas) if metricas is not None else None)
    return {"arquivo": str(alvo), "valida": not problemas, "problemas": problemas}


@mcp.tool()
def estado_do_ciclo() -> dict:
    """Em que etapa do ciclo a pasta do projeto está e qual é o próximo passo."""
    return estado(projeto())


if __name__ == "__main__":
    mcp.run()
