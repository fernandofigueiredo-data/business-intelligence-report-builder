# Contrato entre o analise-dados e o bi-html

**Versão:** 0.1 · **analise-dados mínimo:** 1.1.0 · **Checagem:** `lib/bi_html/contrato.py`,
ferramenta `checar_contrato` do servidor `bi-dados`

A etapa de BI começa quando a etapa de análise entrega os três arquivos abaixo
na pasta do projeto. Cada um recebe um estado: `ok`, `alerta` (utilizável, com
algo a conferir) ou `ausente`/`invalido` (bloqueia a passagem, com a correção
indicada). O projeto está pronto para o BI quando nenhum item bloqueia.

| Arquivo | Quem grava | Bloqueia quando | Alerta quando | O que o bi-html reaproveita |
|---|---|---|---|---|
| `contexto.md` | `/analise` do analise-dados | Não existe; ou **Pergunta de negócio** ou **Quem lê o resultado** está vazio ou com `?` | Sem dicionário de colunas; ou sem **Decisão que a análise apoia** | Objetivo (pergunta, público, decisão), dicionário de colunas, decisões de tratamento |
| `analise.ipynb` | `/analise` do analise-dados | Não existe; não é um notebook legível; não tem célula markdown com título de conclusão (`## Conclusão`) | As células de código não foram executadas de cima a baixo (rode `/validar`) | Itens da conclusão, que viram métricas candidatas; só entram no documento de decisão os que a camada de métricas reproduz |
| `saidas/dados_tratados.parquet` | Notebook da análise (o `/painel` do analise-dados insere a célula se faltar) | Não existe; não é legível; não tem linhas | Colunas com vazios; colunas do dicionário que sumiram; colunas novas sem definição no `contexto.md` (nem no dicionário, nem citadas entre crases nas decisões de tratamento); notebook alterado depois da gravação | Esquema (colunas, tipos, vazios) e a base da camada de métricas |

Opcional: `estilos/design-system.md` (paleta do analise-dados), lido como ponto
de partida do design quando o usuário não envia outro.

Os campos do `contexto.md` seguem o formato que o `/analise` grava: itens
`- **Rótulo:** valor` na seção `## Objetivo`, tabelas `| Coluna | Significado | … |`
abaixo de `### <arquivo>` na seção `## Dados` e itens na seção
`## Decisões de tratamento`.

Mudanças neste contrato sobem a versão e precisam de teste nos dois
repositórios. O teste de referência usa uma cópia do projeto de exemplo do
analise-dados em `tests/dados/projeto_exemplo/`.
