# Plano de construção: BI com interface HTML e camada de dados governada

**Data:** 17/11/2026 · **Status:** planejamento, sem implementação · **Revisão 3:** incorpora suas respostas de 17/11 (uso pessoal, portfólio público com dados fictícios, execução dentro do Claude, design system enviado ou inferido) e o ciclo completo **Planilha → Análise → Dashboard → BI**, com o plugin `analise-dados` como etapa de análise

**Legenda epistêmica.** **[F]** fato verificado nesta sessão em documentação, página ou ambiente consultado (número da fonte no fim). **[I]** inferência minha a partir de fatos. **[H]** hipótese a validar. **[NV]** afirmação técnica não verificada nesta sessão.

**Estado das provas de conceito.** A F6 rodou em 17/11/2026 com três .pbix seus, todos em modo de importação; a coluna de importação da matriz 5.1 está **testada** [F21], e as colunas DirectQuery e conexão dinâmica continuam com base documental, à espera de um arquivo em cada modo. A F7 converteu os três arquivos [F22]; a F7b publicou o relatório fictício com Publicar na Web (conta Free) e o pôs ao lado do convertido na vitrine, com o teste do iframe registrado [F23]. A F9 (vitrine em `docs/`), a F10 (assistente: 30 de 30 perguntas de controle corretas e nenhum número fora do que consultou) e a F11 (HTML autocontido) estão implementadas [F24][F25][F26]. A F8 rodou o fluxo completo no projeto de eleições do autor, sem publicar e sem alterar a pasta de origem; os onze problemas encontrados estão em `provas/f8/ISSUES.md`, o principal deles a coluna no grão errado, que vira soma inflada sem alerta [F27]. O servidor MCP `pbix-mcp` já está instalado neste ambiente [F].

---

## 1. Visão, escopo e fora de escopo

**Visão.** O produto fecha um ciclo completo dentro do Claude Code: **Planilha → Análise → Dashboard → BI**. A análise é feita pelo plugin que você já tem, o `analise-dados` [F20]: notebook guiado, revisão crítica e validação do zero. Um novo plugin parte dos dados tratados e das conclusões dessa análise, ou de um .pbix em modo de importação, e gera um dashboard HTML compartilhável e um documento de decisão. O Claude conduz a conversa, desenha a interface e redige o texto, mas **nenhum número sai do modelo de linguagem**: todo valor vem de ferramentas determinísticas (um servidor MCP em Python com DuckDB) que registram origem, regras e versão. É a forma operacional da premissa: interface flexível em HTML sobre uma camada robusta de dados, regras e governança. O uso inicial é pessoal, como portfólio público com dados fictícios; a arquitetura não impede que vire oferta de serviço depois.

**Escopo.** Etapa de análise: o `analise-dados`, sem alterações no MVP, conectado por um contrato de arquivos (seção 3). Fluxo 1: CSV, XLSX ou texto colado, passando pela análise (padrão) ou direto para o dashboard (atalho, com o aviso "sem análise prévia"). Fluxo 2: via (a), conversão de .pbix em modo de importação, e via (b), incorporação oficial, condicionada ao tipo de licença da sua conta. Design: você envia um design system ou o Claude infere o domínio do conjunto de dados (marketing, vendas, financeiro etc.) e propõe o visual. Publicação como Artifact do claude.ai (link privado por padrão, compartilhável) e como arquivo HTML local. Governança proporcional ao uso pessoal: manifesto, linhagem e versionamento por git. Assistente de IA e interface externa própria são fases opcionais.

**Fora de escopo agora.** Contas de usuários e multiusuário. Conectores a ERPs ou APIs e atualização agendada (o `/banco` do `analise-dados` já cobre Postgres, BigQuery e DuckDB na etapa de análise [F20]). O tratamento de dados não fica no plugin de BI: acontece na análise, com as decisões registradas no `contexto.md`. Execução de Power Query M. Conversão de relatórios DirectQuery ou de conexão dinâmica. Recriação de visuais personalizados. Edição de .pbix. HTML autocontido com dados brutos (entra mais tarde, na F11).

## 2. Usuários e casos de uso

| Perfil | Quem é | Caso de uso principal | Fluxo |
|---|---|---|---|
| Autor | Você, dentro do Claude Code | Enviar planilha ou .pbix, revisar o perfil, confirmar métricas, escolher ou enviar o design, publicar | 1 e 2 |
| Leitor do portfólio | Recrutador ou cliente em potencial com o link | Explorar o dashboard, ler o documento de decisão e ver o "por trás" (qualidade, definições, linhagem) | 1 e 2 |
| Usuário de Power BI (demonstração) | Você, simulando um cliente com Power BI | Comparar a versão HTML convertida com o relatório original incorporado | 2 |
| Autor de projeto real | Você, com um projeto em andamento | Rodar o sistema sobre dados reais, sem publicar, para validar o método | 1 |
| Cliente de serviço (futuro) | PME sem Power BI ou empresa que já usa Power BI | Receber o mesmo pacote como serviço; exige a fase multiusuário, fora do escopo atual | — |

## 3. Arquitetura em camadas

