# Didática das cenas: o que cada uma mostra, o que simplifica e o que a narração NÃO pode afirmar

Leia a seção da cena **antes de escrever o trecho do roteiro que ela cobre** e de novo antes de aprovar a folha de contato. Cada cena é uma simplificação fiel: o que está na tela é verdade no nível em que é mostrado, mas a narração pode estragar isso afirmando mais do que a imagem sustenta. As fontes do §10 foram abertas em **2026-10-07**; o que é dito aqui está parafraseado delas (nada foi escrito de memória sem conferir a página). Número de modelo específico (tamanho de vocabulário, de janela, de vetor, preço, placar) **não** sai deste arquivo: sai da ficha de fatos (`video-pesquisa-ia`) com `fato_ids` e `fonte`.

Regra geral das oito cenas de modelo (§1 a §8; as de sistema e de estrutura estão no §9):

- Os exemplos padrão são **inventados para ilustrar** e levam o selo "ilustrativo". Trocar por dado real = `ilustrativo: false` + `fonte` + `fato_ids` (o build e o `validar` recusam sem os três).
- O que a cena **calcula de verdade** com os números dados: a soma e a ativação de `rede_neural`; a perda `−ln p` de `treino`; a redistribuição por temperatura e o sorteio com semente de `proximo_token`. O que ela só **desenha**: posições de `embeddings`, pesos de `atencao`, trajetória de `treino`, imagem de `difusao`.
- Verbos como "pensa", "entende", "decide", "sabe" são figura de linguagem. Use de propósito, nunca como explicação técnica.

## 1. `tokenizacao` — frase → pedaços → números

| | |
|---|---|
| **Mostra** | O texto corrido se separa em pedaços (tokens); cada pedaço recebe o número dele no vocabulário; a lista de números é a entrada do modelo. O espaço inicial fica desenhado dentro do pedaço (" não"), como nos tokenizadores que tratam o espaço como parte do token [S2]. |
| **Simplifica** | A divisão e os números do exemplo são inventados. Num tokenizador real, a divisão vem de um vocabulário aprendido: palavras frequentes ficam inteiras e as raras são decompostas em subpalavras [S1][S2]; há mais de um algoritmo (BPE, Unigram, WordPiece) e cada modelo usa o seu [S2]. Um token pode ser palavra, subpalavra, caractere ou byte [S3]. |
| **Não afirme** | "Cada palavra é um token" · "um token são N letras" como regra (a proporção muda com o idioma e com o modelo [S3]) · "o modelo lê letras" · que os números têm significado (são só posições numa tabela) · que o exemplo é a tokenização do modelo X (para isso, rode o tokenizador oficial e passe `tokens` e `ids` reais com fonte). |
| **Erros comuns** | Confundir token com palavra ao falar de preço e de limite; dizer que o texto em português "custa o mesmo" que em inglês; tratar a tokenização como parte "inteligente" do modelo (é uma tabela fixa, aplicada antes). |

## 2. `embeddings` — palavras como pontos; vizinhança; o vetor

| | |
|---|---|
| **Mostra** | Cada palavra tem um lugar num plano; palavras de significado parecido ficam próximas; para o modelo, a palavra é uma lista de números (o vetor), desenhada também como a seta da origem até o ponto. |
| **Simplifica** | O plano é uma **projeção em 2 dimensões** (está escrito na tela); os vetores reais têm centenas ou milhares de números (512 e 1.024 nas duas versões do Transformer original [S6]; o tamanho de um modelo atual é fato com fonte). As posições são inventadas. A ideia de representar palavras como vetores contínuos aprendidos, em que palavras parecidas ficam próximas, vem dos modelos neurais de linguagem [S5] e ficou conhecida com o word2vec [S4]. Nos modelos atuais o vetor é do **token**, não da palavra, e a representação muda de camada em camada conforme o contexto (é o que `atencao` mostra). |
| **Não afirme** | Que os eixos significam algo ("eixo do tamanho", "eixo da fofura") · que a distância no desenho é a distância real (projeção distorce) · "o modelo guarda o significado da palavra" como dicionário · um tamanho de vetor sem fato (`dimensoes` é dado de modelo) · "rei − homem + mulher = rainha" como lei exata: é um exemplo famoso de regularidade, não uma garantia, e só entra no roteiro com fato registrado na ficha (a conta não foi conferida em fonte para este arquivo). |
| **Erros comuns** | Apresentar o mapa 2D como se fosse o espaço real; dizer que cada número do vetor tem um sentido legível; esquecer que a mesma palavra em contextos diferentes termina com vetores diferentes dentro do modelo. |

