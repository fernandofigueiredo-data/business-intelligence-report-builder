# F6 — prova de conceito .pbix: matriz 5.1 testada

Gerado por `provas/f6/executar.py` a partir de `resultados.json`; não edite à mão.

**Execução:** 2026-11-17T13:59:05-03:00 · Python 3.12.14 · pbix-mcp 0.9.153 · pbixray 0.15.5 · DuckDB 2.0.0 · Apple M2, 16 GB, Darwin 27.3.0

**Escala:** **I** = integral, **P** = parcial, **N** = não extraível. Uma célula testada leva a pior classificação entre os arquivos daquele modo; o detalhe por arquivo e a saída das ferramentas estão abaixo. Célula não testada mantém a classificação documental do plano, entre parênteses.

## Arquivos

| Apelido | Arquivo | Tamanho | SHA-256 (12) | Modo detectado |
|---|---|---|---|---|
| `ifdata` | M5_Dashboard_IFdata.pbix | 0,3 MB | `2823516303e5` | Importação |
| `eleicoes` | eleicoes-presidenciais-br - final - cópia.pbix | 2,7 MB | `ff59c36e4ffc` | Importação |
| `lab1` | Lab1_reorganizado.pbix | 1,8 MB | `b202077ae9a0` | Importação |

## Matriz

| Elemento | Importação | DirectQuery | Conexão dinâmica |
|---|---|---|---|
| Dados das tabelas | **I** · testada (3 de 3) | não testada (documental: N) | não testada (documental: N) |
| Modelo e relacionamentos | **I** · testada (3 de 3) | não testada (documental: I) | não testada (documental: N) |
| Medidas DAX (texto) | **I** · testada (2 de 3) | não testada (documental: I) | não testada (documental: P) |
| Medidas DAX (cálculo) | **I** · testada (2 de 3) | não testada (documental: N) | não testada (documental: N) |
| Consultas Power Query (M) | **P** · testada (3 de 3) | não testada (documental: P) | não testada (documental: N) |
| Layout de páginas e visuais | **P** · testada (3 de 3) | não testada (documental: P) | não testada (documental: P) |
| Filtros e segmentações | **P** · testada (3 de 3) | não testada (documental: P) | não testada (documental: P) |
| Temas | **P** · testada (3 de 3) | não testada (documental: I/P) | não testada (documental: I/P) |
| Visuais personalizados | — · sem o elemento nos 3 arquivos (documental: N) | não testada (documental: N) | não testada (documental: N) |
| Segurança por linha (RLS) | — · sem o elemento nos 3 arquivos (documental: P) | não testada (documental: P) | não testada (documental: N) |

**DirectQuery e Conexão dinâmica:** nenhum dos arquivos enviados está nesse modo, então essas colunas continuam com a base documental. Para testá-las, basta rodar o script de novo com um .pbix em cada modo.

## Resultado por arquivo

### Dados das tabelas

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 2 tabelas e 1.622 linhas lidas por inteiro; contagem e conteúdo de cada coluna iguais nos dois leitores | I | [pbix_list_tables.txt](saidas/ifdata/dados__pbix_list_tables.txt) · [comparacao.json](saidas/ifdata/dados__comparacao.json) |
| `eleicoes` | 7 tabelas e 360.990 linhas lidas por inteiro; contagem e conteúdo de cada coluna iguais nos dois leitores | I | [pbix_list_tables.txt](saidas/eleicoes/dados__pbix_list_tables.txt) · [comparacao.json](saidas/eleicoes/dados__comparacao.json) |
| `lab1` | 3 tabelas e 52.752 linhas lidas por inteiro; contagem e conteúdo de cada coluna iguais nos dois leitores | I | [pbix_list_tables.txt](saidas/lab1/dados__pbix_list_tables.txt) · [comparacao.json](saidas/lab1/dados__comparacao.json) |