| Camada | Responsabilidade | Onde roda | Contrato de saída |
|---|---|---|---|
| Orquestração | Conduzir o ciclo, fazer as perguntas de contexto, chamar as ferramentas na ordem certa | Comando `/bi:ciclo` e skills do novo plugin | Etapa atual e decisões no manifesto |
| Análise (etapa 0) | Leitura, tratamento, perguntas de negócio, achados revisados, notebook validado do zero | Plugin `analise-dados` (Jupyter MCP, hooks, subagentes revisor e editor) [F20] | `contexto.md`, `analise.ipynb` com conclusão, `saidas/dados_tratados.parquet`, `estilos/design-system.md` |
| Ingestão | Ler o arquivo ou texto, detectar codificação, delimitador e localidade pt-BR; guardar o original imutável com hash | MCP `bi-dados` (Python) | `original/` + `dados/*.parquet` + manifesto |
| Validação e perfilamento | Tipos, nulos, duplicatas, cardinalidade, datas, outliers, dados pessoais; regras bloqueantes e alertas | MCP `bi-dados` | `perfil/qualidade.json` |
| Modelo semântico e métricas | Medidas, dimensões, grão, formatação e regras versionadas; consulta e exportação de cubo agregado | MCP `bi-dados` sobre DuckDB | `modelo/metricas.yaml` + `consulta()` + `exportar_cubo()`, **único caminho para números** |
| Design | Aplicar o design system enviado ou inferir o domínio e propor tokens e blocos | Skill de design + ferramenta de tokens | `design/tokens.json` |
| Geração do dashboard | O Claude escreve a spec (estilo, layout, blocos, métricas ligadas); um renderizador determinístico gera o HTML com o cubo embutido | Template HTML + ECharts | `dashboard/spec.json` + `saida/dashboard.html` |
| Documento de decisão | Motor de achados determinístico; o Claude redige; um verificador confere os números | MCP `bi-dados` + skill | `saida/decisao.html` + relatório de verificação |
| Publicação e compartilhamento | Publicar como Artifact ou entregar o arquivo local | Ferramenta Artifact do Claude | URL privada do claude.ai ou arquivo |
| Governança | Manifesto (origem, hash, data), linhagem (arquivo → modelo → spec → saída), versionamento, definição visível de cada métrica | Arquivos do projeto + git | Histórico consultável |

**Integração com o `analise-dados`: dois plugins, um contrato de arquivos.** O novo plugin (`bi-html`) entra no mesmo marketplace e usa a mesma estrutura de projeto: `dados/` protegida contra edição, `saidas/` para derivados, `contexto.md` como memória e `estilos/design-system.md` como única fonte de estilo [F20]. A etapa de BI exige três artefatos da análise: `saidas/dados_tratados.parquet` (o `/painel` já grava esse arquivo [F20]), a conclusão do notebook e o `contexto.md` (pergunta de negócio, público, dicionário de colunas, decisões de tratamento). Com os três presentes, a ingestão vira uma checagem de contrato (esquema, tipos, nulos) em vez de um novo perfilamento. Os achados da conclusão viram métricas candidatas, e só entram no documento de decisão os que a camada de métricas reproduz [I]. A alternativa de fundir tudo em um só plugin fica descartada no MVP: o `analise-dados` tem CI, testes e uma comparação publicada, e um plugin separado não arrisca isso [F20] [I]. A camada de métricas é um servidor MCP porque ferramentas tipadas impedem o Claude de pular essa camada [I].

## 4. Fluxo da planilha ao BI

**Etapas do ciclo.** (1) **Planilha:** `/bi:ciclo` recebe o arquivo ou o texto colado e o coloca em `dados/`. (2) **Análise:** o `/analise` do `analise-dados` conduz o notebook (uma pergunta por vez, revisão crítica, tratamento registrado no `contexto.md`), seguido de `/revisar` e `/validar` [F20]. O `/relatorio` continua disponível como relatório da análise, e o `/painel` como painel de conclusões; o dashboard de BI é a etapa seguinte, com filtros e camada de métricas. (3) **Passagem para o BI:** o sistema confere o contrato (parquet tratado, conclusão, `contexto.md`) e reaproveita a pergunta de negócio e o público já registrados, sem perguntar de novo. (4) O sistema propõe as métricas a partir do dicionário de colunas e dos achados da conclusão, e você confirma. No atalho sem análise, as etapas 2 e 3 são substituídas pelo perfilamento próprio e pelas três perguntas de contexto. (5) Design: se você enviar um design system (DESIGN.md [F11], tokens em JSON ou CSS, tema do Power BI ou guia de marca em PDF ou imagem), o sistema o aplica. Se não, o Claude classifica o domínio pelos nomes e valores das colunas (marketing: campanha, CTR, CPC; vendas: receita, pedido, SKU; financeiro: conta, DRE, fluxo de caixa) e propõe duas opções de estilo com os blocos típicos do domínio (funil e ROAS; ranking e mapa; cascata e DRE) [I]. (6) O Claude escreve a spec, o renderizador gera o HTML e você ajusta. (7) Publicação e documento de decisão.

**Documento de decisão: conteúdo e formato.** Seis partes: (1) a pergunta de negócio e a resposta em uma frase; (2) de 3 a 5 achados, cada um com número, comparação explícita e link para o bloco que o sustenta; (3) o que os dados **não** permitem afirmar; (4) opções de decisão com prós e contras e o que monitorar; (5) próximas perguntas; (6) apêndice de método (origem, hash, data, regras de qualidade, definição de cada métrica). O formato é uma página HTML com o mesmo design, imprimível em 1 ou 2 páginas A4, em português de negócio. Como você não tem um modelo próprio, a F5 usa esse template e você ajusta depois.

**Regra central.** O Claude recebe os achados já calculados, em JSON, e só redige. O verificador extrai os números do texto e confere com os achados; se falhar, o texto é refeito. É o que separa este sistema da referência dashbuilder, em que a IA substitui os números diretamente dentro do HTML [F6] [I].

## 5. Fluxo do Power BI ao HTML

### 5.1 Matriz de viabilidade (importação testada na F6; DirectQuery e conexão dinâmica sem arquivo)

A Microsoft afirma que o .pbix é binário e que **não há métodos suportados** para ver ou modificar o conteúdo [F1]; toda extração depende de engenharia reversa de terceiros. O PBIP (PBIR + TMDL) é documentado, com JSON schema público [F2]. Escala: **I** = integral, **P** = parcial, **N** = não extraível. Na coluna de importação, cada célula foi testada na F6 com o `pbix-mcp` 0.9.153 e conferida com o `pbixray` 0.15.5, o JSON do relatório ou SQL independente; a saída das ferramentas, o tempo e a memória estão em `provas/f6/MATRIZ.md` [F21]. As outras duas colunas continuam documentais: nenhum dos três arquivos está nesses modos.