## 3. `atencao` — um token consulta os outros

| | |
|---|---|
| **Mostra** | Modo `arcos`: um token consulta os outros; a espessura do arco e o percentual são o peso dado a cada um; os pesos somam 100%; a faixa final ("mistura") é a nova representação do token como soma ponderada das outras. Modo `matriz`: todas as linhas (quem olha) × colunas (para quem), cada linha somando 100%. Com `causal: true`, o token só enxerga os anteriores e ele mesmo. |
| **Simplifica** | Uma cabeça de atenção de uma camada, com pesos inventados. No Transformer a saída da atenção é uma soma ponderada dos "valores", com pesos vindos de um softmax (por isso somam 1), e no decodificador uma máscara impede olhar para posições futuras [S6]. O modelo base do artigo original empilha 6 camadas com 8 cabeças cada [S6]; os modelos de hoje têm muito mais — cada cabeça com pesos próprios. O que é misturado não são as palavras, e sim vetores derivados delas. |
| **Não afirme** | "A atenção mostra no que o modelo está pensando" ou "explica a resposta": pesos de atenção não são explicação do raciocínio · que existe **uma** atenção por modelo · que o token "sabe" quem importa (os pesos são calculados, a cada vez, a partir dos vetores) · que um gerador de texto olha para palavras que ainda não foram escritas (por isso o padrão é `causal: true`; `false` só para modelos que leem a frase inteira, como codificadores). |
| **Erros comuns** | Usar o exemplo clássico em que um pronome "olha" para um nome que vem **depois** para explicar um gerador de texto; mostrar uma matriz bonita e chamá-la de "o que o modelo entendeu"; confundir atenção com memória. |

## 4. `proximo_token` — probabilidades, temperatura, sorteio, um token por vez

| | |
|---|---|
| **Mostra** | Para o texto escrito até ali, uma probabilidade para cada continuação candidata; a temperatura redistribuindo as chances; um ponto sorteado numa régua de 0 a 1 dividida conforme as probabilidades; o token sorteado entrando no texto; o ciclo se repetindo. |
| **Simplifica** | De 2 a 6 candidatos por rodada, tratados como se fossem a distribuição inteira (a real cobre o vocabulário todo, dezenas de milhares de tokens [S2]). A temperatura é aplicada como na definição: probabilidade proporcional a exp(logit / t); t menor que 1 concentra a distribuição nos mais prováveis [S7]. A cena faz `p^(1/t)` e renormaliza, que é a mesma conta partindo das probabilidades. O sorteio é real (gerador com `semente`): o resultado fica em `layout.sorteios` do carimbo. `escolha: "maior"` mostra a decodificação gulosa. Fora da cena ficam os cortes da cauda (top-k, top-p/núcleo) que quase todo serviço aplica [S7]. |
| **Não afirme** | "O modelo escolhe a palavra mais provável" (só com `escolha: "maior"`; no uso comum há sorteio) · "temperatura é criatividade" como fato (ela muda a aleatoriedade da escolha [S3]) · "temperatura zero dá sempre a mesma resposta" (nem isso é garantido nas APIs [S3]) · que o modelo planeja a frase inteira **na forma como a cena mostra** (a cena mostra só o laço de geração, um token por vez) · que as probabilidades do exemplo são de algum modelo. |
| **Erros comuns** | "É só um autocompletar" dito para diminuir (o laço é esse, o cálculo de cada distribuição é que é enorme); confundir temperatura com "nível de inteligência"; esquecer que a mesma pergunta pode dar respostas diferentes justamente por causa do sorteio. |

## 5. `rede_neural` — camadas, pesos, a conta de um neurônio, o sinal avançando