### Modelo e relacionamentos

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 22 colunas e 0 relações; iguais nos dois leitores | I | [pbix_get_model_schema.txt](saidas/ifdata/modelo__pbix_get_model_schema.txt) · [pbix_get_model_relationships.txt](saidas/ifdata/modelo__pbix_get_model_relationships.txt) · [comparacao.json](saidas/ifdata/modelo__comparacao.json) |
| `eleicoes` | 48 colunas e 5 relações; iguais nos dois leitores | I | [pbix_get_model_schema.txt](saidas/eleicoes/modelo__pbix_get_model_schema.txt) · [pbix_get_model_relationships.txt](saidas/eleicoes/modelo__pbix_get_model_relationships.txt) · [comparacao.json](saidas/eleicoes/modelo__comparacao.json) |
| `lab1` | 28 colunas e 0 relações; iguais nos dois leitores; 1 relação com a tabela de datas automática, que só o pbix-mcp lista | I | [pbix_get_model_schema.txt](saidas/lab1/modelo__pbix_get_model_schema.txt) · [pbix_get_model_relationships.txt](saidas/lab1/modelo__pbix_get_model_relationships.txt) · [comparacao.json](saidas/lab1/modelo__comparacao.json) |

### Medidas DAX (texto)

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 19 medidas, 0 colunas calculadas e 0 tabelas calculadas; texto integral igual nos dois leitores (19 medidas idênticas caractere a caractere); a saída formatada de pbix_get_model_measures corta expressões longas, o texto integral vem do leitor do pacote | I | [pbix_get_model_measures.txt](saidas/ifdata/dax_texto__pbix_get_model_measures.txt) · [medidas.json](saidas/ifdata/dax_texto__medidas.json) |
| `eleicoes` | 55 medidas, 2 colunas calculadas e 1 tabela calculada; texto integral igual nos dois leitores (55 medidas idênticas caractere a caractere); a saída formatada de pbix_get_model_measures corta expressões longas, o texto integral vem do leitor do pacote | I | [pbix_get_model_measures.txt](saidas/eleicoes/dax_texto__pbix_get_model_measures.txt) · [medidas.json](saidas/eleicoes/dax_texto__medidas.json) · [colunas_e_tabelas_calculadas.json](saidas/eleicoes/dax_texto__colunas_e_tabelas_calculadas.json) |
| `lab1` | o arquivo não tem medidas, colunas nem tabelas calculadas em DAX do autor (os visuais usam agregação implícita; só há a tabela de datas automática) | — | [pbix_get_model_measures.txt](saidas/lab1/dax_texto__pbix_get_model_measures.txt) · [medidas.json](saidas/lab1/dax_texto__medidas.json) |

### Medidas DAX (cálculo)

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 19 de 19 medidas avaliadas sem erro; 9 de 9 conferências contra SQL independente batem; todas as medidas juntas em 0,2 s, a conferência mais lenta (ROE Médio Simples) em 0,1 s | I | [cobertura.json](saidas/ifdata/dax_calculo__cobertura.json) · [paridade.json](saidas/ifdata/dax_calculo__paridade.json) |
| `eleicoes` | 55 de 55 medidas avaliadas sem erro; 11 de 11 conferências contra SQL independente batem; todas as medidas juntas em 103,1 s, a conferência mais lenta (Municípios Vencidos) em 16,4 s | I | [cobertura.json](saidas/eleicoes/dax_calculo__cobertura.json) · [paridade.json](saidas/eleicoes/dax_calculo__paridade.json) |
| `lab1` | o arquivo não tem medidas DAX para avaliar (os visuais usam agregação implícita) | — | [pbix_get_model_measures.txt](saidas/lab1/dax_calculo__pbix_get_model_measures.txt) |

