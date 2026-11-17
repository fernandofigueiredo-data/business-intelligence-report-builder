"""
Detecção da etapa do ciclo Planilha → Análise → Dashboard → BI numa pasta de projeto.

A pasta segue a estrutura do plugin analise-dados (dados/, saidas/, contexto.md,
estilos/design-system.md). A passagem da análise para o BI é decidida pela
checagem do contrato (contrato.py, descrita em CONTRATO.md).
"""
from pathlib import Path

from . import contrato

EXTENSOES_DADOS = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".txt", ".tsv"}


def _arquivos_de_dados(pasta: Path) -> list[str]:
    if not pasta.is_dir():
        return []
    return sorted(p.name for p in pasta.iterdir() if p.suffix.lower() in EXTENSOES_DADOS)


def estado(projeto: Path) -> dict:
    projeto = Path(projeto)
    dados = _arquivos_de_dados(projeto / "dados")
    pbix = sorted(p.name for pasta in (projeto, projeto / "dados") if pasta.is_dir() for p in pasta.glob("*.pbix"))
    da_analise = [a for a in (contrato.CONTEXTO, contrato.NOTEBOOK, contrato.PARQUET) if (projeto / a).is_file()]
    spec = (projeto / "dashboard" / "spec.json").is_file()
    checagem = contrato.checar(projeto) if da_analise else None

    if not dados and not pbix and not da_analise:
        etapa, proximo = "planilha", "Coloque a planilha em dados/ (ou envie um .pbix) para começar."
    elif pbix and not dados and not da_analise:
        etapa, proximo = "pbix", "Fluxo do Power BI: a leitura do .pbix chega nas fases F6 e F7."
    elif not da_analise:
        etapa, proximo = "analise", "Rode /analise do plugin analise-dados (ou siga pelo atalho sem análise prévia)."
    elif not checagem["pronto_para_bi"]:
        etapa = "analise"
        proximo = "A análise ainda não entregou o que o BI precisa: " + " | ".join(checagem["faltando"])
    elif not spec:
        etapa, proximo = "dashboard", "Análise pronta para o BI. O dashboard é gerado a partir da fase F4."
    else:
        etapa, proximo = "bi", "Dashboard especificado. O documento de decisão chega na fase F5."

    return {
        "projeto": str(projeto),
        "etapa": etapa,
        "proximo_passo": proximo,
        "arquivos_de_dados": dados,
        "pbix": pbix,
        "spec_dashboard": spec,
        "contrato": {k: checagem[k] for k in ("versao_contrato", "pronto_para_bi", "itens", "faltando")}
        if checagem else None,
    }