| | |
|---|---|
| **Mostra** | Neurônios em camadas; cada ligação com um peso (mais grossa = peso maior em módulo; tracejada = peso negativo); a tabela de um neurônio: entrada × peso, soma, função de ativação; depois o sinal avançando camada por camada até a saída. Os brilhos e os números saem do mesmo cálculo. |
| **Simplifica** | Rede minúscula, sem viés, com a mesma ativação em todas as camadas e pesos sorteados (uma casa decimal, para a conta da tabela fechar à vista). Redes reais têm milhões de pesos ou muito mais (65 milhões na versão base do Transformer de 2017 [S6]; o tamanho de um modelo atual é fato com fonte), termos de viés e arquiteturas que não são só camadas totalmente ligadas; a rede aprende ajustando repetidamente os pesos das ligações [S8], e chama-se "profunda" pela quantidade de etapas encadeadas entre a entrada e a saída [S12]. |
| **Não afirme** | "Funciona como o cérebro" ou "neurônios como os nossos" (o nome é herança histórica; a conta é soma ponderada + função) · que cada neurônio representa um conceito legível · que dá para ler o que a rede "sabe" olhando os pesos · que os rótulos de saída do exemplo são uma classificação real. |
| **Erros comuns** | Desenhar o sinal como eletricidade "pensando"; dizer que a rede "armazena dados" (ela armazena pesos); pular a função de ativação (sem ela, empilhar camadas não acrescentaria nada). |

## 6. `treino` — previsão × resposta, perda, ajuste, curva descendo

| | |
|---|---|
| **Mostra** | O modelo dá probabilidades para o próximo token de uma frase de treino; o texto já traz a resposta; a distância entre a previsão e a resposta vira um número (a perda); os pesos são ajustados um pouco; repetindo, a perda cai. A perda de cada passo é calculada da probabilidade dada à resposta certa (`−ln p`) — a curva sai dos mesmos números das barras. |
| **Simplifica** | Um exemplo só, repetido; uma amostra de 4 a 12 "controles" no lugar de todos os pesos; trajetória inventada. No treino real, cada passo usa lotes de muitos exemplos diferentes, o ajuste de todos os pesos é calculado de uma vez pela retropropagação do erro [S8], e a curva tem ruído. Modelos de linguagem autorregressivos são pré-treinados exatamente nesta tarefa — prever a próxima palavra dado o contexto anterior — em grandes volumes de texto [S3]; etapas posteriores (ajuste fino, treino com feedback humano) ficam fora da cena [S3]. |
| **Não afirme** | "O modelo decora os textos" · "alguém ensina as respostas" (a resposta é o próprio texto) · que a perda chega a zero · que o modelo "aprende ao conversar com você" (os pesos de um modelo em uso não mudam durante a conversa; o que ele "lembra" está na janela de contexto) · quantidade de dados, custo ou tempo de treino sem fato. |
| **Erros comuns** | Mostrar a curva descendo como prova de que o modelo "entendeu"; confundir treino com busca na internet; dizer que cada peso é ajustado "à mão" ou um de cada vez. |

## 7. `janela_contexto` — a faixa que enche; entrada × saída; o que fica de fora

| | |
|---|---|
| **Mostra** | Uma faixa de tamanho fixo; o que você escreve e o que o modelo responde ocupam a **mesma** faixa; a conversa inteira é reenviada a cada turno; quando não cabe, o trecho mais antigo fica de fora e o modelo não o vê. |
| **Simplifica** | Poucas dezenas de casas no lugar de centenas de milhares de tokens. A janela é todo o texto que o modelo consegue consultar ao gerar a resposta, **incluindo a própria resposta** [S9]; a cada turno, a entrada é o histórico inteiro mais a mensagem nova [S9]. O descarte do mais antigo é **uma** política: interfaces de conversa podem gerenciar a janela em fila (o primeiro que entrou é o primeiro que sai) [S9], outras resumem o começo; já uma chamada direta à API cuja entrada excede a janela é recusada com erro, não truncada [S9]. Prompt de sistema, ferramentas, imagens e raciocínio também ocupam a janela [S9] — a cena mostra só mensagens. |
| **Não afirme** | "O modelo tem memória de N tokens" como se guardasse algo entre conversas (a janela é memória de trabalho, diferente dos dados de treino [S3][S9]) · que a janela é o limite de **saída** (o teto de uma resposta é outro número) · "janela maior = resposta melhor" (a documentação descreve perda de precisão em contextos muito longos [S9]) · o tamanho da janela de qualquer modelo sem fato com data. |
| **Erros comuns** | Dizer que o modelo "esqueceu" como se fosse defeito aleatório; confundir janela de contexto com o que o modelo "sabe"; afirmar que todo aplicativo corta o começo da conversa. |

## 8. `difusao` — do ruído à imagem em passos

