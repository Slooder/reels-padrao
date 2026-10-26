# 06 · Som e entrega

## Som

- **Só a voz de quem fala.** O dono faz efeitos sonoros e trilha à mão; não colocar whoosh, clique, tecla, trilha ou hino sem
  ele pedir (no 104 os efeitos que ele mesmo pediu foram tirados depois: "não gostei, vou fazer manualmente").
- Vídeo de terceiro dentro do Reels: sempre sem som.
- Loudness da entrega: **−14 LUFS, pico ≤ −1 dBTP**, em duas passadas (`finalizar.py <render>`), sem mexer no vídeo (`-c:v copy`).

## Conferências antes de entregar

- `checar_legenda.py`: desvio do centro ≤ 8 px e a mesma altura em todas as frases.
- Loudness medido (ebur128) no arquivo final.
- Folha de quadros do vídeo inteiro (1 quadro a cada 8 s) olhada antes de mandar.
- Nenhuma junção `bundle\public` sobrando em `C:\STUDIO-RENDER-TMP\<NNN>\bundle` (ver armadilhas).

## Arquivos entregues

| arquivo | para quê |
|---|---|
| `publicacao/<nome>-final.mp4` | 1080×1920, h264 crf 16, áudio AAC 256k: o arquivo de postar (só abre no app do computador, passa de 30 MB) |
| `publicacao/<nome>-final-leve.mp4` | 720×1280, crf 28 (~22 MB): para ver no celular |
| prévias `publicacao/v2-*.mp4` / `*.jpg` | as amostras de cada etapa |

Mandar os dois pelo app (o leve chega no celular). Na mensagem: duração, o que mudou, o que foi medido, o que ficou de fora.