| Elemento | Importação (testada) | DirectQuery (documental) | Conexão dinâmica (documental) | Justificativa |
|---|---|---|---|---|
| Dados das tabelas | **I** — 415.364 linhas em 12 tabelas, conteúdo idêntico nos dois leitores [F21] | N | N | Em DirectQuery nenhum dado é importado [F3]; o pbix-mcp declara erro ao ler tabelas DirectQuery [F9]; na conexão dinâmica o modelo é externo [F3] |
| Modelo e relacionamentos | **I** — colunas e relações iguais nos dois leitores; a relação da tabela de datas automática só aparece no pbix-mcp [F21] | I [I] | N | Na conexão dinâmica os campos vêm do modelo externo [F3] |
| Medidas DAX (texto) | **I** — 74 medidas, 2 colunas calculadas e 1 tabela calculada, texto idêntico; a saída formatada da ferramenta corta expressões longas, o texto integral vem do leitor do pacote [F21] | I | P | Na conexão dinâmica só as medidas do próprio relatório [I] |
| Medidas DAX (cálculo) | **I na amostra** — 74 de 74 medidas avaliadas sem erro e 20 de 20 conferências contra SQL batem, com CALCULATE, REMOVEFILTERS, ALLSELECTED, TOPN, RANKX e SELECTEDVALUE; caro em tabela grande: de 60 a 103 s e de 1,4 a 1,7 GB para 55 medidas sobre 309 mil linhas, em cinco execuções [F21] | N | N | Amostra não é auditoria: a F7 mantém o teste de equivalência e o selo "não validada" |
| Consultas Power Query (M) | **P** — texto I (inclusive consultas compartilhadas, só visíveis nos metadados); execução N: as origens são arquivos de outra máquina [F21] | P | N | PBIDS não carrega credenciais [F4]; o `pbix_list_data_sources` rotula como "Embedded" tabelas que leem CSV por consulta compartilhada [F21] |
| Layout de páginas e visuais | **P** — leitura I (11 páginas e 122 visuais em PBIR, com tipo e posição); recriação: 53 de 62 visuais de dados têm bloco no bi-html, faltam dispersão e mapa do Azure [F21] | P | P | O layout legado não foi testado (os três arquivos são PBIR) |
| Filtros e segmentações | **P** — segmentações, filtros de página e seleções padrão lidos pelas ferramentas; filtros de visual e interações só pelo JSON do visual [F21] | P | P | A interação cruzada é reimplementada [I] |
| Temas | **P** — o tema registrado vem em JSON e importa no bi-html com AA; num arquivo, o tema em uso (`CopilotDefault`, embutido) não veio da ferramenta e foi lido do pacote [F21] | I/P | I/P | O tema extraído serve de design system de entrada (seção 7) |
| Visuais personalizados | — não testável: nenhum nos três arquivos (detecção conferida em 17 tipos de visual) [F21] | N | N | Rodar código de terceiros fora do Power BI não é viável nem seguro [I]; vira bloco equivalente ou placeholder |
| Segurança por linha (RLS) | — não testável: nenhum papel nos três arquivos [F21] | P | N | Papéis e filtros são extraíveis [F9][F10]; membros são atribuídos no serviço [F5] |

**O que a F6 muda nas próximas fases [F21] [I].** (1) A leitura de .pbix roda num processo à parte: o `pbix-mcp` exige `mcp<2` e o servidor `bi-dados` usa `mcp>=2.3`. (2) No híbrido da seção 5.2, pré-calcular pelo avaliador do `pbix-mcp` só serve para grades pequenas; o que for traduzível vai para SQL. (3) O mapa de visuais para blocos precisa de dispersão e de um destino para o mapa do Azure. (4) O tema em uso é lido do `report.json`, não só da ferramenta.

### 5.2 Tradução de medidas

| Abordagem | O que preserva | O que perde em interatividade | O que perde em fidelidade |
|---|---|---|---|
| Reimplementar na camada de métricas (DAX → spec/SQL) | Filtro livre por qualquer dimensão | Nada, se a tradução existir | Contexto de filtro, ALL/ALLSELECTED, inteligência de tempo e relações bidirecionais divergem com facilidade [I] |
| Pré-calcular (avaliar numa grade fixa de dimensões e gravar) | O número exato nos pontos calculados, se o avaliador for fiel | Só as combinações calculadas; distintos, médias e % não se reagregam [I] | Depende do avaliador; no pbix-mcp a paridade não é auditada [NV] |
| **Híbrido (recomendado)** | Traduzir aditivas e razões simples; pré-calcular as complexas na grade das dimensões que os visuais usam | Total nas traduzidas, limitada nas pré-calculadas, com indicação visual | Teste de equivalência numa amostra de contextos; medida sem validação recebe o selo "não validada" |

**Resultado da F7 [F22].** A tradução está implementada (`dax.py` e `conversao.py`): soma, média, mínimo, máximo, contagens, razão, participação, filtros de `CALCULATE`, iteradores com coluna calculada e escala viram métricas; cada medida sai classificada como traduzida, texto ou não traduzida, com o motivo. Nos três arquivos reais, as 30 traduzidas batem com o motor DAX do pbix-mcp em 147 contextos, e as linhas de todas as 12 tabelas são idênticas. O teste pegou uma divergência real no .pbix fictício: o filtro de um `CALCULATE` substitui o do leitor no Power BI e se soma a ele na camada de métricas, e a medida ficou com o selo "não validada". O pré-cálculo das medidas complexas **não** foi implementado: a F6 mediu de 11 a 16 s por medida pesada no avaliador, e a spec não tem onde guardar uma grade. As não traduzidas ficam fora do dashboard, listadas no relatório de fidelidade [I]. O relatório é lido em PBIR e no layout legado.