| | |
|---|---|
| **Mostra** | Um mosaico de ruído; o pedido em texto; a cada passo uma "leitura" (a varredura) e um pouco menos de ruído; no fim, a imagem. O medidor mostra o nível de ruído; cada estado é a mistura imagem + ruído. |
| **Simplifica** | Cinco passos no lugar de dezenas ou centenas (o artigo de referência usa mil passos de difusão [S10]); direto nos "pixels" — a maioria dos geradores atuais trabalha num espaço comprimido e só decodifica para pixels no fim [S11]; e a cena **já conhece a imagem final**, o modelo não: a geração parte de ruído puro e a rede é treinada para estimar o ruído presente em cada etapa [S10]. As formas grandes aparecem primeiro e os detalhes por último [S10] — é o que a frase do último passo diz. |
| **Não afirme** | "A IA monta uma colagem de imagens que viu" ou "busca uma imagem parecida" (não há banco de imagens na geração) · "a imagem estava escondida no ruído" (ruídos diferentes dão imagens diferentes; a `semente` mostra isso) · que o pedido em texto "desenha" (ele condiciona cada passo) · quantidade de passos, resolução ou tempo de um gerador específico sem fato. |
| **Erros comuns** | Confundir difusão com "filtro" aplicado numa foto; dizer que o modelo "apaga o ruído" como quem limpa (ele estima e subtrai, e pode errar); ignorar que o treino é o caminho inverso: aprender a desfazer ruído acrescentado a imagens reais. |

## 9. Cenas de sistema e de estrutura (`rag`, `agente`, `chat`, `terminal`, `comparativo`, `linha_do_tempo`, `numero`, `conceito`, `lista`, `fluxo`, `versus`)

Estas onze cenas não têm fonte própria no §10: o que está abaixo descreve **o que a cena desenha** (conferido no código e nas folhas de contato de 2026-10-12). Qualquer afirmação da narração sobre um produto, um modelo ou um número específico precisa de fato na ficha (`video-pesquisa-ia`), como nas outras.

| cena | mostra | não afirme |
|---|---|---|
| `rag` | A pergunta dispara uma busca; os `k` trechos de maior pontuação entram **no contexto**, junto com a pergunta; a resposta cita cada trecho. A cena recusa resposta que cite trecho não recuperado. | "O modelo aprendeu o documento" ou "foi treinado com os seus arquivos" (nada muda nos pesos: o trecho é lido naquela resposta e some depois) · "com RAG ele não erra" (a busca pode trazer o trecho errado, e o modelo pode ler mal o certo) · que a pontuação é uma probabilidade ou uma nota de verdade (é semelhança com a pergunta) · que o modelo leu a base inteira (só recebeu `k` trechos). |
| `agente` | O laço: o modelo **pede** uma ferramenta, o aplicativo executa, o resultado entra no contexto, o modelo relê tudo e decide o próximo passo, até responder. | "O modelo acessa a internet/a agenda sozinho" (quem executa é o aplicativo, com as permissões que recebeu) · "o agente lembra da última tarefa" (o que ele tem é o contexto desta) · que o número de voltas ou as ferramentas do exemplo são de um produto real. |
| `chat` | A resposta chegando token a token; o contador conta os tokens **da resposta mostrada**. | Que a conversa é a memória permanente do modelo (ver §7) · que o `ritmo` é a velocidade de algum modelo (é escolha de animação) · que a contagem padrão é a de um tokenizador real (é estimativa do exemplo). |
| `terminal` | Um comando sendo digitado e a saída. Os comandos do exemplo (`perguntar`, `contar-tokens`) **não existem**. | Que aquele comando ou aquela saída são reais sem `ilustrativo: false` + fonte. |
| `comparativo`, `linha_do_tempo`, `numero` | Dados do roteiro em tabela, em eixo ou em destaque. Os exemplos padrão são inventados ("Modelo A", "128 mil tokens", meses genéricos). | Preço, tamanho de janela, velocidade, data de lançamento ou qualquer número de modelo sem fato com data — esses valores mudam, e o selo "ilustrativo" não pode ficar numa tela que a narração apresenta como dado. |
| `conceito`, `lista`, `fluxo`, `versus` | O texto do roteiro, sem selo. O exemplo padrão de `conceito` define token como "uma palavra, parte de uma palavra ou um sinal" — nunca "token = palavra" (§1). | Em `versus`, generalizações do tipo "o modelo sempre varia" ou "o programa nunca erra": os padrões dizem "pode variar" e "pode errar" de propósito. Em `fluxo`, que o diagrama é a arquitetura de um produto. |

## 10. Fontes (abertas em 2026-10-07)

