# bi-html — do dado ao BI dentro do Claude Code

Plugin do [Claude Code](https://code.claude.com) que fecha o ciclo
**Planilha → Análise → Dashboard → BI**. A análise fica com o plugin
[`analise-dados`](https://github.com/fernandofigueiredo-data/analise-dados-plugin);
o bi-html parte dela e gera um dashboard HTML e um documento de decisão em que
**nenhum número sai do modelo de linguagem**: o Claude desenha e escreve, e os
valores vêm de um servidor MCP com uma camada de métricas determinística.

**Estado:** fases F0 (fundações), F0b (contrato com o analise-dados), F1 (ingestão e perfil), F2 (camada de métricas), F3 (design), F4 (dashboard e publicação), F5 (documento de decisão) e F6 (prova de conceito com .pbix reais). O plano completo, com fases e critérios de
aceite, está em [`PLANO_DE_CONSTRUCAO.md`](PLANO_DE_CONSTRUCAO.md).

## O que já existe

| Peça | Onde |
|---|---|
| Schema da spec de dashboard (sem campo para valores; textos sem algarismos) | `plugins/bi-html/schemas/dashboard-spec.schema.json` |
| Validador da spec (linha de comando e MCP) | `plugins/bi-html/scripts/validar_spec.py`, ferramenta `validar_spec` |
| Servidor MCP `bi-dados` | `plugins/bi-html/mcp/servidor.py` |
| Comandos `/bi-html:ciclo`, `/bi-html:ingerir`, `/bi-html:metricas`, `/bi-html:design`, `/bi-html:dashboard`, `/bi-html:decisao` e `/bi-html:validar-spec` | `plugins/bi-html/commands/` |
| Camada de métricas: `modelo/metricas.yaml`, consulta com períodos e comparação, cubo para o dashboard e linhagem no manifesto (ferramentas `propor_modelo`, `validar_modelo`, `consultar`, `exportar_cubo`) | `plugins/bi-html/lib/bi_html/modelo.py`, `consulta.py` |
| Ingestão (CSV, Excel, texto colado) e perfil com dados pessoais (ferramentas `ingerir`, `ingerir_texto`, `perfilar`) | `plugins/bi-html/lib/bi_html/ingestao.py`, `perfil.py` |
| Contrato com o analise-dados e sua checagem (ferramenta `checar_contrato`) | `plugins/bi-html/CONTRATO.md`, `plugins/bi-html/lib/bi_html/contrato.py` |
| Cópia do projeto de exemplo do analise-dados, usada como teste de contrato | `tests/dados/projeto_exemplo/` |
| Design: tokens nos modos claro e escuro com contraste AA, importação de DESIGN.md, tema do Power BI e CSS, estilos base e inferência de domínio (ferramentas `importar_design`, `propor_estilos`, `aplicar_estilo`) | `plugins/bi-html/lib/bi_html/design.py`, `cores.py` |
| Dashboard: blocos calculados no DuckDB para cada combinação de filtros, HTML com ECharts que só formata e desenha, versão para publicar como Artifact (ferramenta `renderizar_dashboard`) | `plugins/bi-html/lib/bi_html/dashboard.py`, `render.py` |
| Documento de decisão: achados calculados, reprodução da conclusão da análise, verificador que rastreia cada número do texto e HTML em até duas páginas A4 (ferramentas `gerar_achados`, `reproduzir_conclusao`, `verificar_documento`, `renderizar_documento`) | `plugins/bi-html/lib/bi_html/achados.py`, `conclusao.py`, `verificador.py`, `documento.py` |
| Quatro exemplos: vendas, marketing e financeiro pelo atalho, e o ciclo completo (análise do analise-dados → dashboard → documento de decisão) | `exemplos/` (monte com `exemplos/construir.py`) |
| Dados fictícios (vendas, marketing, financeiro, casos de teste e design systems de exemplo) | `fixtures/` |
| Prova de conceito .pbix: a matriz de viabilidade do plano testada com três arquivos reais em importação, com a saída de cada ferramenta, tempo e memória | `provas/f6/` (resultado em `provas/f6/MATRIZ.md`) |

## Instalar localmente

Requer o [`uv`](https://docs.astral.sh/uv/).

```bash
claude plugin marketplace add /caminho/para/este/repositorio
claude plugin install bi-html@bi-html
```

## Licença

MIT.