### 5.3 Via oficial (b), comparação e recomendação

**Requisitos da via (b) [F5][F7][F8].** *Publicar na Web* não exige autenticação, expõe dados de detalhe e precisa ser habilitado pelo administrador do tenant; com dados fictícios, serve para o portfólio. A *incorporação segura* exige login e licença Pro ou PPU de cada visualizador, salvo capacidade F64 ou superior. A *incorporação para seus clientes* exige entidade de serviço ou usuário mestre no Entra ID; em desenvolvimento, aceita tokens de avaliação com uma conta Pro ou PPU (o relatório mostra uma faixa); em produção, exige capacidade. A RLS é aplicada com `EffectiveIdentity`. Falta saber se a sua conta é Free, Pro ou PPU e se o tenant é pessoal ou corporativo (seção 12).

**Argumento mais forte de cada lado.** A favor da (b): fidelidade total, RLS nativa, DirectQuery e conexão dinâmica. Contra: custo de licença ou capacidade, dependência do tenant, e o HTML vira só moldura. A favor da (a): independe de licença, usa o design system e a mesma camada de métricas do Fluxo 1, e é o que demonstra a premissa. Contra: só serve para importação, depende de formato sem suporte oficial, tem fidelidade parcial e exige reimplementar a RLS.

**Recomendação.** A (a) é o núcleo do Fluxo 2, restrita à importação, com relatório de fidelidade por elemento e com o PBIP como entrada preferencial. Para o portfólio, a demonstração mais forte põe lado a lado o HTML convertido e o original incorporado. Com conta Free, esse original vem do *Publicar na Web* (dados fictícios); com Pro, vem da incorporação segura. O teste da F7b confirmou que o Artifact do claude.ai não permite o iframe do Power BI: o contrato de página dos Artifacts recusa incorporar outros sites, para qualquer leitor [F18]. Do lado do Power BI, os links de Publicar na Web (`/view?r=`) e de incorporação segura (`/reportEmbed`) não bloqueiam a incorporação, e a página comum do serviço bloqueia (`X-Frame-Options: deny`) [F23]. Por isso o par fica numa página estática (`saidas/bi/comparativo/`, comando `/bi-html:comparar`), que pode morar na interface externa (F9) ou em qualquer hospedagem; o dashboard convertido continua publicável como Artifact. No envio, o sistema detecta o modo do arquivo: importação vai para a (a); DirectQuery e conexão dinâmica recebem a explicação e a opção (b).

## 6. Compartilhamento e segurança

### 6.1 Comparação dos modelos

| Critério | HTML autocontido com dados embutidos | Link hospedado (Artifact do claude.ai) | Instância multiusuário com contas |
|---|---|---|---|
| Quem acessa | Quem tiver o arquivo; reencaminhável sem controle | Artifacts nascem privados; você decide com quem compartilhar [F18] | Usuários convidados, por papel |
| Sensibilidade e LGPD | Todos os dados embutidos viajam juntos; só para dados fictícios ou agregados | Os dados embutidos ficam visíveis para quem tem acesso [I]; adequado para dados fictícios; dados reais ficam privados | Necessário para dados de clientes; exige contrato e registro das operações |
| Revogação e expiração | Impossível revogar depois do envio | Apagar o Artifact derruba o link para todos [F18]; expiração por data não aparece na documentação da ferramenta [NV] | Desativar conta ou papel |
| Versionamento | Cópia congelada, com versão e hash no rodapé | Republicar atualiza o mesmo link [F18]; o git do projeto guarda o histórico | Histórico completo no servidor |
| RLS do Power BI | Não se aplica: filtro no navegador não protege dados que estão no arquivo [I] | Não se aplica: o cubo embutido é o mesmo para todos [I]; recortes diferentes viram Artifacts diferentes | Implementável no servidor, por usuário |
| Limite técnico | Tamanho do arquivo | Página de até 16 MB [F18]: embute-se o cubo agregado, nunca as linhas brutas | — |

A RLS de um .pbix **não se transfere sozinha** em nenhum modelo: as regras podem ser lidas, mas a atribuição de pessoas a papéis vive no serviço Power BI [F5].

### 6.2 Recomendação

O padrão é **publicar como Artifact**: privado até você compartilhar, revogável por exclusão, atualizado no mesmo link a cada republicação e sem infraestrutura própria. O arquivo HTML local fica como cópia de trabalho. O HTML autocontido para envio (por exemplo, WhatsApp) entrou na F11 (`/bi-html:exportar`): o ECharts vai embutido, conferido pelo hash do cdnjs, as fontes passam a ser as do sistema, o rodapé diz que é uma cópia congelada e a exportação é recusada com dados pessoais; aberto no navegador, o arquivo fez uma única requisição, a dele mesmo [F26]. A instância multiusuário só volta ao plano se o projeto virar serviço.

LGPD: com dados fictícios, o risco é baixo. Para o seu projeto real em andamento, a regra é não publicar enquanto houver colunas pessoais. O perfilamento sinaliza CPF, e-mail e telefone, e a publicação é bloqueada até você removê-los ou agregá-los. Se o projeto virar serviço, o tema volta com contrato de operador e revisão jurídica (Lei 13.709/2018; conhecimento geral, sem documento consultado nesta sessão) [NV].

Com papéis de RLS no .pbix, o sistema importa as regras como rascunho e avisa que o dashboard publicado mostra todos os dados. Para um recorte por pessoa, você publica um Artifact por recorte.

## 7. Design system e experiência do usuário

