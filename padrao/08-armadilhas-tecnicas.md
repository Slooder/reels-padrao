# 08 · Armadilhas técnicas (já aconteceram)

- **Junção do bundle levou `projetos/` embora (23/10, 03:17).** O render do Remotion usa uma junção
  `C:\STUDIO-RENDER-TMP\<NNN>\bundle\public → D:\STUDIO\studio\projetos` (para não copiar GB). Um `robocopy /MOVE` de outra sessão
  varreu a pasta temporária, seguiu a junção e moveu os projetos de todos os vídeos para o D:. Foi parado e devolvido sem perda.
  Agora `render_remotion.py` cria a junção só durante o render e apaga no fim (`rmdir` na junção apaga só o atalho).
  Nunca mover/copiar/limpar `STUDIO-RENDER-TMP` sem `/XJ` e sem apagar as junções antes.
- **Legenda medida errado.** Medir pelo branco puro só funciona sobre fundo escuro; no pescoço (cinza ~226) a diferença some.
  `checar_legenda.py` compara com a base sem legenda (pixel > 245 e mais claro que a base) e mede no fim de cada frase, fora das
  telas cheias. Amostra no instante errado (frase saindo) também dá falso desvio.
- **Whisper estica a palavra por cima da pausa** ("E" de 58,96 a 59,98 s). Ao cortar o respiro, a palavra sumia da legenda.
  `finalizar.py` prende a palavra ao pedaço que contém o meio dela ou, se o meio caiu no corte, o fim dela.
- **Vídeo de terceiro com legenda queimada** (no do Nikolas, em y 1920–2040 do 4K). Recorte que esconde a legenda corta o corpo
  das pessoas; em tela cheia ela aparece — e a nossa legenda some nesse trecho.
- **O vídeo do Nikolas só tem 2,4 s dele falando**; depois ele levanta da cadeira. Medir cortes de cena (diferença entre quadros)
  antes de escolher trechos de vídeo de terceiro.
- **Primeiro trecho de um clipe com a pessoa errada**: o depoimento "Sou nordestina" começa na imagem do homem anterior; o
  corte de cena era em 10,6 s. Conferir o quadro do início de cada clipe.
- **Mapa com ilhas**: Fernando de Noronha alargava a caixa e deixava o mapa pequeno e torto; tirar ilhas oceânicas.
- **Quebra de linha `\n` em Python via heredoc/sed** virou quebra de verdade e quebrou o `plano.py` duas vezes: editar esses
  textos com a ferramenta de edição, não com sed/heredoc.
- **`Freeze` do Remotion** segura o último quadro da pessoa depois do fim do take (a base fica preta depois); o escurecimento tem
  que terminar antes dele para não aparecer imagem parada.
- **Arquivo final > 30 MB não chega no celular**: sempre mandar também a versão leve.
- **Nunca pôr o e-mail do dono em cabeçalho de requisição** (aconteceu ao baixar a bandeira do Wikimedia).
