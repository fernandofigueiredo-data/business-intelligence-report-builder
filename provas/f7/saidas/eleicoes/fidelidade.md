# Fidelidade da conversão — eleicoes.pbix

Convertido em 2026-11-17T14:34:21-03:00 pelo bi-html (pbix-mcp 0.9.153, pbixray 0.15.5). Modo do arquivo: importacao. Relatório: PBIR.

## Tabelas

| Tabela | Linhas no .pbix | Linhas extraídas | No modelo convertido | Iguais |
|---|---|---|---|---|
| PartidoCores | 27 | 27 | fora (nenhuma medida a usa) | sim |
| _Medidas | 0 | 0 | fora (nenhuma medida a usa) | sim |
| dCandidato | 47 | 47 | 47 | sim |
| dMunicipio | 5766 | 5766 | 5766 | sim |
| dTurno | 8 | 8 | dimensão dos fatos | sim |
| fComparecimento | 45834 | 45834 | 45834 | sim |
| fVotos | 309308 | 309308 | 309308 | sim |

## Medidas

| Medida | Classe | Métrica | Equivalência | Motivo ou ressalva |
|---|---|---|---|---|
| Aptos | traduzida | aptos | 5 de 5 contextos |  |
| Comparecimento | traduzida | comparecimento | 5 de 5 contextos |  |
| Abstenções | traduzida | abstencoes | 5 de 5 contextos |  |
| Votos Válidos | traduzida | votos_validos | 5 de 5 contextos |  |
| Votos Brancos | traduzida | votos_brancos | 5 de 5 contextos |  |
| Votos Nulos | traduzida | votos_nulos | 5 de 5 contextos |  |
| % Abstenção | traduzida | pct_abstencao | 5 de 5 contextos |  |
| % Comparecimento | traduzida | pct_comparecimento | 5 de 5 contextos |  |
| % Brancos | traduzida | pct_brancos | 5 de 5 contextos |  |
| % Nulos | traduzida | pct_nulos | 5 de 5 contextos |  |
| % Brancos e Nulos | traduzida | pct_brancos_e_nulos | 5 de 5 contextos |  |
| Votos | traduzida | votos | 5 de 5 contextos |  |
| Votos Todos os Candidatos | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |
| % Votos Válidos | nao_traduzida | — | — | depende de [Votos Todos os Candidatos], que não foi traduzida |
| Posição | nao_traduzida | — | — | usa IF, RANKX, sem equivalente na camada de métricas |
| Vencedor | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Partido Vencedor | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| % do Vencedor | nao_traduzida | — | — | usa TOPN, VALUES, sem equivalente na camada de métricas |
| Margem de Vitória | nao_traduzida | — | — | usa IF, TOPN, VALUES, sem equivalente na camada de métricas |
| Municípios Vencidos | nao_traduzida | — | — | usa REMOVEFILTERS, VALUES, sem equivalente na camada de métricas |
| % Municípios Vencidos | nao_traduzida | — | — | depende de [Municípios Vencidos], que não foi traduzida |
| Ano Selecionado | nao_traduzida | — | — | usa SELECTEDVALUE, sem equivalente na camada de métricas |
| Partido Vencedor 1º Turno | nao_traduzida | — | — | depende de [Partido Vencedor], que não foi traduzida |
| Partido Vencedor 1º Turno Anterior | nao_traduzida | — | — | depende de [Partido Vencedor], que não foi traduzida |
| Mudou Partido Vencedor | nao_traduzida | — | — | usa IF, SUBSTITUTE, sem equivalente na camada de métricas |
| Municípios que Mudaram | nao_traduzida | — | — | usa VALUES, sem equivalente na camada de métricas |
| % Municípios que Mudaram | nao_traduzida | — | — | depende de [Municípios que Mudaram], que não foi traduzida |
| % Votos Válidos Eleição Anterior | nao_traduzida | — | — | usa IF, REMOVEFILTERS, SELECTEDVALUE, sem equivalente na camada de métricas |
| Variação p.p. | nao_traduzida | — | — | usa IF, sem equivalente na camada de métricas |
| % Abstenção Eleição Anterior | nao_traduzida | — | — | usa REMOVEFILTERS, SELECTEDVALUE, sem equivalente na camada de métricas |
| Variação Abstenção p.p. | nao_traduzida | — | — | usa IF, sem equivalente na camada de métricas |
| Vencedor 1º Turno | nao_traduzida | — | — | depende de [Vencedor], que não foi traduzida |
| Vencedor 2º Turno | nao_traduzida | — | — | depende de [Vencedor], que não foi traduzida |
| Virou no 2º Turno | nao_traduzida | — | — | usa IF, sem equivalente na camada de métricas |
| Municípios que Viraram | nao_traduzida | — | — | usa VALUES, sem equivalente na camada de métricas |
| % Municípios que Viraram | nao_traduzida | — | — | depende de [Municípios que Viraram], que não foi traduzida |
| Votos 1º Turno | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |
| Votos 2º Turno | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |
| Votos Ganhos no 2º Turno | nao_traduzida | — | — | usa IF, sem equivalente na camada de métricas |
| % Votos Válidos 1º Turno | nao_traduzida | — | — | depende de [% Votos Válidos], que não foi traduzida |
| % Votos Válidos 2º Turno | nao_traduzida | — | — | depende de [% Votos Válidos], que não foi traduzida |
| Variação entre Turnos p.p. | nao_traduzida | — | — | usa IF, sem equivalente na camada de métricas |
| Municípios | traduzida | municipios | 5 de 5 contextos | DISTINCTCOUNT conta o vazio como um valor; a contagem distinta do bi-html, não; o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| População 2022 | traduzida | populacao_dois_mil_e_vinte_e_dois | 5 de 5 contextos |  |
| PIB per capita | traduzida | pib_per_capita | 5 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Alfabetização | traduzida | alfabetizacao | 5 de 5 contextos | o filtro do CALCULATE se soma ao filtro do leitor; no Power BI ele substitui um filtro na mesma coluna |
| Diferença de Apuração | traduzida | diferenca_de_apuracao | 5 de 5 contextos |  |
| Conferência Válidos | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Cor do Partido | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Cor do Partido Vencedor | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Cor Mudança | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Cor Virada | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Título Eleição | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| Resumo Vencedor | texto | — | — | devolve texto (rótulo, cor ou frase), não número |
| % Abstenção Nacional | nao_traduzida | — | — | usa REMOVEFILTERS, sem equivalente na camada de métricas |

