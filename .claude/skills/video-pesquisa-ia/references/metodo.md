# Método de verificação para conteúdo sobre IA

Leia quando um fato não for trivial de confirmar, quando duas fontes divergirem ou quando o roteiro tocar num dos temas abaixo. Os exemplos datados ("visto em 2026-10-06") são observações do dia em que esta skill foi testada: servem para mostrar o **tipo** de armadilha, não como fato. De propósito, este arquivo não traz preço, nota nem especificação de modelo nenhum: o número se lê na página, no dia.

## 0. Vocabulário da ficha

**Primária** é a fonte que tem autoridade sobre o dado: o fabricante sobre o próprio produto (documentação, model card, página de preços, changelog, comunicado), o artigo sobre o próprio resultado, o órgão oficial sobre a lei, quem roda o benchmark sobre o placar que ele mesmo mede. **Secundária** é quem relata, agrega ou explica: imprensa, blog, enciclopédia, agregador de preços, placar que só coleta números de terceiros, glossário.

Primária **não** quer dizer independente. O fabricante é a fonte primária da nota que ele mesmo se deu — e é parte interessada. Por isso a ficha tem dois eixos: `tipo` da fonte (primária/secundária) e `autodeclarado: true` no fato quando o número vem de quem se beneficia dele e ninguém de fora reproduziu.

| `status` | quando usar | pode ir ao roteiro? |
|---|---|---|
| `confirmado` | ≥ 1 primária lida hoje com trecho literal; ou, só em `historia`, `conceito`, `empresa` e `outro`, ≥ 2 secundárias de editores **e domínios** distintos (a mesma página não conta duas vezes). `preco`, `modelo` e `benchmark` só se confirmam com primária — o `validar` recusa o resto | sim, na redação de `como_dizer`, depois de o trecho ser conferido (abaixo) |
| `divergente` | duas fontes sérias dizem coisas diferentes e ainda não se sabe por quê | não — é estado de trabalho (§13) |
| `nao_confirmado` | só boato, só uma secundária, fonte que não abre, memória do modelo | não |

| `confianca` | critério |
|---|---|
| `alta` | **exige primária** (o `validar` recusa `alta` sem ela), trecho conferido na página, sem ambiguidade de unidade, variante ou data |
| `media` | primária autodeclarada sem confirmação independente; ou duas secundárias boas (o teto delas é `media`); ou primária que exigiu interpretação (tabela ambígua, nota de rodapé) |
| `baixa` | qualquer coisa que você não gravaria com o seu nome embaixo |

`caduca_em` é a data depois da qual o fato não pode ser dito sem reabrir a fonte. Sugestão da casa: preço 30 dias, modelo e benchmark 60 dias; história e conceito não caducam. Se a própria fonte anuncia uma mudança (preço "até 31 de dezembro"), vale a data **mais próxima**.

`trecho` é citação literal, no idioma original, de no máximo 25 palavras: o pedaço contíguo da página que contém o dado (pode ser a linha de uma tabela). Literal porque é o que permite ao `checar-links --trechos` acusar que a página mudou; curto porque é citação, não cópia.

**Conferência do trecho** é a prova de que o fato foi lido e não lembrado. `checar-links --trechos` baixa cada página, procura o trecho e grava em cada fonte o campo `conferencia` (só o `fatos.py` escreve nele; vindo no JSON do usuário é descartado): `encontrado`, `ausente` (a página abriu e o trecho não está lá, ou a página saiu do ar) ou `nao_verificado` (o robô não conseguiu ler: bloqueio, PDF, sem resposta). A conferência vale para o par (URL, trecho): trocar um dos dois a apaga. Enquanto houver fonte `ausente`, não verificada ou nunca conferida, o fato **não** ganha crédito de tela, `validar --estrito` e `conferir-roteiro --estrito` reprovam, e `ausente` reprova o roteiro mesmo sem `--estrito`. Quando o robô não lê a página (montada por JavaScript, PDF, site que barra robôs), abra-a você — WebFetch ou navegador — e declare a leitura: `fatos.py atualizar F003 --conferido-manual "onde e como li: tabela Models, linha do modelo, coluna Context window"`. A nota tem no mínimo 20 caracteres e fica na ficha e no `fatos.md`, com a data: é uma assinatura, não um atalho.

