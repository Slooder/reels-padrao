# 03 · Legenda

Referências do dono: `projetos/104. JP/LEGENDA (FONTE HELVETICA COM ESPAÇAMENTO MENOR).png` e `ESTILO LEGENDA E REELS.mp4`.

## Especificação aprovada (não mudar sem pedido)

| item | valor |
|---|---|
| fonte | Helvetica Bold (`da/fontes/Helvetica-Bold.ttf`), branca `#FFFFFF` |
| tamanho | 72 px num vídeo 1080×1920 (`legenda.tamanho` 0,067 da DA) |
| espaçamento | letras apertadas: tracking −0,045 em; entrelinha 1,0 |
| linhas | **uma linha só**, até 4 palavras e ~22 caracteres por frase |
| altura | centro do texto a **79 %** da altura (y ≈ 1517 de 1920) — "mais para baixo" foi pedido duas vezes |
| centro | centralizada de verdade: desvio ≤ 8 px **medido** (`checar_legenda.py`; no 104 deu 2 px) |
| tamanho igual | todas as palavras do mesmo tamanho; nenhuma palavra maior em destaque |
| animação | **nenhuma**: a frase aparece pronta e é trocada pela próxima |
| emenda | uma frase fica até a próxima começar (sem buraco entre frases) |
| sombra | **nenhuma** no texto |
| caixa | texto como foi falado (maiúscula no começo de frase, pontuação), grafia corrigida (nomes próprios) |

- **Sombra leve embaixo** (não no texto, no vídeo): degradê preto de 58 % da altura até a base, 38 % de opacidade no fim
  (referência "Dreamy digital product…"). Fica atrás da legenda e embaixo dos inserts.
- Quebra das frases: em pontuação, em pausa > 0,45 s, no limite de 4 palavras ou quando não cabe na linha.
- **Some** nas telas cheias (prints, mapa, ranking, vídeo de terceiros, versículo, final) — elas têm texto próprio.
- **Tela dividida:** a legenda vai para a linha do meio (y = 960), porque na altura normal cobriria o rosto.
- Pode encostar na descrição do post em alguns celulares nessa altura; o dono aprovou mesmo assim.

## Como conferir

Antes de renderizar: stills das 6 primeiras frases (folha) + 1 tela cheia, mandados em JPG.
Depois do render: `python checar_legenda.py <video>` → "FORA DO CENTRO: nenhuma". Ele compara com a base sem legenda e ignora as
telas cheias e a dividida.

## O que já foi tentado e reprovado

- Legenda no centro da tela / em cima da boca → "muito em cima".
- Legenda deslocada para a esquerda (centrada na zona segura e não no vídeo) → "descentralizada".
- Duas linhas, palavra-chave maior, palavra acendendo quando é dita, palavras apagadas esperando → "quero texto simples, uniforme, sem animação".
- Sombra no texto.