## Páginas e visuais

### Visão Nacional

Spec: `dashboard/paginas/visao_nacional.json`. 7 de 12 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Resumo Vencedor] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | cardVisual | bloco_a | convertido |  |
| (sem título) | cardVisual | bloco_b | convertido |  |
| (sem título) | cardVisual | bloco_c | convertido |  |
| (sem título) | cardVisual | bloco_d | convertido |  |
| (sem título) | cardVisual | bloco_e | convertido |  |
| (sem título) | cardVisual | bloco_f | convertido |  |
| Votos válidos por candidato | barChart | — | nao_convertido | [% Votos Válidos] não traduzida: depende de [Votos Todos os Candidatos], que não foi traduzida |
| Municípios vencidos | barChart | — | nao_convertido | [Municípios Vencidos] não traduzida: usa REMOVEFILTERS, VALUES, sem equivalente na camada de métricas |
| Participação ao longo das eleições | clusteredColumnChart | bloco_g | convertido |  |

### Mapa dos vencedores

Spec: `dashboard/paginas/mapa_dos_vencedores.json`. 1 de 6 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | sg_regiao_nome | filtro_global |  |
| Vencedor por município | azureMap | — | nao_convertido | o mapa usa dMunicipio.local_mapa, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| Partido vencedor por UF | azureMap | — | nao_convertido | o mapa usa dMunicipio.sg_uf_nome, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| Resultado por UF | tableEx | bloco_a | parcial | [Vencedor] não traduzida: devolve texto (rótulo, cor ou frase), não número; [% do Vencedor] não traduzida: usa TOPN, VALUES, sem equivalente na camada de métricas; [Margem de Vitória] não traduzida: usa IF, TOPN, VALUES, sem equivalente na camada de métricas; 1 filtro(s) do visual não foram convertidos |

### Comparecimento e abstenção

Spec: `dashboard/paginas/comparecimento_e_abstencao.json`. 3 de 8 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| Variação vs. eleição anterior | cardVisual | — | nao_convertido | [Variação Abstenção p.p.] não traduzida: usa IF, sem equivalente na camada de métricas |
| Abstenção por UF | azureMap | — | nao_convertido | o mapa usa dMunicipio.sg_uf_nome, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| (sem título) | clusteredBarChart | bloco_a | parcial | 1 filtro(s) do visual não foram convertidos |
| Abstenção x alfabetização | scatterChart | — | nao_convertido | dispersão não tem bloco equivalente no bi-html |
| Abstenção por região ao longo do tempo | lineChart | bloco_b | parcial | a linha virou barras: o eixo não é data; 1 filtro(s) do visual não foram convertidos |
| Brancos e nulos | clusteredColumnChart | bloco_c | parcial | 1 filtro(s) do visual não foram convertidos |

### Mudanças entre eleições

