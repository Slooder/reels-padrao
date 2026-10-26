# 02 · Decupagem

## Regra

**A pessoa fala natural; corta-se pouco.** O vídeo do JP ficou "estranho" quando tinha falas de outro vídeo no meio da fala dele e
dissolves entre os pedaços. O que ficou aprovado:

- A fala corre inteira, na ordem gravada.
- Só se corta: **erro de fala** (no 104, o "21, 8" — referência bíblica errada), a **troca de take** e os **respiros longos**.
- Nunca colocar áudio de outra pessoa no meio da fala (o vídeo do Nikolas entrava falando "Eu envelheci" — saiu).
- Nunca dissolve entre pedaços da mesma pessoa: **corte seco**.
- Nunca pausa artificial (no 104 houve uma pausa com whoosh no 0:03; saiu e o começo voltou a ser contínuo).

## Respiros

Só os **muito longos**, e tirando pouco:
- medir pela energia do áudio (janelas de 20 ms; limiar = piso + 35 % da distância até a fala); o Whisper sozinho erra a pausa;
- encurtar só pausas **≥ 0,68 s**; tirar o miolo e deixar **~0,4 s** (0,2 s depois da última palavra e 0,2 s antes da próxima);
- no 104 foram 8 respiros e o vídeo perdeu só 3 s. Pausas normais ficam.
- Em `plano.py`: `RESPIROS = {"A": [(início_do_corte, fim_do_corte), ...]}`; os `TRECHOS` são divididos sozinhos.

## Zoom do rosto (montagem.py)

- Recorte do bruto 4K com zoom contínuo e **leve** (1,00–1,20), ancorado no rosto (medido com YuNet, `ROSTO`).
- "Ficou muito zoom" foi reclamação: keyframes espaçados, variação pequena, nada de pulsar.
- No corte de erro e na troca de take, o zoom **muda de uma vez** no corte (parece troca de câmera e esconde o pulo).
- Quando abre um card em cima (tipo "janela"), a pessoa desce (`ZOOM_JANELA 1.16`, `Y_JANELA 0.56`) para o card não cobrir o rosto.

## Legenda acompanha o corte

`finalizar.py palavras` mapeia cada palavra do bruto para o tempo final. Palavra cujo meio caiu num corte de erro sai; palavra
que o Whisper esticou por cima de um respiro cortado fica presa ao pedaço que restou (ver [08-armadilhas-tecnicas.md](08-armadilhas-tecnicas.md)).
