"""
Detecção da etapa do ciclo Planilha → Análise → Dashboard → BI numa pasta de projeto.

A pasta segue a estrutura do plugin analise-dados (dados/, saidas/, contexto.md,
estilos/design-system.md). A passagem da análise para o BI é decidida pela
checagem do contrato (contrato.py, descrita em CONTRATO.md).
"""
from pathlib import Path

from . import contrato
from .ingestao import ErroDeLeitura, ler_manifesto
from .modelo import ARQUIVO_MODELO, carregar

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
    modelo_ok, problemas_modelo = False, []
    if (projeto / ARQUIVO_MODELO).is_file():
        try:
            carregar(projeto)
            modelo_ok = True
        except ErroDeLeitura as e:
            problemas_modelo = [e.mensagem] + e.detalhes
    checagem = contrato.checar(projeto) if da_analise else None
    ingeridas = {n: t.get("situacao", "sem_perfil") for n, t in ler_manifesto(projeto)["tabelas"].items()}
    utilizaveis = [n for n, s in ingeridas.items() if s in ("ok", "com_alertas")]

    if not dados and not pbix and not da_analise:
        etapa, proximo = "planilha", "Coloque a planilha em dados/ (ou envie um .pbix) para começar."
    elif pbix and not dados and not da_analise:
        etapa, proximo = "pbix", f"Converta o relatório do Power BI com /bi-html:pbix {pbix[0]} (modo de importação)."
    elif not da_analise and not ingeridas:
        etapa, proximo = "analise", ("Rode /analise do plugin analise-dados (caminho padrão) ou "
                                     "/bi-html:ingerir para o atalho sem análise prévia.")
    elif not da_analise and not utilizaveis:
        etapa = "perfil"
        proximo = ("Há tabelas ingeridas, mas nenhuma utilizável ainda: "
                   + ", ".join(f"{n} ({s})" for n, s in ingeridas.items())
                   + ". Rode /bi-html:ingerir de novo depois de corrigir os bloqueios do perfil.")
    elif da_analise and not checagem["pronto_para_bi"]:
        etapa = "analise"
        proximo = "A análise ainda não entregou o que o BI precisa: " + " | ".join(checagem["faltando"])
    elif not modelo_ok:
        etapa = "metricas"
        if problemas_modelo:
            proximo = "O modelo de métricas tem problemas: " + " | ".join(problemas_modelo)
        elif da_analise:
            proximo = "Análise pronta para o BI. Defina as métricas com /bi-html:metricas."
        else:
            proximo = (f"Atalho sem análise prévia: {', '.join(utilizaveis)} ingerida(s) e perfilada(s). "
                       "Defina as métricas com /bi-html:metricas; o dashboard sairá com o aviso 'sem análise prévia'.")
    elif not (projeto / "design" / "tokens.json").is_file():
        etapa, proximo = "design", ("Métricas definidas e validadas. Escolha o visual com /bi-html:design "
                                    "(design system próprio ou estilo proposto pelo domínio dos dados).")
    elif not spec:
        etapa, proximo = "dashboard", "Métricas e design prontos. Monte o dashboard com /bi-html:dashboard."
    elif not (projeto / "saidas" / "bi" / "decisao.html").is_file():
        etapa, proximo = "bi", ("Dashboard especificado. Escreva o documento de decisão com /bi-html:decisao "
                                "(e renderize ou publique o painel com /bi-html:dashboard).")
    else:
        etapa, proximo = "concluido", ("Ciclo completo: dashboard e documento de decisão gerados. Para atualizar, "
                                       "rode /bi-html:dashboard e /bi-html:decisao de novo.")

    return {
        "projeto": str(projeto),
        "etapa": etapa,
        "proximo_passo": proximo,
        "arquivos_de_dados": dados,
        "pbix": pbix,
        "spec_dashboard": spec,
        "tabelas_ingeridas": ingeridas,
        "modelo_valido": modelo_ok,
        "contrato": {k: checagem[k] for k in ("versao_contrato", "pronto_para_bi", "itens", "faltando")}
        if checagem else None,
    }
