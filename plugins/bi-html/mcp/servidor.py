# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=2.3,<3", "jsonschema>=4.21", "duckdb>=1.1", "openpyxl>=3.1", "pyyaml>=6"]
# ///
"""
servidor.py — servidor MCP `bi-dados` do plugin bi-html.

É o único caminho para números no sistema. As instruções que ele manda ao
Claude (`bi_html.instrucoes`) dizem quando usar as ferramentas em pedidos em
texto livre, fora dos comandos /bi-html. Ele expõe:

- `saude`: versão do plugin e pasta do projeto vista pelo servidor;
- `validar_spec`: confere uma spec de dashboard contra o schema e as regras;
- `estado_do_ciclo`: diz em que etapa do ciclo Planilha → Análise → Dashboard → BI
  a pasta do projeto está;
- `checar_contrato`: confere o que a análise (plugin analise-dados) entregou e devolve
  o que o BI reaproveita sem perguntar de novo (objetivo, dicionário, conclusão, esquema);
- `ingerir` e `ingerir_texto`: leem CSV, Excel ou texto colado e gravam a tabela tipada
  (atalho sem análise prévia);
- `perfilar`: perfil e validação da tabela ingerida, com dados pessoais e alertas;
- `propor_modelo` e `validar_modelo`: rascunho e validação de modelo/metricas.yaml, com a
  linhagem de cada métrica registrada no manifesto;
- `consultar`: o único caminho para um número (métricas × dimensões × filtros × período);
- `exportar_cubo`: dados agregados que o dashboard embute;
- `propor_estilos`, `aplicar_estilo` e `importar_design`: domínio inferido, estilos base e
  design system enviado, gravados em design/tokens.json e tokens.css com contraste AA;
- `renderizar_dashboard`: calcula os blocos da spec e grava o HTML do dashboard;
- `gerar_achados`, `reproduzir_conclusao`, `verificar_documento` e `renderizar_documento`:
  fatos calculados para o documento de decisão, reprodução da conclusão da análise,
  conferência de cada número do texto e o HTML do documento.
- `converter_pbix`: Fluxo 2, via (a): um .pbix em modo de importação vira tabela, modelo de
  métricas, specs por página e páginas renderizadas, com o teste de equivalência das medidas
  traduzidas contra o Power BI e o relatório de fidelidade por visual. A leitura do .pbix roda
  num processo à parte (o pbix-mcp exige mcp<2).
- `montar_comparativo`: Fluxo 2, via (b): o relatório original publicado no Power BI ao lado da
  página convertida, numa pasta estática (o Artifact do claude.ai não incorpora outros sites).
- `exportar_offline`: o dashboard num HTML autocontido para enviar, que abre sem internet; recusado
  com dados pessoais.
- `renderizar_assistente`: o dashboard com um assistente de perguntas (capacidade `sample` do
  Artifact), em que cada número da resposta é conferido contra o que o assistente consultou.

Roda com `uv run --script`, que instala as dependências declaradas acima.
"""
import os, sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "lib"))
import bi_html  # noqa: E402
from bi_html.ciclo import estado  # noqa: E402
from bi_html.contrato import checar  # noqa: E402
from bi_html.ingestao import ErroDeLeitura, ingerir as _ingerir, ingerir_texto as _ingerir_texto  # noqa: E402
from bi_html.perfil import perfilar as _perfilar, resumo  # noqa: E402
from bi_html.consulta import consultar as _consultar, exportar_cubo as _exportar_cubo, para_json  # noqa: E402
from bi_html.modelo import carregar, propor, registrar_linhagem  # noqa: E402
from bi_html import design as _design  # noqa: E402
from bi_html.render import renderizar  # noqa: E402
from bi_html.achados import gerar as _gerar_achados  # noqa: E402
from bi_html.conclusao import reproduzir  # noqa: E402
from bi_html.documento import renderizar_documento as _renderizar_documento  # noqa: E402
from bi_html.verificador import verificar as _verificar_documento  # noqa: E402
from bi_html.spec import validar_arquivo  # noqa: E402
from bi_html.conversao import converter as _converter_pbix  # noqa: E402
from bi_html.incorporacao import montar_comparativo as _montar_comparativo  # noqa: E402
from bi_html.exportacao import exportar as _exportar_offline  # noqa: E402
from bi_html.assistente import renderizar_assistente as _renderizar_assistente  # noqa: E402
from bi_html.instrucoes import instrucoes  # noqa: E402