**Referências e o que foi possível ler.** Os dois vídeos do TikTok **não puderam ser lidos** (só o título genérico, exigem JavaScript ou login); o conteúdo não foi deduzido. A dashbuilder foi lida por fetch na home e em navegador com JavaScript no montador, no catálogo e no método [F6]. A shadcn.io/design é um diretório de terceiros com arquivos DESIGN.md, não o shadcn/ui oficial [F11]; os tokens oficiais foram verificados em ui.shadcn.com [F12].

**Padrões extraídos [F6][F12].** A dashbuilder separa três camadas independentes: **estilo** (tokens), **layout** (grade) e **blocos** (peças), sob o lema "muda o token, não a peça". São 20 estilos, 6 layouts (Clássico, Painel de controle, Três colunas, Painel denso 3-2-2, Mosaico, Mapa em destaque) e 32 blocos. Os blocos que observei: número-herói, faixa de KPIs, KPI com sparkline, medidor de meta, bullet, comparativo de período, ranking, tabela com ROAS, tabela pivot, feed, linha com meta, área empilhada, barras agrupadas, cascata, barra com linha em eixo duplo, rosca, treemap, sankey, Pareto, funil, mapa de calor, coorte, boxplot, bolhas, radar, histograma, mapa coroplético das UFs e mapa de bolhas. Os tokens: superfície (`--bg`, `--plane`, `--stroke`, `--grid`), texto (`--ink`, `--muted`), acento (`--acc`), estados (`--good`, `--bad`, `--warn`), gráfico (`--c1` a `--c5`) e forma (`--font`, `--radius`, `--shadow`). O shadcn/ui oficial (MIT) usa `--background`, `--foreground`, `--card`, `--primary`, `--muted`, `--border`, `--chart-1` a `--chart-5` e `--radius`, com cores em oklch e modo escuro pela classe `.dark`. Convenções pt-BR: R$ 1.234,56, abreviações K e M, ▲/▼ com comparação explícita.

**Proposta, com a sua sugestão incorporada.** O contrato é estilo/layout/bloco, com tokens semânticos no padrão shadcn/ui mais estados e cores de gráfico. Há duas entradas de estilo. *Enviado:* o sistema aceita DESIGN.md, JSON ou CSS de tokens, o tema JSON de um .pbix ou um guia de marca em PDF ou imagem, de onde o Claude extrai cores e fontes para você confirmar; um validador checa contraste AA antes de aplicar. *Inferido:* o Claude classifica o domínio do conjunto de dados e propõe dois estilos e uma seleção de blocos coerente com o domínio, sempre como sugestão editável. No MVP, 4 estilos base e cerca de 12 blocos; a grade colapsa para uma coluna abaixo de 768px; cada bloco mostra a definição e a origem da métrica. Estilos, nomes e textos da referência não serão copiados [I].

## 8. Módulo de assistente de IA (fase opcional)

**Duas formas possíveis.** *Dentro do Claude Code:* você pergunta na própria sessão e o Claude responde chamando `consulta()` do MCP; isso funciona desde a F2, sem fase própria [I]. *Dentro do dashboard publicado:* um Artifact pode declarar a capacidade de "perguntar ao Claude" [F18]; nesse caso o chat responde a partir do cubo embutido na página. Essa é a forma que exige fase própria, porque o Claude passa a ler números fora da camada de métricas.

**Controles.** As respostas só podem citar valores presentes no cubo, e o verificador de números do documento de decisão é aplicado à resposta. O conteúdo das células é tratado como dado, nunca como instrução. Há um conjunto de perguntas com resposta conhecida, rodado a cada versão. Os detalhes da capacidade (custo, limites, quem paga a consulta) vêm da skill `artifact-capabilities` na hora de implementar [NV].

**Como ficou na F10 [F25].** O painel "Pergunte ao dashboard" (`/bi-html:assistente`) usa a capacidade `sample` do Artifact, na conta de quem pergunta.
- **O que o Claude enxerga:** só o cubo, por uma ferramenta da página que devolve valores já formatados; não há SQL nem dados brutos.
- **A verificação:** cada número da resposta precisa estar nos blocos que ele consultou para aquela pergunta, arredondado como foi escrito. Valer o cubo inteiro deixaria passar números pequenos que algum valor arredonda por acaso; o teste da fase mostrou isso. A resposta que falha é retida.
- **As perguntas de controle:** são 30, saem do cubo calculado pela camada de métricas e rodam por um botão de quem edita a página. O resultado fica no banco do Artifact, e a correção é refeita em Python. A correção da página (JavaScript) e a de Python são testadas para dar o mesmo resultado.

**Na via (b) e critério de entrada.** Relatórios incorporados podem habilitar o Copilot com Premium ou Fabric pago [F7], e o Q&A do Power BI será descontinuado em fevereiro de 2027 [F13]. A fase só começa com o Fluxo 1 publicado e o catálogo de métricas estável.

## 9. Stack recomendada