`publicado_em` é a data de publicação ou a de "última atualização" que a página declara; `null` quando ela não declara nenhuma. `acessado_em` é o dia em que **você** abriu e leu.

## 1. Decompor antes de pesquisar

Uma frase de roteiro costuma carregar várias afirmações. "O modelo X, lançado em março, lê 1 milhão de tokens e custa metade do Y" são quatro: existência e nome, data, janela de contexto, comparação de preço (que por sua vez são dois preços, cada um com unidade e data). Um fato por afirmação: fato composto não caduca direito — o preço vence em 30 dias e a data de lançamento nunca.

Para cada afirmação pergunte: **quem** (qual variante exata do modelo), **o quê** (qual grandeza, em que unidade), **quando** (a que data se refere), **segundo quem**.

## 2. Benchmark autodeclarado × independente

- Nota publicada pelo fabricante (artigo, model card, post de lançamento) é **autodeclarada**: ele escolheu os testes, as configurações (com ferramentas? com quanto "raciocínio"? quantas tentativas?) e os concorrentes da tabela. Registre com `autodeclarado: true` e escreva o `como_dizer` com atribuição: "segundo a própria empresa, …".
- **Independente** é quem roda o teste por conta própria ou verifica a submissão. Placares diferem nisso — a central da Epoch AI, por exemplo, declara quais avaliações ela mesma administra e quais coleta de fontes externas (visto em 2026-10-06). Leia a página de método antes de chamar um número de independente.
- Benchmarks têm **variantes** com números incomparáveis: a página do SWE-bench separa várias, cada uma em sua aba (confira lá quais existem no dia). O fato precisa dizer qual.
- Placares de preferência humana (arenas) medem gosto de quem vota, não acerto. Placares de uso (roteadores) medem o tráfego daquele serviço, não o mercado.
- "Primeiro lugar" é o fato mais perecível que existe: registre a posição **com a data do placar** e `caduca_em` curto. No roteiro, prefira a nota ao ranking.
- Diferenças pequenas entre modelos costumam estar dentro do ruído. Sem intervalo de confiança na fonte, não diga "supera".

## 3. Janela de contexto × limite de saída × tokens

- **Janela de contexto** é quanto o modelo considera de uma vez (entrada + o que já gerou); **saída máxima** é quanto ele escreve numa resposta. São linhas diferentes da mesma tabela e a segunda costuma ser muito menor. "Lê um livro inteiro" não autoriza "escreve um livro inteiro".
- A janela anunciada pode depender de plano, de nível de acesso, de cabeçalho beta ou da nuvem em que o modelo roda. Registre a condição em `notas`.
- **Token não é palavra**, e a conversão muda com o idioma e com o tokenizador. A documentação de um laboratório pode avisar que uma geração nova usa outro tokenizador, que gera mais tokens para o mesmo texto (vi um aviso assim numa página oficial de preços em 2026-10-06; o tamanho da diferença se lê lá): o mesmo "1 milhão de tokens" cabe menos texto num modelo que no outro. Se o roteiro traduz tokens em palavras ou páginas, a conversão é outro fato, com fonte.
- Limites em "K" e "M" são arredondamentos; o número exato às vezes está só na API.

## 4. Preço por milhão de tokens

Preço de API não é um número: é uma tabela. Antes de registrar, identifique na página:

1. **Entrada × saída** (a saída costuma custar várias vezes mais) e, em modelos com raciocínio, se os tokens de raciocínio são cobrados como saída.
2. **Cache**: leitura e escrita de cache têm preços próprios.
3. **Modalidade de processamento**: lote, prioridade, modo rápido. A página da OpenAI separava colunas por modalidade e por contexto curto × longo (visto em 2026-10-06).
4. **Faixas**: preço que muda acima de certo tamanho de prompt.
5. **Nível**: gratuito × pago; e a nuvem — o mesmo modelo pode custar diferente no laboratório e em cada nuvem.
6. **Vigência**: preço com data marcada para mudar. Uma tabela oficial pode trazer o preço de agora "até" uma data e o novo "a partir de" outra — e, mais tarde, uma nota de rodapé dizendo que o aumento anunciado não vai mais ocorrer (vi as duas formas em páginas oficiais de preços em 2026-10-06). Registre a mudança na `afirmacao`, ponha `caduca_em` antes dela e, se o roteiro vai dizer também o preço novo, escreva-o no `como_dizer` — número que está só na `afirmacao` não valida frase do roteiro.
7. **Unidade e moeda**: por 1M de tokens, em dólar. Converter para real é outro fato (câmbio do dia) — prefira dizer em dólar.