### Consultas Power Query (M)

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | texto M de 2 de 2 tabelas e de 1 consulta compartilhada lido (igual no pbixray); execução não tentada: 1 de 2 consultas com a origem disponível aqui (dados embutidos); as demais leem arquivos de outra máquina; as consultas compartilhadas só aparecem nos metadados (pbix_datamodel_query_metadata), não em pbix_get_model_power_query | P | [pbix_get_model_power_query.txt](saidas/ifdata/m__pbix_get_model_power_query.txt) · [pbix_get_m_code.txt](saidas/ifdata/m__pbix_get_m_code.txt) · [pbix_list_data_sources.txt](saidas/ifdata/m__pbix_list_data_sources.txt) · [pbix_datamodel_query_metadata_Expression.txt](saidas/ifdata/m__pbix_datamodel_query_metadata_Expression.txt) · [fontes.json](saidas/ifdata/m__fontes.json) |
| `eleicoes` | texto M de 6 de 6 tabelas e de 2 consultas compartilhadas lido (igual no pbixray), mais 1 tabela calculada em DAX; execução não tentada: 1 de 6 consultas com a origem disponível aqui (dados embutidos); as demais leem arquivos de outra máquina; as consultas compartilhadas só aparecem nos metadados (pbix_datamodel_query_metadata), não em pbix_get_model_power_query; pbix_list_data_sources rotula como Embedded 5 tabelas cuja origem é um arquivo lido por consulta compartilhada | P | [pbix_get_model_power_query.txt](saidas/eleicoes/m__pbix_get_model_power_query.txt) · [pbix_get_m_code.txt](saidas/eleicoes/m__pbix_get_m_code.txt) · [pbix_list_data_sources.txt](saidas/eleicoes/m__pbix_list_data_sources.txt) · [pbix_datamodel_query_metadata_Expression.txt](saidas/eleicoes/m__pbix_datamodel_query_metadata_Expression.txt) · [fontes.json](saidas/eleicoes/m__fontes.json) |
| `lab1` | texto M de 1 de 1 tabela e de 0 consultas compartilhadas lido (igual no pbixray), mais 2 tabelas calculadas em DAX; execução não tentada: 0 de 1 consulta com a origem disponível aqui (dados embutidos); as demais leem arquivos de outra máquina | P | [pbix_get_model_power_query.txt](saidas/lab1/m__pbix_get_model_power_query.txt) · [pbix_get_m_code.txt](saidas/lab1/m__pbix_get_m_code.txt) · [pbix_list_data_sources.txt](saidas/lab1/m__pbix_list_data_sources.txt) · [pbix_datamodel_query_metadata_Expression.txt](saidas/lab1/m__pbix_datamodel_query_metadata_Expression.txt) · [fontes.json](saidas/lab1/m__fontes.json) |

### Layout de páginas e visuais

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | PBIR: 2 páginas e 18 visuais lidos com tipo e posição (iguais no JSON do relatório); 9 de 10 visuais de dados têm bloco equivalente no bi-html; sem bloco: scatterChart (1) | P | [pbix_get_pages.txt](saidas/ifdata/layout__pbix_get_pages.txt) · [pbix_get_page_visuals.json](saidas/ifdata/layout__pbix_get_page_visuals.json) · [visuais_por_tipo.json](saidas/ifdata/layout__visuais_por_tipo.json) |
| `eleicoes` | PBIR: 8 páginas e 94 visuais lidos com tipo e posição (iguais no JSON do relatório); 40 de 47 visuais de dados têm bloco equivalente no bi-html; sem bloco: azureMap (5), scatterChart (2) | P | [pbix_get_pages.txt](saidas/eleicoes/layout__pbix_get_pages.txt) · [pbix_get_page_visuals.json](saidas/eleicoes/layout__pbix_get_page_visuals.json) · [visuais_por_tipo.json](saidas/eleicoes/layout__visuais_por_tipo.json) |
| `lab1` | PBIR: 1 página e 10 visuais lidos com tipo e posição (iguais no JSON do relatório); 4 de 5 visuais de dados têm bloco equivalente no bi-html; sem bloco: azureMap (1) | P | [pbix_get_pages.txt](saidas/lab1/layout__pbix_get_pages.txt) · [pbix_get_page_visuals.json](saidas/lab1/layout__pbix_get_page_visuals.json) · [visuais_por_tipo.json](saidas/lab1/layout__visuais_por_tipo.json) |