Spec: `—`. nenhum visual convertido

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Municípios que Mudaram] não traduzida: usa VALUES, sem equivalente na camada de métricas |
| (sem título) | cardVisual | — | nao_convertido | [% Municípios que Mudaram] não traduzida: depende de [Municípios que Mudaram], que não foi traduzida |
| (sem título) | slicer | partido_atual | filtro_global |  |
| Municípios que mudaram de partido vencedor | azureMap | — | nao_convertido | o mapa usa dMunicipio.local_mapa, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| Municípios que mudaram de partido vencedor | tableEx | — | nao_convertido | [Partido Vencedor 1º Turno Anterior] não traduzida: depende de [Partido Vencedor], que não foi traduzida; [Partido Vencedor 1º Turno] não traduzida: depende de [Partido Vencedor], que não foi traduzida |
| Variação por UF (p.p.) | pivotTable | — | nao_convertido | o bloco usa uma dimensão; ficaram de fora 1; [Variação p.p.] não traduzida: usa IF, sem equivalente na camada de métricas |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

### Do 1º ao 2º turno

Spec: `—`. nenhum visual convertido

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Municípios que Viraram] não traduzida: usa VALUES, sem equivalente na camada de métricas |
| (sem título) | cardVisual | — | nao_convertido | [% Municípios que Viraram] não traduzida: depende de [Municípios que Viraram], que não foi traduzida |
| Finalistas | tableEx | — | nao_convertido | [Votos 1º Turno] não traduzida: usa REMOVEFILTERS, sem equivalente na camada de métricas; [Votos 2º Turno] não traduzida: usa REMOVEFILTERS, sem equivalente na camada de métricas; [Votos Ganhos no 2º Turno] não traduzida: usa IF, sem equivalente na camada de métricas; [% Votos Válidos 1º Turno] não traduzida: depende de [% Votos Válidos], que não foi traduzida; [% Votos Válidos 2º Turno] não traduzida: depende de [% Votos Válidos], que não foi traduzida; [Variação entre Turnos p.p.] não traduzida: usa IF, sem equivalente na camada de métricas |
| Municípios que viraram no 2º turno | azureMap | — | nao_convertido | o mapa usa dMunicipio.local_mapa, que não traz siglas de UF; o bi-html só desenha o mapa das unidades da federação |
| Municípios que viraram no 2º turno | tableEx | — | nao_convertido | [Vencedor 1º Turno] não traduzida: depende de [Vencedor], que não foi traduzida; [Vencedor 2º Turno] não traduzida: depende de [Vencedor], que não foi traduzida |
| Variação por UF (p.p.) | barChart | — | nao_convertido | [Variação entre Turnos p.p.] não traduzida: usa IF, sem equivalente na camada de métricas |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

### Perfil socioeconômico

Spec: `—`. nenhum visual convertido

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | cardVisual | — | nao_convertido | [Título Eleição] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | slicer | rotulo_turno | filtro_global |  |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| Votos por faixa de PIB per capita | barChart | — | nao_convertido | [% Votos Válidos] não traduzida: depende de [Votos Todos os Candidatos], que não foi traduzida |
| Votos por porte de município | barChart | — | nao_convertido | [% Votos Válidos] não traduzida: depende de [Votos Todos os Candidatos], que não foi traduzida |
| Votos por faixa de alfabetização | barChart | — | nao_convertido | [% Votos Válidos] não traduzida: depende de [Votos Todos os Candidatos], que não foi traduzida |
| PIB per capita x votação por município | scatterChart | — | nao_convertido | dispersão não tem bloco equivalente no bi-html |
| Candidato | slicer | — | nao_convertido | segmentação com valores demais para filtro global (o cubo cresceria demais) |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

### Sobre os dados

Spec: `dashboard/paginas/sobre_os_dados.json`. 1 de 1 visuais com dado viraram bloco ou filtro

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | pageNavigator | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | shape | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| Conferência com o TSE | tableEx | bloco_a | parcial | [Votos Todos os Candidatos] não traduzida: usa REMOVEFILTERS, sem equivalente na camada de métricas; [Conferência Válidos] não traduzida: devolve texto (rótulo, cor ou frase), não número |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |
| (sem título) | textbox | — | decorativo | texto, forma ou navegação: o bi-html desenha o próprio cabeçalho |

### Dica do município

Spec: `—`. página de dica ou oculta: não convertida

| Visual | Tipo no Power BI | Bloco | Status | Motivos |
|---|---|---|---|---|

## Semântica

- cada métrica filtra a própria tabela de origem na tabela convertida, então somas de fatos diferentes não se misturam
- filtro numa tabela que não se liga ao fato da métrica esvazia a métrica no bi-html; no Power BI, não filtra
- o filtro de um CALCULATE se soma ao filtro do leitor; no Power BI, substitui o filtro da mesma coluna
- métrica com escala (por exemplo, R$ tri) usa a métrica base; o bi-html formata a grandeza
- medida sem validação no teste de equivalência leva "(não validada)" na descrição