| Camada | Recomendação | Alternativas | Critério de escolha |
|---|---|---|---|
| Etapa de análise | Plugin `analise-dados` v1.1.0 (MIT; Jupyter MCP via `uvx`, ambiente com `uv`, pandas, DuckDB, Plotly) [F20] | Fundir os dois plugins em um só | Já existe, está testado e tem método publicado; mesmo ecossistema (`uv`, Python) do novo plugin |
| Ambiente de execução | Novo plugin `bi-html` no mesmo marketplace do `analise-dados` (skills, comandos, agentes e MCP) [F17] | Só skills com scripts via terminal; claude.ai web [NV] | Roda inteiramente dentro do Claude, como você pediu; o Claude Code executa MCP local |
| Ferramentas determinísticas | MCP `bi-dados` em Python 3.12 (FastMCP [NV]) | Scripts Python chamados pelas skills | Entradas e saídas tipadas; o Claude não contorna a camada de métricas |
| Motor analítico | DuckDB local sobre Parquet [NV] | pandas puro; Postgres | Arquivo de até ~1 milhão de linhas ou ~200 MB num notebook sem servidor [H] |
| Validação e perfil | pandera + perfilador próprio [NV] | Great Expectations | Regras declarativas versionáveis |
| Camada semântica | `metricas.yaml` próprio compilado para SQL | Cube; dbt MetricFlow [NV] | Simplicidade no uso pessoal |
| Renderização | Template HTML + Apache ECharts via cdnjs [NV] | Recharts (exige React) [F12] | Cobertura do catálogo (sankey, treemap, mapas); o cdnjs está na lista permitida dos Artifacts [F18] |
| Publicação | Ferramenta Artifact do Claude [F18] | Arquivo HTML local; Vercel na F9 | Link privado e revogável, sem infraestrutura |
| LLM | O próprio Claude na sessão | — | Sem chave de API nem custo extra fora da assinatura [I] |
| Leitura de .pbix | pbix-mcp (já instalado; MIT; v0.9.153 de 04/11/2026; lê layout, filtros, tema e RLS; avalia DAX parcialmente; um mantenedor) + pbixray (MIT; v0.15.5 de 27/08/2026; só leitura; não avalia DAX nem lê o layout) [F9][F10] | PBIP/PBIR + TMDL como entrada preferencial [F2]; pbi-tools (AGPL-3.0 [F14]); extensão pbix do DuckDB [F15] | Licença permissiva, manutenção ativa, já integrado ao ambiente |
| Incorporação (via b) | Publicar na Web (dados fictícios) ou incorporação segura, conforme a licença [F5][F7] | Incorporação para seus clientes com token de avaliação [F8] | Tipo de licença da sua conta |
| Interface externa (F9, opcional) | Next.js + shadcn/ui na Vercel, lendo os mesmos arquivos de saída | Página estática | Vitrine própria do portfólio |
| Idioma | Código em Python; nomes, mensagens, documentação e comentários em português do Brasil | — | Sua preferência |

**Recomendação de volume e compartilhamento (sua pergunta 5).** Arquivos de até cerca de 1 milhão de linhas ou 200 MB processados localmente no DuckDB [H]. O HTML publicado embute só o cubo agregado, com meta de até 5 MB, bem abaixo do limite de 16 MB [F18]. O público por dashboard é de 1 a 20 pessoas, por Artifact compartilhado.

## 10. Fases e marcos

| Fase | Marco | Critério de aceite verificável | Esforço |
|---|---|---|---|
| F0 Fundações | Esqueleto do plugin, schema da spec, 3 conjuntos fictícios (marketing, vendas, financeiro) | O plugin carrega no Claude Code e lista os comandos; o schema valida um exemplo; os conjuntos estão em `fixtures/` | P |
| F0b Contrato com a análise | `CONTRATO.md` com os arquivos de passagem; checagem de contrato; `/bi:ciclo` encadeando as etapas | No projeto de exemplo do `analise-dados` (5.000 vendas), o `/bi:ciclo` detecta a análise pronta, lê `contexto.md` sem refazer perguntas e aponta exatamente o que falta quando um dos três arquivos é removido | P |
| F1 Ingestão e perfil | Ferramentas `ingerir` e `perfilar` (atalho sem análise e Fluxo 2) | Os 3 conjuntos geram `qualidade.json` com tipos e datas pt-BR corretos; um arquivo com CPF fictício é sinalizado; um arquivo malformado devolve erro legível | M |
| F2 Métricas | `metricas.yaml`, `consulta()`, `exportar_cubo()` | 10 consultas de teste batem com o cálculo manual (diferença zero); cada métrica tem definição e linhagem no manifesto | M |
| F3 Design | Design enviado ou inferido | Um DESIGN.md de exemplo e um tema de .pbix viram `tokens.json` com contraste AA; os 3 conjuntos são classificados no domínio certo e recebem estilos e blocos coerentes | M |
| F4 Dashboard e publicação | Spec, renderização e Artifact | Os 3 conjuntos renderizam sem erro; a spec escrita pelo Claude **não contém números** (inspeção do JSON); o HTML tem menos de 5 MB, funciona a 375px e foi publicado como Artifact | G |
| F5 Documento de decisão | Achados, texto e verificador | 100% dos números do texto rastreados a achados; cada achado da conclusão do notebook aparece como "reproduzido" ou "não reproduzido" pela camada de métricas; seção de limites presente; impressão em até 2 páginas A4; o subagente `revisor` do `analise-dados` relê o documento sem apontar conclusão sem sustentação | M |
| F6 Prova de conceito .pbix | Matriz 5.1 com os seus arquivos | Cada célula marcada como testada, com a saída da ferramenta anexada; tempo e memória registrados | P |
| F7 Fluxo 2, via (a) | Conversão de .pbix em importação | Contagem de linhas idêntica por tabela; todas as medidas classificadas; as traduzidas batem com a avaliação de referência numa amostra de contextos; relatório de fidelidade por visual | G |
| F7b Fluxo 2, via (b) | Original incorporado ao lado do convertido | Relatório de exemplo visível em página pública ou no Artifact, com o caminho escolhido conforme a licença; teste do iframe no Artifact registrado | P |
| F8 Caso real privado | Seu projeto em andamento | Fluxo completo sem publicação; problemas encontrados viram issues do plugin | P |
| F9 Interface externa (opcional) | Vitrine do portfólio | Página pública com os dashboards de demonstração e o comparativo (a) vs. (b) | M |
| F10 Assistente de IA (opcional) | Chat no dashboard publicado | 30 perguntas com resposta conhecida: pelo menos 90% corretas [H]; nenhum número fora do cubo | M |
| F11 HTML autocontido | Exportação para envio | O arquivo abre offline; com dados pessoais, a exportação é recusada | P |

## 11. Riscos e dependências

