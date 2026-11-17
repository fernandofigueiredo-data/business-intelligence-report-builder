"""
Detecção da etapa do ciclo Planilha → Análise → Dashboard → BI numa pasta de projeto.

A pasta segue a estrutura do plugin analise-dados (dados/, saidas/, contexto.md,
estilos/design-system.md). Na F0 só se detecta a presença dos arquivos; a
checagem do contrato (esquema, conclusão do notebook, campos do contexto.md)
chega na F0b e está descrita em CONTRATO.md.
"""
from pathlib import Path

EXTENSOES_DADOS = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".txt", ".tsv"}


def _arquivos_de_dados(pasta: Path) -> list[str]:
    if not pasta.is_dir():
        return []
    return sorted(p.name for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES_DADOS)


def estado(projeto: Path) -> dict:
    dados = _arquivos_de_dados(projeto / "dados")
    pbix = sorted(p.name for pasta in (projeto, projeto / "dados") if pasta.is_dir() for p in pasta.glob("*.pbix"))
    notebooks = sorted(p.name for p in projeto.glob("*.ipynb"))
    tem = {
        "dados": bool(dados),
        "contexto": (projeto / "contexto.md").is_file(),
        "notebook_analise": "analise.ipynb" in notebooks,
        "dados_tratados": (projeto / "saidas" / "dados_tratados.parquet").is_file(),
        "design_system": (projeto / "estilos" / "design-system.md").is_file(),
        "spec_dashboard": (projeto / "dashboard" / "spec.json").is_file(),
    }
    if not tem["dados"] and not pbix:
        etapa, proximo = "planilha", "Coloque a planilha em dados/ (ou envie um .pbix) para começar."
    elif pbix and not tem["dados"]:
        etapa, proximo = "pbix", "Fluxo do Power BI: a leitura do .pbix chega nas fases F6 e F7."
    elif not (tem["contexto"] and tem["notebook_analise"]):
        etapa, proximo = "analise", "Rode /analise do plugin analise-dados (ou siga pelo atalho sem análise prévia)."
    elif not tem["dados_tratados"]:
        etapa, proximo = "analise", ("A análise existe, mas falta saidas/dados_tratados.parquet: "
                                      "grave os dados tratados no notebook (o /painel do analise-dados faz isso).")
    elif not tem["spec_dashboard"]:
        etapa, proximo = "dashboard", "Análise pronta para o BI. O dashboard é gerado a partir da fase F4."
    else:
        etapa, proximo = "bi", "Dashboard especificado. O documento de decisão chega na fase F5."
    return {"projeto": str(projeto), "etapa": etapa, "proximo_passo": proximo, "presentes": tem,
            "arquivos_de_dados": dados, "pbix": pbix, "notebooks": notebooks}