- **[S1]** Sennrich, Haddow e Birch — *Neural Machine Translation of Rare Words with Subword Units*. arXiv:1508.07909 (v1 de 31/08/2015). https://arxiv.org/abs/1508.07909 — palavras raras e desconhecidas como sequências de subpalavras (BPE).
- **[S2]** Hugging Face, documentação do Transformers — *Tokenization algorithms*. https://huggingface.co/docs/transformers/tokenizer_summary — BPE, Unigram e WordPiece; palavras comuns inteiras, raras decompostas; espaço como parte do token (SentencePiece); exemplos de tamanho de vocabulário.
- **[S3]** Anthropic, documentação — *Glossary*. https://platform.claude.com/docs/en/about-claude/glossary — definições de token, temperatura (inclusive a nota sobre não determinismo), janela de contexto, pré-treino, ajuste fino e RLHF.
- **[S4]** Mikolov, Chen, Corrado e Dean — *Efficient Estimation of Word Representations in Vector Space*. arXiv:1301.3781 (v1 de 16/01/2013). https://arxiv.org/abs/1301.3781 — vetores contínuos de palavras e similaridade sintática e semântica.
- **[S5]** Bengio, Ducharme, Vincent e Jauvin — *A Neural Probabilistic Language Model*. Journal of Machine Learning Research 3 (2003). https://www.jmlr.org/papers/v3/bengio03a.html — representação distribuída de cada palavra aprendida junto com a função de probabilidade das sequências.
- **[S6]** Vaswani e outros — *Attention Is All You Need*. arXiv:1706.03762 (v1 de 12/06/2017; lida a v7 em HTML). https://arxiv.org/abs/1706.03762 — saída da atenção como soma ponderada dos valores, pesos por softmax, máscara do decodificador, 6 camadas e 8 cabeças no modelo base, vetores de 512 (base) e 1.024 (grande) números, 65 e 213 milhões de parâmetros.
- **[S7]** Holtzman, Buys, Du, Forbes e Choi — *The Curious Case of Neural Text Degeneration*. arXiv:1904.09751 (v1 de 22/04/2019; texto lido em https://ar5iv.labs.arxiv.org/html/1904.09751). https://arxiv.org/abs/1904.09751 — fórmula da amostragem com temperatura, top-k e amostragem por núcleo.
- **[S8]** Rumelhart, Hinton e Williams — *Learning representations by back-propagating errors*. Nature 323, 533–536 (1986). https://www.nature.com/articles/323533a0 — o procedimento ajusta repetidamente os pesos para reduzir a diferença entre a saída obtida e a desejada. A página da Nature pediu login em 2026-10-07; o resumo foi conferido no registro https://inspirehep.net/literature/2171919.
- **[S9]** Anthropic, documentação — *Context windows*. https://platform.claude.com/docs/en/build-with-claude/context-windows — o que conta para a janela, acúmulo por turno, gerenciamento em fila nas interfaces de conversa, erro quando a entrada excede a janela, perda de precisão em contextos longos.
- **[S10]** Ho, Jain e Abbeel — *Denoising Diffusion Probabilistic Models*. arXiv:2006.11239 (v1 de 19/06/2020; texto lido em https://ar5iv.labs.arxiv.org/html/2006.11239). https://arxiv.org/abs/2006.11239 — geração a partir de ruído gaussiano, rede treinada para prever o ruído, mil passos nos experimentos, formas grandes antes dos detalhes.
- **[S11]** Rombach, Blattmann, Lorenz, Esser e Ommer — *High-Resolution Image Synthesis with Latent Diffusion Models*. arXiv:2112.10752 (v1 de 20/12/2021). https://arxiv.org/abs/2112.10752 — difusão no espaço latente de autoencoders pré-treinados, em vez do espaço de pixels.
- **[S12]** Schmidhuber — *Deep Learning in Neural Networks: An Overview*. arXiv:1404.7828 (v1 de 30/04/2014). https://arxiv.org/abs/1404.7828 — "profundidade" como comprimento das cadeias de atribuição de crédito.

Não foi possível abrir em 2026-10-07 (e por isso nada daqui se apoia nelas): a central de ajuda da OpenAI sobre tokens (HTTP 403 para a ferramenta) e o capítulo de redes do livro *Deep Learning* de Goodfellow, Bengio e Courville (a página veio truncada). Se o roteiro precisar de uma afirmação que só essas fontes sustentam, abra-as no navegador e registre o fato na ficha.