| Risco ou dependência | Probabilidade / impacto | Mitigação |
|---|---|---|
| Formato .pbix sem suporte oficial [F1]; atualização do Desktop quebra leitores [I] | Alta / alto | Preferir PBIP; isolar o leitor; testar arquivos de versões diferentes |
| pbix-mcp com um mantenedor; paridade DAX não auditada [F9] | Média / alto | Validada na amostra da F6 (20 de 20) [F21]; fixar versões; pbixray como plano B e segundo leitor |
| Avaliação DAX do pbix-mcp lenta e com muita memória em tabelas grandes (de 60 a 103 s e de 1,4 a 1,7 GB para 55 medidas sobre 309 mil linhas) [F21] | Alta / médio | Traduzir para SQL o que for traduzível; pré-calcular só grades pequenas, em processo à parte |
| Conflito de dependências: o pbix-mcp exige `mcp<2`, o `bi-dados` usa `mcp>=2.3` [F21] | Certa / baixo | Leitura de .pbix em processo próprio, como na prova da F6 |
| Tradução DAX infiel gera número errado com aparência confiável | Alta / alto | Teste de equivalência contra o pbix-mcp em cada conversão e selo "não validada"; na F7, pegou o caso do filtro de `CALCULATE` [F22] |
| O Claude contorna as ferramentas e escreve números na spec ou no texto | Média / alto | Schema sem campos numéricos livres; verificador; skills com regra explícita |
| O assistente do dashboard cita um número que não leu | Média / alto | Verificador na página contra os blocos consultados naquela pergunta; resposta retida; bateria de perguntas de controle a cada versão [F25] |
| O Artifact bloqueia o iframe do Power BI (confirmado na F7b [F23]) ou bibliotecas fora da lista permitida | Certa / médio | Comparação numa página estática (`saidas/bi/comparativo/`), hospedada fora do claude.ai; vitrine na F9 |
| Limite de 16 MB por página [F18] | Baixa / médio | Embutir só o cubo agregado |
| Dados reais publicados por engano | Baixa / alto | Bloqueio de publicação com dados pessoais; casos reais ficam privados |
| Coluna no grão errado (valor da zona repetido por candidato) vira soma inflada sem alerta | Alta / alto | Achado na F8 [F27]: perfil que detecta colunas constantes dentro de um grão maior, soma uma vez por chave no modelo e fonte com várias tabelas |
| Mudanças no formato de plugins do Claude Code | Média / médio | Lógica de dados no MCP, independente das skills |
| Acoplamento entre os dois plugins: mudança no `analise-dados` quebra o contrato | Média / médio | `CONTRATO.md` versionado; teste de contrato no CI dos dois repositórios; o `bi-html` declara a versão mínima do `analise-dados` |
| Sobreposição entre o `/painel` do `analise-dados` e o dashboard de BI confunde o uso | Média / baixo | Papéis distintos e documentados (painel de conclusões vs. BI exploratório); na F9, avaliar se o `/painel` passa a usar o renderizador novo |
| Divergência entre um número do notebook e o da camada de métricas | Média / alto | Achado não reproduzido não entra no documento de decisão e aparece listado como pendência |
| **Dependências** | — | Todas atendidas em 18/11/2026: o relatório fictício está publicado com Publicar na Web (o link pode ser revogado em Configurações > Gerenciar códigos de inserção) |

## 12. Perguntas em aberto que dependem de você

| # | Pergunta | O que muda no plano |
|---|---|---|
| 1 | A sua conta Power BI é Free, Pro ou PPU? O tenant é pessoal ou de uma empresa? Você consegue habilitar Publicar na Web (ou já está habilitado)? | Qual caminho da via (b) a F7b usa. **Respondida em 17/11:** Free; Publicar na Web não habilitado (ou desconhecido). A F7b usa Publicar na Web e fica à espera da publicação. |
| 2 | Os .pbix que você vai enviar podem aparecer no portfólio público, ou só servem para teste? | Se a F7 publica a conversão desses arquivos ou de um .pbix fictício. **Respondida em 17/11:** só o fictício (`fixtures/vendas.pbix`) aparece em público; os três reais servem para teste. |
| 3 | Qual é o projeto em andamento para a F8, e ele tem dados pessoais? | Escopo e cuidados do caso real. **Respondida em 17/11:** o projeto de eleições presidenciais; o conjunto usado não tem dados pessoais (os arquivos brutos do TSE com dados de candidatos ficaram de fora). |
| 4 | Basta rodar no Claude Code (app desktop), ou você também quer usar pelo chat do claude.ai na web? | O claude.ai web não executa MCP local [NV]; a alternativa seria uma versão só com skills |
| 5 | Que nome o plugin terá (sugestão: `bi-html`) e qual será o prefixo dos comandos? | F0 |
| 6 | O novo plugin pode entrar no marketplace do `analise-dados` (mesmo repositório) ou você prefere um repositório separado? | Onde ficam o CI e o teste de contrato |
| 7 | O `/painel` do `analise-dados` continua como está, ou deve passar a usar o renderizador do BI quando o novo plugin estiver instalado? | Se há mudança no `analise-dados` (fora do MVP) |

**Sobre a sua pergunta da linha 10 (dados fictícios ou projeto em andamento).** A recomendação é começar pelos três conjuntos fictícios: são reproduzíveis, podem ser publicados sem risco e cobrem os três domínios de que a inferência de design precisa. O seu projeto real entra na F8, depois que o fluxo completo funcionar, como validação privada. Os dados fictícios mostram o produto; o caso real mostra onde ele quebra.

---

## Fontes consultadas em 16 e 17/11/2026

