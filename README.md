# bi-html — do dado ao BI dentro do Claude Code

Plugin do [Claude Code](https://code.claude.com) que fecha o ciclo
**Planilha → Análise → Dashboard → BI**. A análise fica com o plugin
[`analise-dados`](https://github.com/fernandofigueiredo-data/analise-dados-plugin);
o bi-html parte dela e gera um dashboard HTML e um documento de decisão em que
**nenhum número sai do modelo de linguagem**: o Claude desenha e escreve, e os
valores vêm de um servidor MCP com uma camada de métricas determinística.

**Estado:** fase F0 (fundações). O plano completo, com fases e critérios de
aceite, está em [`PLANO_DE_CONSTRUCAO.md`](PLANO_DE_CONSTRUCAO.md).

## O que já existe

| Peça | Onde |
|---|---|
| Schema da spec de dashboard (sem campo para valores; textos sem algarismos) | `plugins/bi-html/schemas/dashboard-spec.schema.json` |
| Validador da spec (linha de comando e MCP) | `plugins/bi-html/scripts/validar_spec.py`, ferramenta `validar_spec` |
| Servidor MCP `bi-dados` | `plugins/bi-html/mcp/servidor.py` |
| Comandos `/bi-html:ciclo` e `/bi-html:validar-spec` | `plugins/bi-html/commands/` |
| Contrato com o analise-dados | `plugins/bi-html/CONTRATO.md` |
| Dados fictícios (vendas, marketing, financeiro e casos de teste) | `fixtures/` |

## Instalar localmente

Requer o [`uv`](https://docs.astral.sh/uv/).

```bash
claude plugin marketplace add /caminho/para/este/repositorio
claude plugin install bi-html@bi-html
```

## Licença

MIT.
