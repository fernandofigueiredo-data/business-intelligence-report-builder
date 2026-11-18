"""
Instruções do servidor MCP `bi-dados` para o Claude.

Os comandos `/bi-html:*` mandam ler o REGRAS.md, mas uma pergunta em texto livre não passa por
eles: sem instruções, o Claude só usa as ferramentas se decidir por conta própria (os evals de
18/11/2026 mostraram isso: nas execuções com o plugin, o `perfilar` não foi chamado diante de uma
planilha com CPF). Este texto diz quando usar cada ferramenta nesses pedidos e aponta o REGRAS.md
para o resto.

O Claude Code corta instruções longas de servidor MCP, então o texto fica abaixo de LIMITE e o que
importa vem primeiro. As regras completas continuam só no REGRAS.md.
"""
from __future__ import annotations

from pathlib import Path

LIMITE = 2048

TEXTO = """\
Servidor de dados do plugin bi-html: é o único caminho para números sobre os dados do projeto \
(a pasta atual). Use estas ferramentas também quando o pedido vier em texto livre, sem comando /bi-html.

- Pergunta sobre um valor (total, média, recorte, ranking, comparação): `validar_modelo` lista as \
métricas e dimensões; depois chame `consultar` com métricas, filtros e período e responda com o \
texto de `formatado`. Nunca some, calcule nem estime de cabeça, nem a partir de linhas lidas do arquivo.
- Valor que nenhuma métrica cobre (por exemplo, lucro sem custo nos dados): diga que os dados não \
permitem e o que faltaria. Não escreva número.
- Planilha nova: `ingerir` e depois `perfilar`, antes de ler o arquivo ou responder. Se o perfil \
apontar dados pessoais (CPF, e-mail, telefone), não publique nem exporte e nunca repita esses \
valores na resposta: diga quais colunas e que é preciso removê-las ou agregá-las.
- Antes de somar uma coluna, confira se ela repete o mesmo valor em várias linhas do mesmo grupo \
(zona, loja, cliente): somar essa coluna infla o total, e o perfil ainda não avisa.
- Sem projeto pronto, `estado_do_ciclo` diz em que etapa a pasta está e qual é o próximo passo.
- Dashboard, documento de decisão e .pbix: os comandos /bi-html:dashboard, /bi-html:decisao e \
/bi-html:pbix conduzem o fluxo.

Regras completas: {regras}. Leia antes de montar dashboard, documento ou conversão."""


def instrucoes(plugin: Path) -> str:
    """Texto de instruções do servidor, com o caminho do REGRAS.md deste plugin."""
    return TEXTO.format(regras=Path(plugin) / "REGRAS.md")