1. Microsoft Learn, *Power BI implementation planning: Develop content and manage changes*. https://learn.microsoft.com/power-bi/guidance/powerbi-implementation-planning-content-lifecycle-management-develop-manage
2. Microsoft Learn, *Power BI Desktop projects*, *Project semantic model folder*, *Enhanced report format*. https://learn.microsoft.com/power-bi/developer/projects/projects-overview · https://learn.microsoft.com/power-bi/developer/projects/projects-dataset · https://learn.microsoft.com/power-bi/developer/embedded/projects-enhanced-report-format
3. Microsoft Learn, *DirectQuery in Power BI* e *Use DirectQuery in Power BI Desktop*. https://learn.microsoft.com/power-bi/connect-data/desktop-directquery-about · https://learn.microsoft.com/power-bi/connect-data/desktop-use-directquery
4. Microsoft Learn, *Get data in Power BI Desktop* (PBIDS sem autenticação). https://learn.microsoft.com/power-bi/connect-data/desktop-data-sources
5. Microsoft Learn, *Row-level security (RLS) with Power BI* e *Publish to web*. https://learn.microsoft.com/fabric/security/service-admin-row-level-security · https://learn.microsoft.com/power-bi/collaborate-share/service-publish-to-web
6. dashbuilder.asimov.academy: home, `/montador/`, `/catalogo/`, `/metodo/` (os três últimos lidos em navegador com JavaScript).
7. Microsoft Learn, *Embed a report in a secure portal or website*. https://learn.microsoft.com/power-bi/collaborate-share/service-embed-secure
8. Microsoft Learn, *What is Power BI embedded analytics?*, *Capacity and SKUs*, *Generate an embed token*, *Embed for your customers*. https://learn.microsoft.com/power-bi/developer/embedded/embedded-analytics-power-bi · https://learn.microsoft.com/power-bi/developer/embedded/embedded-capacity · https://learn.microsoft.com/power-bi/developer/embedded/generate-embed-token · https://learn.microsoft.com/power-bi/developer/embedded/embed-sample-for-customers
9. pbix-mcp: https://github.com/d0nk3yhm/pbix-mcp · https://pypi.org/project/pbix-mcp/
10. pbixray: https://github.com/Hugoberry/pbixray · https://pypi.org/project/pbixray/
11. shadcn.io/design (diretório de DESIGN.md; formato aberto do Google Labs). https://www.shadcn.io/design · https://github.com/google-labs-code/design.md
12. shadcn/ui: https://ui.shadcn.com/docs/theming · https://ui.shadcn.com/docs/components/chart · https://github.com/shadcn-ui/ui
13. Microsoft Learn, *Data sources for natural language Q&A*. https://learn.microsoft.com/power-bi/natural-language/q-and-a-data-sources
14. pbi-tools: https://github.com/pbi-tools/pbi-tools
15. Extensão pbix do DuckDB: https://duckdb.org/community_extensions/extensions/pbix.html
16. pbixray-mcp-server: https://github.com/jonaolden/pbixray-mcp-server
17. Este ambiente do Claude Code em 16/11/2026: o plugin `analise-dados` (skills, agentes, MCP Jupyter), a skill `reorganizar-layout-power-bi` e as ferramentas `pbix-mcp` instaladas.
18. Documentação da ferramenta Artifact nesta sessão: privado por padrão, exclusão derruba o link, republicação no mesmo link, limite de 16 MB, CDNs permitidas (cdnjs, jsdelivr, unpkg), capacidades de execução (como perguntar ao Claude).
19. Não lidos: https://www.tiktok.com/@uxerflow/video/7642617380111174920 e https://www.tiktok.com/@paulcodes4/video/7707346514556865812 (só o título genérico; exigem JavaScript ou login).
20. Plugin `analise-dados` v1.1.0 (MIT), cópia local do repositório https://github.com/fernandofigueiredo-data/analise-dados-plugin, commit `10bbdaf` de 18/10/2026: README, `REGRAS.md`, `.mcp.json`, `hooks/hooks.json`, comandos `/analise`, `/painel` e `/relatorio`, `scripts/projeto.py`, `lib/analise_dados/painel.py`, `modelo/estilos/design-system.md`, skill `analista-senior`.
21. Prova de conceito da F6 neste repositório, executada em 17/11/2026 com três .pbix do autor em modo de importação: `provas/f6/MATRIZ.md`, `provas/f6/resultados.json` e as saídas das ferramentas em `provas/f6/saidas/`.
22. Prova da F7 neste repositório, executada em 17/11/2026 com cópias dos três .pbix do autor (o de eleições e o Lab1 em versões posteriores às da F6) e com os .pbix fictícios de `fixtures/`: `provas/f7/RESULTADO.md`, `provas/f7/resultados.json` e os relatórios de fidelidade em `provas/f7/saidas/`.
23. Teste do iframe da F7b neste repositório, em 17 e 18/11/2026: cabeçalhos HTTP do serviço do Power BI com identificadores fictícios e com o link do relatório fictício publicado, e a página de comparação da vitrine aberta num navegador local, com o original carregado ao lado do convertido (`provas/f7b/RESULTADO.md` e `resultados.json`).
24. Vitrine da F9 neste repositório, em 17/11/2026: `docs/`, gerada por `vitrine/construir.py` a partir dos exemplos fictícios e do .pbix fictício convertido.
25. Assistente da F10 neste repositório: `plugins/bi-html/lib/bi_html/assistente.py`, Artifact privado com o exemplo de vendas e `provas/f10/RESULTADO.md` (bateria de 18/11/2026: 30 de 30 corretas, nenhum número fora do consultado).
26. Exportação da F11 neste repositório, em 17/11/2026: `plugins/bi-html/lib/bi_html/exportacao.py`; arquivo aberto num navegador local com uma única requisição, a do próprio arquivo.
27. Caso real da F8, em 17/11/2026: cópia do projeto de eleições presidenciais do autor em `casos/` (fora do git), fluxo completo sem publicação; estados e contagens em `provas/f8/RESULTADO.md` e problemas em `provas/f8/ISSUES.md`.
