# F8 — issues do plugin reveladas pelo caso real

O caso é o projeto de eleições presidenciais do autor:
- 340.702 linhas, uma por candidato × zona × turno;
- quatro eleições, cada uma com dois turnos;
- um .pbix em modo de importação.

O fluxo rodou inteiro sem publicar nada (ver [`RESULTADO.md`](RESULTADO.md)). A pasta de origem não foi alterada: o caso usa uma cópia em `casos/eleicoes/`, ignorada pelo git.

O que funcionou:
- **Ingestão:** leu o CSV inteiro em cerca de 9 s.
- **Reprodução do resultado oficial:** o modelo revisado deu os votos de cada candidato do 2º turno de 2026 iguais aos que o README do projeto cita.
- **Design:** o tema do Power BI virou design system com contraste AA.
- **Documento de decisão:** 25 de 25 números rastreados.
- **Conversão do .pbix:** todas as 17 medidas traduzidas bateram com o Power BI.

Sem remoto no git, as issues ficam aqui, em ordem de impacto. Cada uma traz o que aconteceu, o efeito e uma proposta.

## Alta

### 1. Coluna no grão errado passa sem alerta e vira soma inflada
- **O que aconteceu.** As colunas `zona_*` (aptos, comparecimento, abstenções, válidos, brancos, nulos) e os indicadores do município (`populacao_2022`, `alfabetizacao_2022`, `pib_mil_reais`) repetem em cada linha de candidato. O perfil não emitiu nenhum alerta, e o `propor_modelo` sugeriu somar todas elas.
- **Efeito.** A soma de `zona_aptos` sai multiplicada pelo número de candidatos da zona: o dobro em todo 2º turno e de 10,75 a 13 vezes no 1º turno, conforme a eleição. É um número errado com cara de certo, o risco que o plano mais quer evitar.
- **Proposta.**
  - O perfil detecta colunas constantes dentro de um grupo de colunas de grão maior (zona, município) e alerta.
  - O modelo ganha uma soma que conta uma vez por chave, por exemplo `{tipo: soma, coluna: zona_aptos, uma_vez_por: [ano, nr_turno, cd_municipio_tse, nr_zona]}`.
  - O `propor_modelo` não sugere soma para coluna marcada pelo perfil.

### 2. O Fluxo 1 só lê uma tabela
- **O que aconteceu.** O projeto tem as tabelas no grão certo (`limpo/fVotos.csv`, `limpo/fComparecimento.csv` e as dimensões), mas o modelo de métricas aceita uma fonte só.
- **Efeito.** Abstenção, comparecimento, brancos e nulos ficaram fora do dashboard e do documento. Já o Fluxo 2, com o mesmo modelo vindo do .pbix, calcula todas elas, porque a conversão empilha os fatos (`plano.parquet`).
- **Proposta.** Uma fonte com várias tabelas e relações no `metricas.yaml`, montada pelo mesmo código da conversão (`montar_plano`), para os dois fluxos usarem a mesma regra.

## Média

### 3. O rascunho de modelo soma códigos e percentuais
- **O que aconteceu.** Além das colunas da issue 1, o `propor_modelo` sugeriu somar `cd_municipio_tse`, `cd_municipio_ibge`, `nr_zona` e `nr_candidato` (códigos) e `alfabetizacao_2022` (um percentual).
- **Proposta.**
  - Não sugerir soma para colunas de código (prefixos `cd_`, `nr_`, `id`, ou inteiro com cardinalidade alta e sem significado de quantidade).
  - Para percentual, propor média ponderada ou nada.

### 4. Sem coluna de data não há tempo
- **O que aconteceu.** O tempo do caso é `ano` (inteiro) e `nr_turno`. Sem coluna de data, não há período, linha do tempo nem comparação, e o ano vira uma dimensão comum.
- **Proposta.** Aceitar coluna de ano inteiro como tempo com granularidade `ano`, sem exigir data completa.

### 5. O filtro global não tem valor inicial
- **O que aconteceu.** O dashboard abre com todos os filtros em "Todos" e mostra a soma das oito votações, que conta o mesmo eleitor até oito vezes. O leitor só vê o resultado de uma votação depois de escolher ano e turno, e a spec não deixa definir isso.
- **Proposta.** `filtros_globais` aceita um valor inicial (`{dimensao, inicial}`) e o renderizador abre nele.

### 6. Os achados ignoram o recorte
- **O que aconteceu.** O `gerar_achados` respeita só o período da spec. Os 14 achados somaram as oito votações ("LULA lidera votos nominais", "2 lidera votos por turno"), e o documento de decisão só ficou honesto porque disse isso em todas as frases.
- **Proposta.** Os achados usam o recorte inicial da spec (issue 5) ou recebem um recorte explícito.

## Baixa

### 7. O achado de liderança soma contagem distinta entre grupos
- **O que aconteceu.** No achado por candidato, a contagem total de municípios saiu como a soma das contagens de cada candidato ("5.758 de 227.127"), porque os candidatos se sobrepõem nos municípios.
- **Proposta.** Calcular `contagem_total` numa consulta sem a dimensão.

### 8. O assistente montou 23 perguntas de controle, não 30
- **O que aconteceu.** O critério da F10 pede 30 perguntas, e o gerador só cria o que os blocos permitem; dashboards pequenos ficam abaixo disso.
- **Proposta.** Completar com outros recortes: pares de filtros, segundo colocado, valor de um item com filtro.

### 9. O domínio não foi reconhecido
- **O que aconteceu.** A inferência de design classificou o caso como "outro", com confiança baixa.
- **Efeito.** Sem prejuízo aqui, porque o projeto enviou o próprio tema.
- **Proposta.** Um domínio para dados públicos e eleitorais, com os blocos típicos (mapa por UF, resultado por candidato).

### 10. A mensagem de arquivo não encontrado omite que o caminho é relativo ao projeto
- **O que aconteceu.** `ingerir` com caminho relativo resolve a partir da pasta do projeto, mas o erro mostra só o caminho digitado.
- **Proposta.** Mostrar o caminho resolvido.

## Corrigida durante a F8

### 11. A conversão com pasta de projeto relativa não renderizava nada e dava sucesso
- **O que aconteceu.** Com o projeto num caminho relativo, a importação do tema montava o caminho duas vezes e falhava. A conversão seguia sem renderizar nenhuma página e devolvia `ok`, com `dashboard: null`. Pelo servidor MCP não acontecia, porque ele usa caminho absoluto.
- **Correção.** `converter` resolve o caminho do projeto, e falha de tema passa a sair em `avisos`. O teste está em `tests/test_f8.py`.
