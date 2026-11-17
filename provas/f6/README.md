# F6 — prova de conceito com .pbix reais

A matriz 5.1 do plano tinha base só documental. Aqui ela foi testada com três
.pbix seus, em modo de importação: o painel do IF.data (`ifdata`), o das
eleições presidenciais (`eleicoes`) e o do laboratório de vendas globais do
curso (`lab1`).

- **Resultado célula a célula, com a saída das ferramentas anexada, tempo e memória:** [`MATRIZ.md`](MATRIZ.md)
- **Dados brutos da execução:** [`resultados.json`](resultados.json) e [`saidas/`](saidas/)
- **Referências de cálculo DAX (SQL escrito à mão):** [`referencias.yaml`](referencias.yaml)

## Como rodar

```bash
uv run --no-project --python 3.12 --with pbix-mcp==0.9.153 --with pbixray==0.15.5 --with duckdb --with pyyaml python -I provas/f6/executar.py --arquivo ifdata=/caminho/M5_Dashboard_IFdata.pbix --arquivo eleicoes=/caminho/eleicoes.pbix --arquivo lab1=/caminho/Lab1_reorganizado.pbix
```

Leva cerca de 2 minutos num Apple M2 (quase tudo é a avaliação DAX do arquivo
de eleições). Sem `--arquivo`, o script só regenera `MATRIZ.md` a partir de
`resultados.json`. Para testar as colunas DirectQuery e conexão dinâmica, basta
passar um arquivo em cada modo: o modo é detectado sozinho.

## Como cada célula foi testada

Cada elemento de cada arquivo roda num processo próprio, que abre o .pbix com
o `pbix-mcp`, chama as ferramentas do elemento (as mesmas funções que o
servidor MCP expõe) e confere o resultado com uma fonte independente:

| Elemento | Conferência independente |
|---|---|
| Dados | `pbixray` lê as mesmas tabelas; contagem de linhas e hash de cada coluna nos dois leitores |
| Modelo | colunas e relações do `pbixray` |
| DAX (texto) | expressões do `pbixray`, caractere a caractere |
| DAX (cálculo) | todas as medidas num contexto (contagem de erros) e 20 conferências em contextos com filtro contra SQL escrito à mão no DuckDB, sobre as tabelas do `pbixray` |
| M | texto do `pbixray`; origem de cada consulta seguida até o arquivo, inclusive por consulta compartilhada |
| Layout e filtros | JSON do relatório (PBIR) lido direto do pacote |
| Tema | tema em uso segundo o `report.json`; importação pelo `importar_design` do bi-html, com contraste AA |
| Visuais personalizados e RLS | pacotes de visual no `report.json` e papéis no `pbixray` |

Os anexos não levam dados das tabelas (só contagens e hashes), caminhos de
origem viram só o nome do arquivo e dados embutidos em base64 nas consultas M
são omitidos. O teste `tests/test_f6.py` confere isso.

## O que a F6 mostrou

1. **Importação lê por inteiro.** 415.364 linhas em 12 tabelas, com conteúdo
   idêntico nos dois leitores; colunas, relações e o texto das 74 medidas
   também batem.
2. **O cálculo DAX bateu nas 20 conferências**, inclusive `CALCULATE` com
   `REMOVEFILTERS`, `ALLSELECTED`, `TOPN`, `RANKX`, `SELECTEDVALUE` e a
   comparação com a eleição anterior. É uma amostra, não uma auditoria: a
   paridade continua precisando do teste de equivalência da F7.
3. **O cálculo DAX é caro em tabela grande.** No arquivo de eleições (309 mil
   linhas de votos), as 55 medidas num único contexto levaram 103 s na execução
   registrada em `MATRIZ.md` (entre 60 e 103 s em cinco execuções), com pico de
   1,4 a 1,7 GB; cada medida que itera municípios levou de 11 a 16 s. Nesse
   ritmo, pré-calcular uma grade grande pelo `pbix-mcp` (milhares de municípios
   × turnos × medidas) levaria horas: na F7, o híbrido precisa traduzir para SQL
   tudo o que for traduzível e pré-calcular só grades pequenas.
4. **O M é texto, não execução.** As origens são arquivos de outra máquina
   (Excel e CSV no caminho do Windows); só as tabelas "Inserir dados" seriam
   executáveis. As consultas compartilhadas só aparecem nos metadados
   (`pbix_datamodel_query_metadata`), e o `pbix_list_data_sources` rotula como
   "Embedded" as tabelas que leem CSV por elas.
5. **Layout e filtros são legíveis; a recriação é parcial.** Os três arquivos
   estão em PBIR (o layout legado não foi testado). 53 de 62 visuais de dados
   têm bloco equivalente no bi-html; faltam dispersão (`scatterChart`) e mapa do
   Azure (`azureMap`). Filtros de visual e interações editadas só aparecem no
   JSON do visual: não há ferramenta própria para eles.
6. **Tema:** o `pbix_get_theme` devolve o tema personalizado quando ele é um
   recurso registrado, mas no `lab1` não devolve o tema em uso (`CopilotDefault`,
   embutido do Power BI); lido do pacote, ele importa no bi-html com AA.
7. **Não testado com estes arquivos:** DirectQuery e conexão dinâmica (os três
   são importação), RLS e visuais personalizados (nenhum dos três tem).
8. **Ambiente:** o `pbix-mcp` exige `mcp<2` e o servidor `bi-dados` usa
   `mcp>=2.3`. A leitura de .pbix na F7 precisa rodar num processo à parte
   (como aqui) ou usar o `pbixray`, que não depende do MCP.