Comparar "preço por milhão" entre modelos com tokenizadores diferentes engana (§3): o mais barato por token pode sair mais caro por documento. Assinatura de aplicativo (por usuário/mês) é outra página e outro fato; nunca misture com API.

## 5. Data de anúncio × disponibilidade

"Lançou" pode significar: anunciado; em prévia para convidados; disponível na API; disponível no aplicativo; disponível em tal nuvem; disponível no Brasil. A data de cada um é diferente. O fato deve dizer qual, e a fonte certa é o changelog ou a nota de versão (data em que passou a valer), não o post de anúncio.

O outro lado é o desligamento: laboratórios publicam a data em que um modelo é descontinuado e a data em que para de responder. Vídeo que ensina a usar um modelo deve checar a página de descontinuações — e a ficha, a data de "aposentadoria não antes de".

## 6. Pesos abertos × código aberto

- **Pesos disponíveis** (dá para baixar e rodar) não é o mesmo que **código aberto**. A Open Source AI Definition 1.0 da OSI exige informação suficiente sobre os dados de treino, o código e os parâmetros (visto em 2026-10-06); pesos sozinhos não bastam.
- Muitas licenças de modelos "abertos" restringem uso comercial, tamanho da empresa ou finalidade. A licença está no cartão do modelo (metadado `license`) e no arquivo de licença do repositório: cite o nome exato dela.
- Redação segura: "pesos abertos sob a licença X" ou "disponível para baixar". "Open source" só se a licença for reconhecida como tal.

## 7. Nomes e versões de modelo

- Família, modelo, versão e instantâneo são coisas diferentes. Um apelido de API pode apontar para instantâneos diferentes ao longo do tempo, ou não: na Anthropic, os identificadores sem data passaram a ser instantâneos fixos a partir de certa geração (visto em 2026-10-06). O que vale para um laboratório não vale para outro.
- O nome do aplicativo, o do modelo e o do modo ("pensando", "rápido", "pro") se confundem na imprensa. O fato registra o identificador **como a documentação escreve**.
- O mesmo nome pode ter capacidades diferentes por nuvem ou por plano.
- Nomes de modelos que você "lembra" podem já ter sucessores: em 2026-10-06 as três páginas de modelos abertas para o teste desta skill listavam modelos lançados nas semanas anteriores. Nunca escreva "o mais recente" de memória.

## 8. Data de corte de conhecimento

- Há mais de uma data. A tabela da Anthropic trazia duas linhas, "Reliable knowledge cutoff" e "Training data cutoff" (visto em 2026-10-06). Diga qual.
- Perguntar ao modelo qual é a data de corte dele **não é fonte**: a resposta é texto gerado, não leitura de um registro, e pode estar errada. A fonte é a documentação ou o relatório de transparência.
- Corte de conhecimento não impede o produto de responder sobre fatos recentes quando ele usa busca. "Só sabe até tal data" pede a ressalva "sem busca".

## 9. Parâmetros, dados de treino e custo de treino

Laboratórios de modelos fechados raramente divulgam número de parâmetros, tamanho do conjunto de treino ou custo. Números que circulam costumam ser estimativa de terceiros. Regra: se a fonte primária não divulga, o fato é `nao_confirmado` e o roteiro diz "a empresa não divulga" (que é, isso sim, um fato confirmável) — ou cita a estimativa **como estimativa, com autor**.

## 10. Afirmações de marketing

"O mais inteligente", "nível de doutorado", "raciocina como humano", "AGI", "revolucionário": texto de lançamento não é medida. Dá para registrar como citação atribuída ("a empresa descreve o modelo como…"), nunca como fato do canal. Cuidado com gráficos de lançamento: eixo cortado, concorrente desatualizado, teste escolhido a dedo.