### Filtros e segmentações

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 4 segmentações, 0 filtros de página (conferem com o JSON), 4 filtros de visual, 0 seleções padrão de segmentação e 4 interações editadas; filtros de visual e interações só aparecem no JSON do visual (não há ferramenta própria) | P | [pbix_get_filters_e_default_filters.json](saidas/ifdata/filtros__pbix_get_filters_e_default_filters.json) · [contagem_no_json.json](saidas/ifdata/filtros__contagem_no_json.json) |
| `eleicoes` | 10 segmentações, 2 filtros de página (conferem com o JSON), 64 filtros de visual, 9 seleções padrão de segmentação e 19 interações editadas; filtros de visual e interações só aparecem no JSON do visual (não há ferramenta própria) | P | [pbix_get_filters_e_default_filters.json](saidas/eleicoes/filtros__pbix_get_filters_e_default_filters.json) · [contagem_no_json.json](saidas/eleicoes/filtros__contagem_no_json.json) |
| `lab1` | 3 segmentações, 0 filtros de página (conferem com o JSON), 1 filtro de visual, 0 seleções padrão de segmentação e 0 interações editadas; filtros de visual e interações só aparecem no JSON do visual (não há ferramenta própria) | P | [pbix_get_filters_e_default_filters.json](saidas/lab1/filtros__pbix_get_filters_e_default_filters.json) · [contagem_no_json.json](saidas/lab1/filtros__contagem_no_json.json) |

### Temas

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | 2 temas devolvidos por pbix_get_theme; o tema em uso (IFData_Navy_Teal5276342275015783.json) está entre eles; importado (pbix_get_theme) como design system do bi-html com contraste AA e 5 ajustes de cor | I | [pbix_get_theme.txt](saidas/ifdata/tema__pbix_get_theme.txt) · [importacao_bi_html.json](saidas/ifdata/tema__importacao_bi_html.json) |
| `eleicoes` | 2 temas devolvidos por pbix_get_theme; o tema em uso (Elei__es_BR12491567103830592.json) está entre eles; importado (pbix_get_theme) como design system do bi-html com contraste AA e 2 ajustes de cor | I | [pbix_get_theme.txt](saidas/eleicoes/tema__pbix_get_theme.txt) · [importacao_bi_html.json](saidas/eleicoes/tema__importacao_bi_html.json) |
| `lab1` | 1 tema devolvido por pbix_get_theme; o tema em uso (CopilotDefault, SharedResources) não está entre eles; importado (lido do pacote, CopilotDefault.json) como design system do bi-html com contraste AA e 0 ajustes de cor | P | [pbix_get_theme.txt](saidas/lab1/tema__pbix_get_theme.txt) · [importacao_bi_html.json](saidas/lab1/tema__importacao_bi_html.json) |

### Visuais personalizados

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | nenhum visual personalizado (8 tipos de visual, todos nativos) | — | [pbix_list_resources.txt](saidas/ifdata/visuais_personalizados__pbix_list_resources.txt) · [deteccao.json](saidas/ifdata/visuais_personalizados__deteccao.json) |
| `eleicoes` | nenhum visual personalizado (13 tipos de visual, todos nativos) | — | [pbix_list_resources.txt](saidas/eleicoes/visuais_personalizados__pbix_list_resources.txt) · [deteccao.json](saidas/eleicoes/visuais_personalizados__deteccao.json) |
| `lab1` | nenhum visual personalizado (7 tipos de visual, todos nativos) | — | [pbix_list_resources.txt](saidas/lab1/visuais_personalizados__pbix_list_resources.txt) · [deteccao.json](saidas/lab1/visuais_personalizados__deteccao.json) |

### Segurança por linha (RLS)

| Arquivo | Resultado | Classificação | Saída anexada |
|---|---|---|---|
| `ifdata` | nenhum papel de RLS no arquivo (pbix-mcp e pbixray concordam) | — | [pbix_get_rls_roles.txt](saidas/ifdata/rls__pbix_get_rls_roles.txt) |
| `eleicoes` | nenhum papel de RLS no arquivo (pbix-mcp e pbixray concordam) | — | [pbix_get_rls_roles.txt](saidas/eleicoes/rls__pbix_get_rls_roles.txt) |
| `lab1` | nenhum papel de RLS no arquivo (pbix-mcp e pbixray concordam) | — | [pbix_get_rls_roles.txt](saidas/lab1/rls__pbix_get_rls_roles.txt) |

## Tempo e memória

Cada célula roda num processo próprio. *Abrir* é o `pbix_open`; *ferramenta* soma as chamadas do pbix-mcp do elemento; *conferência* soma o segundo leitor (pbixray), o DuckDB e a leitura do JSON do relatório; *pico* é o pico de memória residente do processo inteiro (abrir + ferramenta + conferência).

