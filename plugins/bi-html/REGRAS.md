# Regras do bi-html

> Valem em toda sessão em que o plugin é usado. A regra 1 é a razão de existir
> do plugin; as outras protegem ela.

1. **Nenhum número sai do modelo de linguagem.** Todo valor que aparece num
   dashboard, num documento de decisão ou numa resposta sobre os dados vem de
   uma ferramenta do servidor `bi-dados` (hoje: `validar_spec`,
   `estado_do_ciclo`, `checar_contrato`, `ingerir`, `ingerir_texto`, `perfilar`,
   `propor_modelo`, `validar_modelo`, `consultar`, `exportar_cubo`, `propor_estilos`,
   `aplicar_estilo`, `importar_design` e `renderizar_dashboard`; na próxima fase:
   achados). Ao mostrar um número, use o texto de `formatado` que a ferramenta devolve.
   Números já escritos na conclusão revisada da análise podem ser repetidos como
   estão, nunca recalculados de cabeça. Se a
   ferramenta não existe ainda, diga isso ao usuário em vez de calcular.
2. **A spec descreve, não informa.** Ao escrever uma spec de dashboard, ligue
   cada bloco a métricas por id. Textos não levam algarismos: um valor no
   texto entra como marcador `{id_da_metrica}`, e a métrica precisa estar no
   próprio bloco; num bloco com dimensão, o marcador mostra o valor da primeira
   linha (a líder, na ordenação do bloco). Valide sempre antes de seguir.
3. **A análise vem antes.** O caminho padrão é Planilha → `/analise` do plugin
   `analise-dados` → dashboard → documento de decisão. O atalho sem análise
   existe, mas o dashboard sai com o aviso "sem análise prévia".
4. **A pasta do projeto é a do `analise-dados`.** `dados/` guarda os originais
   e não é editada; derivados vão para `saidas/`; `contexto.md` é a memória do
   projeto e é lido antes de qualquer pergunta ao usuário.
5. **Dados pessoais não são publicados.** Arquivo com CPF, e-mail ou telefone
   fica privado até as colunas serem removidas ou agregadas.
6. **Português do Brasil** em tudo que o usuário lê: `R$ 1.234,56`, `12,3%`,
   `31/12/2025`, comparações explícitas ("vs. mês anterior").