mcp = MCPServer("bi-dados", instructions=instrucoes(PLUGIN))


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


@mcp.tool()
def checar_contrato() -> dict:
    """Confere se a análise entregou os três arquivos do contrato (saidas/dados_tratados.parquet,
    analise.ipynb com conclusão, contexto.md). Devolve o veredito, o que falta com a correção, e o
    objetivo, o dicionário de colunas, as decisões de tratamento, os itens da conclusão e o esquema."""
    return checar(projeto())


def _erro(e: ErroDeLeitura) -> dict:
    return {"ok": False, "erro": e.mensagem, "detalhes": e.detalhes}


def _resumo_ingestao(r: dict) -> dict:
    return {"ok": True, "tabela": r["tabela"], "origem": r["origem"], "linhas": r["linhas"],
            "leitura": r["leitura"], "parquet": r["parquet"],
            "colunas": [{"nome": c["nome"], "original": c["original"], "tipo": c["tipo"]} for c in r["colunas"]]}


@mcp.tool()
def ingerir(caminho: str, nome: str | None = None, aba: str | None = None) -> dict:
    """Lê um CSV, TXT, TSV ou XLSX e grava a tabela tipada em saidas/bi/tabelas/<nome>.parquet.
    `caminho` é relativo à pasta do projeto ou absoluto; arquivo de fora é copiado para dados/
    (nada em dados/ é sobrescrito). `aba` escolhe a aba do Excel (padrão: a primeira).
    Em caso de erro, devolve ok=false com a explicação e as linhas afetadas."""
    try:
        return _resumo_ingestao(_ingerir(projeto(), caminho, nome, aba))
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def ingerir_texto(texto: str, nome: str) -> dict:
    """Ingere uma tabela colada como texto (por exemplo, copiada do Excel): grava dados/<nome>.csv
    com o texto exatamente como veio e segue a ingestão normal."""
    try:
        return _resumo_ingestao(_ingerir_texto(projeto(), texto, nome))
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def perfilar(tabela: str) -> dict:
    """Perfil e validação de uma tabela já ingerida: tipos, vazios, período, chaves, dados pessoais,
    bloqueios e alertas. Grava o relatório completo em saidas/bi/perfil/<tabela>.qualidade.json
    e devolve a versão curta."""
    try:
        return {"ok": True, **resumo(_perfilar(projeto(), tabela))}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def propor_modelo(tabela: str | None = None, sobrescrever: bool = False) -> dict:
    """Escreve um rascunho de modelo/metricas.yaml a partir das colunas da fonte: a tabela ingerida
    informada, ou saidas/dados_tratados.parquet da análise. Descrições vêm do dicionário do
    contexto.md quando existe. Não sobrescreve um modelo existente sem `sobrescrever=true`."""
    try:
        return {"ok": True, **propor(projeto(), tabela, sobrescrever)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def validar_modelo() -> dict:
    """Valida modelo/metricas.yaml contra o arquivo da fonte e registra no manifesto a definição,
    as colunas e a origem (com hash) de cada métrica. Devolve a lista de métricas e dimensões."""
    try:
        modelo, arquivo, _ = carregar(projeto())
        linhagem = registrar_linhagem(projeto(), modelo, arquivo)
    except ErroDeLeitura as e:
        return _erro(e)
    return {"ok": True, "fonte": linhagem and next(iter(linhagem.values()))["fonte"],
            "metricas": {n: {k: l[k] for k in ("descricao", "tipo", "formato", "definicao", "colunas")}
                         for n, l in linhagem.items()},
            "dimensoes": {n: {"coluna": d["coluna"], "granularidade": d.get("granularidade"),
                              "descricao": d.get("descricao", "")} for n, d in modelo["dimensoes"].items()}}


@mcp.tool()
def consultar(metricas: list[str], dimensoes: list[str] | None = None, filtros: list[dict] | None = None,
              periodo: str = "tudo", comparacao: str = "nenhuma", ordenacao: str | None = None,
              limite: int | None = None) -> dict:
    """Calcula métricas do modelo, abertas por dimensões. `filtros`: [{dimensao, operador: em|fora_de,
    valores}]. `periodo`: tudo, ultimos_trinta_dias, ultimo_mes, ultimo_trimestre, ano_corrente,
    ultimo_ano_completo (relativos à data mais recente dos dados). `comparacao`: nenhuma,
    periodo_anterior, mesmo_periodo_ano_anterior. `ordenacao`: maior_primeiro, menor_primeiro,
    cronologica, alfabetica. Use os textos de `formatado` ao mostrar números ao usuário."""
    try:
        return {"ok": True, **para_json(_consultar(projeto(), metricas, dimensoes, filtros, periodo, comparacao,
                                                    ordenacao, limite))}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def exportar_cubo(nome: str, metricas: list[str], dimensoes: list[str], periodo: str = "tudo",
                  comparacao: str = "nenhuma") -> dict:
    """Grava saidas/bi/cubos/<nome>.json: componentes somáveis das métricas no grão das dimensões,
    com a receita de recálculo de cada métrica, para o dashboard refiltrar no navegador."""
    try:
        return {"ok": True, **_exportar_cubo(projeto(), nome, metricas, dimensoes, periodo, comparacao)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def propor_estilos(tabela: str | None = None) -> dict:
    """Infere o domínio dos dados (marketing, vendas, financeiro, operacoes, rh ou outro) pelos nomes
    das colunas e pelo contexto.md, e propõe duas opções de estilo e os blocos típicos do domínio.
    Não grava nada."""
    try:
        return {"ok": True, **_design.propor_estilos(projeto(), tabela)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def aplicar_estilo(estilo: str, dominio: str | None = None, com_acento: bool = True) -> dict:
    """Grava design/tokens.json e tokens.css a partir de um estilo base (claro, escuro, corporativo,
    alto_contraste), com o acento do domínio quando informado. Contraste AA conferido e ajustado."""
    try:
        return {"ok": True, **_design.aplicar_estilo(projeto(), estilo, dominio, com_acento)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def importar_design(caminho: str) -> dict:
    """Lê um design system enviado (DESIGN.md, tema JSON do Power BI, CSS com variáveis, tokens.json
    ou estilos/design-system.md do analise-dados) e grava design/tokens.json e tokens.css nos modos
    claro e escuro, com contraste AA. Devolve cada ajuste de contraste feito."""
    try:
        return {"ok": True, **_design.importar(projeto(), caminho)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def renderizar_dashboard() -> dict:
    """Confere dashboard/spec.json contra o schema e o modelo, calcula cada bloco no DuckDB (para todas
    as combinações dos filtros globais) e grava saidas/bi/dashboard.html (abre no navegador) e
    saidas/bi/dashboard.artifact.html (para publicar como Artifact). Devolve tamanho, avisos e, em
    `publicacao_bloqueada`, os motivos para não publicar (dados pessoais)."""
    try:
        return {"ok": True, **renderizar(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def gerar_achados() -> dict:
    """Calcula os achados que o documento de decisão pode citar (total, líderes, concentração,
    amplitude das razões, composição de valores com sinal, série mensal, cobertura dos dados) e grava
    saidas/bi/achados.json. Cada achado tem id (A1, A2…), valores e textos formatados."""
    try:
        return {"ok": True, **_gerar_achados(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def reproduzir_conclusao() -> dict:
    """Confere cada número da conclusão do analise.ipynb com a camada de métricas, seguindo
    decisao/verificacoes.yaml. Grava saidas/bi/reproducao.json com o estado de cada item:
    reproduzido, nao_reproduzido ou sem_numero."""
    try:
        return {"ok": True, **reproduzir(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def verificar_documento() -> dict:
    """Confere decisao/documento.md: seções obrigatórias, de três a cinco achados citando [A…] ou [C…]
    reproduzido, e se cada número do texto vem de um valor calculado. Lista cada número com a origem."""
    try:
        return {"ok": True, **_verificar_documento(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def renderizar_documento() -> dict:
    """Renderiza o documento de decisão (saidas/bi/decisao.html e decisao.artifact.html) com o apêndice
    de método gerado sem o modelo de linguagem. Recusa se a verificação dos números não passar."""
    try:
        return {"ok": True, **_renderizar_documento(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def converter_pbix(caminho: str, testar_equivalencia: bool = True, sobrescrever: bool = False) -> dict:
    """Converte um .pbix em modo de importação (caminho absoluto ou relativo à pasta do projeto).
    Extrai as tabelas (contagem de linhas conferida), classifica cada medida DAX (traduzida, texto ou
    não traduzida, com o motivo), grava saidas/bi/pbix/plano.parquet e modelo/metricas.yaml, escreve
    uma spec por página em dashboard/paginas/ (a primeira vira dashboard/spec.json), importa o tema,
    testa cada medida traduzida contra o motor DAX do pbix-mcp numa amostra de contextos e renderiza as
    páginas em saidas/bi/paginas/. O relatório de fidelidade fica em saidas/bi/pbix/fidelidade.md.
    DirectQuery e conexão dinâmica são recusados com a explicação e a via (b). Leva de segundos a
    alguns minutos, conforme o tamanho do modelo."""
    try:
        return {"ok": True, **_converter_pbix(projeto(), caminho, testar_equivalencia, sobrescrever)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def montar_comparativo(link_power_bi: str | None = None, licenca: str = "free", pagina: str | None = None) -> dict:
    """Via (b): grava saidas/bi/comparativo/ com o relatório original do Power BI (num iframe) ao lado da
    página convertida pela via (a), o resumo da conversão e o status de cada visual. `link_power_bi`:
    link de Publicar na Web (app.powerbi.com/view?r=...) ou de incorporação segura
    (app.powerbi.com/reportEmbed?reportId=...); sem link, o lado do original mostra o passo a passo.
    `licenca`: free, pro ou ppu. `pagina`: nome da página convertida (padrão: a primeira). A pasta é
    estática (abre do disco ou em qualquer hospedagem); o Artifact do claude.ai não incorpora outros sites."""
    try:
        return {"ok": True, **_montar_comparativo(projeto(), link_power_bi, licenca, pagina)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def exportar_offline(spec: str | None = None) -> dict:
    """Grava o dashboard num HTML autocontido, que abre sem internet (ECharts embutido, fontes do
    sistema): saidas/bi/dashboard.offline.html. `spec`, se informado, é outra spec do projeto (por
    exemplo dashboard/paginas/<pagina>.json), gravada em saidas/bi/paginas/<pagina>.offline.html.
    Recusa quando há dados pessoais. Na primeira vez, baixa o ECharts do cdnjs (conferido pelo hash)
    para o cache do usuário."""
    try:
        destino = None
        if spec:
            from pathlib import Path as _P
            destino = _P("saidas") / "bi" / "paginas" / (_P(spec).stem + ".offline.html")
        return {"ok": True, **_exportar_offline(projeto(), spec, destino)}
    except ErroDeLeitura as e:
        return _erro(e)


@mcp.tool()
def renderizar_assistente() -> dict:
    """Grava saidas/bi/assistente.artifact.html: o dashboard com o painel "Pergunte ao dashboard" (o Claude
    responde só com os números do cubo; cada número é conferido antes de aparecer) e as perguntas de controle
    com resposta conhecida. Só funciona publicado como Artifact, com as capacidades devolvidas em
    `capacidades`. Recusa publicar (em `publicacao_bloqueada`) quando há dados pessoais."""
    try:
        return {"ok": True, **_renderizar_assistente(projeto())}
    except ErroDeLeitura as e:
        return _erro(e)


if __name__ == "__main__":
    mcp.run()