| Arquivo | Elemento | Abrir (s) | Ferramenta (s) | Conferência (s) | Processo (s) | Pico (MB) |
|---|---|---|---|---|---|---|
| `ifdata` | Detecção do modo | 0,75 | 0,01 | 0,00 | 1,01 | 65 |
| `ifdata` | Dados das tabelas | 0,50 | 0,04 | 0,07 | 1,29 | 124 |
| `ifdata` | Modelo e relacionamentos | 0,37 | 0,02 | 0,01 | 0,79 | 117 |
| `ifdata` | Medidas DAX (texto) | 0,39 | 0,01 | 0,02 | 0,97 | 114 |
| `ifdata` | Medidas DAX (cálculo) | 0,63 | 0,36 | 0,10 | 1,86 | 151 |
| `ifdata` | Consultas Power Query (M) | 0,59 | 0,05 | 0,02 | 1,40 | 113 |
| `ifdata` | Layout de páginas e visuais | 0,49 | 0,04 | 0,00 | 0,79 | 70 |
| `ifdata` | Filtros e segmentações | 0,60 | 0,01 | 0,00 | 0,78 | 65 |
| `ifdata` | Temas | 0,40 | 0,00 | 0,00 | 0,51 | 70 |
| `ifdata` | Visuais personalizados | 0,36 | 0,00 | 0,00 | 0,47 | 69 |
| `ifdata` | Segurança por linha (RLS) | 0,34 | 0,00 | 0,01 | 0,73 | 115 |
| `eleicoes` | Detecção do modo | 0,70 | 0,02 | 0,00 | 0,88 | 87 |
| `eleicoes` | Dados das tabelas | 1,02 | 0,78 | 3,67 | 9,15 | 244 |
| `eleicoes` | Modelo e relacionamentos | 0,71 | 0,07 | 0,04 | 1,61 | 142 |
| `eleicoes` | Medidas DAX (texto) | 0,83 | 0,07 | 0,04 | 1,91 | 156 |
| `eleicoes` | Medidas DAX (cálculo) | 1,09 | 134,43 | 0,44 | 139,94 | 1.358 |
| `eleicoes` | Consultas Power Query (M) | 0,45 | 0,11 | 0,03 | 1,03 | 160 |
| `eleicoes` | Layout de páginas e visuais | 0,37 | 0,10 | 0,00 | 0,59 | 94 |
| `eleicoes` | Filtros e segmentações | 0,40 | 0,20 | 0,00 | 0,76 | 94 |
| `eleicoes` | Temas | 0,45 | 0,01 | 0,00 | 0,63 | 94 |
| `eleicoes` | Visuais personalizados | 0,44 | 0,00 | 0,00 | 0,59 | 94 |
| `eleicoes` | Segurança por linha (RLS) | 0,39 | 0,02 | 0,03 | 0,82 | 144 |
| `lab1` | Detecção do modo | 0,39 | 0,01 | 0,00 | 0,52 | 76 |
| `lab1` | Dados das tabelas | 0,36 | 0,27 | 1,03 | 2,73 | 181 |
| `lab1` | Modelo e relacionamentos | 0,38 | 0,04 | 0,02 | 0,89 | 129 |
| `lab1` | Medidas DAX (texto) | 0,36 | 0,02 | 0,02 | 0,77 | 129 |
| `lab1` | Medidas DAX (cálculo) | 0,34 | 0,01 | 0,00 | 0,49 | 83 |
| `lab1` | Consultas Power Query (M) | 0,34 | 0,07 | 0,02 | 0,82 | 132 |
| `lab1` | Layout de páginas e visuais | 0,35 | 0,00 | 0,00 | 0,46 | 76 |
| `lab1` | Filtros e segmentações | 0,35 | 0,01 | 0,00 | 0,45 | 76 |
| `lab1` | Temas | 0,36 | 0,00 | 0,00 | 0,49 | 76 |
| `lab1` | Visuais personalizados | 0,35 | 0,00 | 0,00 | 0,46 | 76 |
| `lab1` | Segurança por linha (RLS) | 0,34 | 0,01 | 0,02 | 0,74 | 126 |