## 11. Como citar artigo científico

- arXiv é pré-publicação: o próprio site avisa que o material não é revisado por pares pelo arXiv (visto em 2026-10-06). Se o artigo saiu em conferência ou periódico, prefira citar a versão publicada e diga onde.
- `publicado_em` é a data da **primeira** versão (v1), que é quando o resultado veio a público; a versão que você leu vai no `titulo` ("…, v7"). No teste desta skill, registrar a data da v7 fez o crédito sair "arXiv, ago/2023" para um artigo de 2017.
- Cite pelo que o artigo **mostra**, não pelo que o resumo promete: "num teste com N exemplos de tal conjunto, …". Resultado de artigo vale para aquele modelo, aquela configuração, aquela data.
- Um artigo não é consenso. "Estudos mostram" exige mais de um; com um só, diga "um estudo de [instituição], de [ano]".
- `editor` é o veículo (arXiv, NeurIPS, Nature); os autores entram na `afirmacao` ou no `titulo`.

## 12. Quando a fonte secundária basta

- Fato histórico estável e incontroverso, com duas secundárias de editores e domínios distintos e de boa reputação (a confiança fica em `media`: `alta` exige primária).
- Conceito de livro-texto, com um glossário ou material didático de referência **mais** a fonte original quando for fácil (no teste: o artigo do Transformer + o glossário de ML do Google).
- Fato sobre empresa noticiado por dois veículos que **não** se citam um ao outro. Dez sites repetindo a mesma agência são uma fonte.

Nunca basta para: preço, especificação de modelo, pontuação de benchmark, data de lançamento. Nesses casos a primária existe e está a um clique (`fontes-primarias.md`), e o `validar` **recusa** `confirmado` sem primária nas categorias `preco`, `modelo` e `benchmark`. Enciclopédia, fórum e agregador servem para **achar** a primária; o `validar` avisa quando um deles está marcado como primária e quando um fato se sustenta só neles.

## 13. Divergência entre fontes

1. **É a mesma coisa?** Nove em dez divergências são de unidade, variante, modalidade, nuvem ou data. Alinhe antes de comparar.
2. **Primária vence secundária.** Se a imprensa diz 2 e a documentação diz 1, vale 1 — e a `notas` registra que há veículos dizendo 2.
3. **Entre primárias, vale a mais específica e a mais recente**: tabela de referência > post de anúncio; changelog datado > página de marketing. Use a Wayback Machine para ver o que a página dizia na data do anúncio.
4. **Continuou divergente?** Registre com `status: "divergente"`, as duas fontes e `notas` dizendo quem diz o quê. Depois escolha: (a) reescreva a afirmação de modo que as duas fontes a sustentem — atribuição ("a documentação lista X; o anúncio falava em Y") ou faixa ("entre X e Y") — e aí ela vira `confirmado`; ou (b) tire do roteiro. `conferir-roteiro` reprova qualquer fato citado que não esteja `confirmado`.

## 14. Fórmulas de `como_dizer`

| situação | escreva | não escreva |
|---|---|---|
| fato volátil | "Em outubro de 2026, a tabela oficial listava…" | "Hoje custa…", "atualmente" |
| número autodeclarado | "Segundo a própria empresa, o modelo acertou…" | "O modelo acerta…" |
| arredondamento | "cerca de 1 milhão de tokens" | "1 milhão" quando a fonte diz outro número |
| comparação | "no teste Z de [data], A marcou x e B marcou y" | "A é melhor que B" |
| preço | "US$ x por milhão de tokens de entrada, no nível pago" | "custa x" |
| ausência de dado | "a empresa não divulga o número de parâmetros" | um número de fórum |
| estimativa | "a [instituição] estima…" | a estimativa como fato |

O vídeo fica no ar por anos. Toda frase com fato volátil precisa continuar verdadeira para quem assistir depois que o dado mudar — é isso que a data na frase compra.

## 15. O que o conferidor vê, o que não vê e quanto erra

`conferir-roteiro` trabalha por padrões de texto; ele **não** entende a frase. O que ele faz:

- **Lê** dígitos e numerais por extenso ("nove dólares", "noventa por cento", "dois mil e dezessete", "três em cada quatro", "metade", "o dobro", "caiu dez vezes"), dinheiro com a moeda, percentuais, datas, nomes de modelo, nomes próprios, superlativos e tempo relativo.
- **Compara por tipo** na frase marcada: dinheiro com dinheiro (e a moeda), percentual com percentual, data com data, contagem com contagem. O que o roteiro pode dizer é o `valor`, o que está no `como_dizer` e nos `termos`. Número que só aparece na `afirmacao` como outro dado, ou só no trecho da fonte, não valida a frase.
- **Acusa trocas típicas** em frase marcada: entrada × saída ("escrevia até 1 milhão de tokens" citando o fato da janela de contexto), grandeza ("1 milhão de palavras" citando fato de tokens), cobrança ("por mês" citando preço de API), modelo que não é o do fato.
- **Exige marcador**: dado checável sem `[F###]` é pendência mesmo quando um fato parece cobri-lo (o relatório sugere qual; não aplica sozinho). Nome com versão que nenhum fato confirmado registra, verbo de lançamento/preço/licença/compra e tempo relativo junto de um nome também são pendência.

O que continua por sua conta:

- afirmações conceituais sem número nem nome ("o modelo entende contexto", "a IA aprende sozinha") — ele não vê;
- causalidade e intenção ("a empresa fez isso porque…");
- o **sentido**: "oito pesquisadores **do MIT**" citando o fato dos oito autores só gera aviso (nome fora do fato); "inventaram a IA" no lugar de "publicaram um artigo" passa se os números baterem;
- "um" e "uma" sozinhos ("um gigawatt") e quantidades vagas ("a maioria", "quase todos") não são lidos como número;
- qual número vai com qual data: se o `como_dizer` traz dois (o preço de agora e o aumento anunciado), a frase passa com qualquer um deles em qualquer data — mais um motivo para um fato por afirmação;
- contagens editoriais e durações, que ele ignora de propósito ("3 motivos", "em 60 segundos", "0–3s") — se "responde em 2 segundos" for afirmação de desempenho, marque o fato à mão;
- número pequeno em fala na primeira pessoa, em chamada ("comenta 1", "manda para 2 amigos") ou em analogia declarada ("imagina 1 milhão de livros") é ignorado e listado em "NÚMEROS IGNORADOS"; em frase dirigida ao espectador ("você sabia que só 5 países…") vira **aviso**, porque tanto pode ser dado quanto jeito de falar;
- o que está na **tela**: `conferir-storyboard` compara, por tipo, os números do `trecho`, dos textos de `params` e de `params.dados[].valor` (com `prefixo`/`unidade`) com os fatos citados — mas não lê imagem, não confere rótulo nem a ordem das barras.

**Quanto erra (medido em 2026-10-06, uma frase por vez, contra uma ficha de 4 fatos):** no conjunto de 42 frases problemáticas e 14 inocentes do revisor, que serviu para **ajustar** as regras, nenhuma problemática passa e nenhuma inocente vira pendência (uma vira aviso). Num segundo conjunto (48 + 20), também usado para ajuste: 2 de 48 passam no modo padrão, 1 passa até com `--estrito` ("um gigawatt") e 1 inocente vira pendência. Numa **medição cega** final (30 + 20 frases novas, sem ajuste depois): 5 de 30 problemáticas passaram no modo padrão — três como aviso de nome próprio ("O Gemini entende vídeos de até uma hora", "O Brasil é o terceiro país que mais usa o ChatGPT", "O modelo novo da Anthropic erra bem menos que o anterior"), uma como aviso de superlativo em frase marcada (regra que depois virou pendência, sem nova medição cega) e uma sem nada ("Treinar um modelo desses consome a energia de uma cidade pequena") —; essa última passou também com `--estrito`; e 1 de 20 inocentes virou pendência ("Eu uso IA todo dia há 2 anos"). Conte com isto: em frases que as regras nunca viram, perto de uma em cada seis afirmações problemáticas escapa do modo padrão, quase todas com aviso; com `--estrito`, o que escapa é a afirmação sem número nem nome.

Por isso o portão de gravação é `--estrito` (aviso também reprova) **mais** a leitura humana do relatório; e `[sem-fato]`/`[opinião]` existem para o falso positivo, não para silenciar afirmação.
