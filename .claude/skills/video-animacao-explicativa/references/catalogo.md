# Catálogo: as 19 cenas da biblioteca

Uma linha por cena. A lista viva (com tipos, faixas, padrões e os passos sincronizáveis) é sempre `sb cenas` e `sb cenas <nome>`; esta página serve para escolher. Todas saem em horizontal, vertical e quadrado, com fundo opaco. A duração é a padrão da cena: `adicionar` recalcula com o ritmo da DA do projeto.

**Selo**: "ilustrativo" = o exemplo padrão é inventado e sai com o selo na tela. "texto" = a cena mostra o texto do próprio roteiro e sai sem selo (número ou nome de modelo dentro dela pede `ilustrativo: true` ou fonte). Dado real, em qualquer cena: `"ilustrativo": false` + `"fonte"` + `fato_ids`.

## Como o modelo funciona

| cena | dur | mostra | parâmetros principais | selo |
|---|---|---|---|---|
| `tokenizacao` | 9 s | a frase quebrada em pedaços e o número de cada pedaço | `tokens` (com o espaço dentro: `" não"`), `ids`, `destaque` | ilustrativo |
| `embeddings` | 10 s | palavras como pontos num plano; vizinhança; o vetor | `pontos [{rotulo, x, y}]`, `destaque`, `vizinhos`, `vetor`, `dimensoes` | ilustrativo |
| `atencao` | 11 s | um token consulta os outros com pesos que somam 100% | `tokens`, `pesos`, `consulta`, `modo` (`arcos`, `matriz`), `causal` | ilustrativo |
| `proximo_token` | 20 s | probabilidades, temperatura, sorteio, um token por vez | `contexto`, `rodadas[].candidatos [{token, prob}]`, `temperatura`, `comparar`, `escolha` (`sorteio`, `maior`), `semente` | ilustrativo |
| `rede_neural` | 14 s | camadas, pesos, a conta de um neurônio, o sinal avançando | `camadas`, `entradas`, `pesos`, `ativacao` (`relu`, `sigmoide`, `tanh`), `foco`, `rotulos_saida`, `semente` | ilustrativo |
| `treino` | 15 s | previsão × resposta do texto, perda, ajuste, curva descendo | `contexto`, `alvo`, `outros`, `prob_alvo`, `pesos_visiveis`, `semente` | ilustrativo |
| `janela_contexto` | 14 s | a faixa de tamanho fixo enche; entrada e saída na mesma janela; o que não cabe fica de fora | `capacidade`, `blocos [{rotulo, tokens, tipo}]`, `tokens_por_celula` | ilustrativo |
| `difusao` | 16 s | do ruído à imagem em passos, guiada pelo pedido | `imagem` (mosaico em texto), `pedido`, `passos`, `semente` | ilustrativo |

## Sistemas em volta do modelo

| cena | dur | mostra | parâmetros principais | selo |
|---|---|---|---|---|
| `rag` | 18 s | a pergunta dispara uma busca, os trechos mais parecidos entram no contexto e a resposta cita cada um | `pergunta`, `documentos [{titulo, trecho, pontuacao}]`, `k`, `resposta` (cita `[1]`…`[k]`), `nome_base`, `rotulo_pontuacao` | ilustrativo |
| `agente` | 20 s | o laço modelo → pedido de ferramenta → execução pelo aplicativo → resultado no contexto → resposta | `tarefa`, `voltas [{ferramenta, entrada, resultado}]`, `resposta`, `nome_modelo`, `nome_ferramentas`, `quem_executa` | ilustrativo |
| `chat` | 12 s | bolhas de pergunta e resposta; a resposta chega token a token, com contador | `mensagens [{de: usuario\|modelo, texto}]`, `ritmo`, `contador`, `nome_usuario`, `nome_modelo` | ilustrativo |
| `terminal` | 11 s | comando digitado com cursor e a saída embaixo, até 3 blocos | `blocos [{comando, saida[]}]`, `prompt`, `janela`, `saida_modo` (`linhas`, `fluxo`), `destaque` | ilustrativo |

## Estrutura do roteiro

| cena | dur | mostra | parâmetros principais | selo |
|---|---|---|---|---|
| `conceito` | 9 s | um termo, a definição curta e um exemplo num cartão | `termo`, `definicao`, `exemplo`, `sub`, `rotulo_exemplo` | texto |
| `lista` | 11 s | tópicos que entram um a um; o da vez em destaque | `itens` (`*termo*` destaca), `chamada`, `marcador` (`numero`, `ponto`, `traco`, `nenhum`), `anteriores`, `recapitular` | texto |
| `fluxo` | 13 s | caixas e setas reveladas passo a passo; ciclos viram arcos | `nos [{id, rotulo, sub}]`, `ligacoes [{de, para, rotulo, tracejada}]`, `ordem`, `destaque`, `direcao` | texto |
| `versus` | 12 s | dois lados na mesma tela, revelados aos pares | `lados [{titulo, itens}]`, `divisor`, `revelar` (`pares`, `lados`), `destaque` | texto |
| `comparativo` | 13 s | opções × critérios, um critério por vez (tabela no horizontal, blocos no vertical) | `criterios`, `opcoes [{nome, valores}]`, `destaque_opcao`, `destaque_criterio`, `disposicao` | ilustrativo |
| `linha_do_tempo` | 13 s | marcos com data sobre um eixo (tracejado = só a ordem; `escala: "tempo"` = proporcional) | `marcos [{data, titulo, texto}]`, `escala`, `destaque` | ilustrativo |
| `numero` | 7 s | um dado grande com contagem, rótulo, frase do que ele mede e crédito | `valor`, `unidade`, `prefixo`, `casas`, `rotulo`, `contexto`, `contagem` | ilustrativo no exemplo; com `valor` seu a cena exige a escolha |

Parâmetros comuns a todas: `titulo`, `legendas`, `passos_t`, `cor` (token da DA), `ilustrativo`, `fonte`, `plataforma`, `reservar_legenda`.

Do kit, pelo mesmo storyboard: `titulo` (cartela), `citacao`, `barras` (gráfico) e `gc`. Conceito que nenhuma cena cobre: cena própria em `<projeto>/animacoes/cenas/` (`biblioteca.md` §4).
