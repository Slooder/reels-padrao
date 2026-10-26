# Faixa de legenda com alfa (`--so-overlay`)

Para quando a legenda não deve ser queimada agora: o editor ainda vai mexer no corte, ou a legenda entra numa composição com outras camadas (GC, moldura) e só no fim vira um arquivo.

```bash
LEG="$CRIABR_SKILLS"/video-legendas/scripts
python3 "$LEG/legendar.py" --video render/final.mp4 --palavras transcricao/final.palavras.json \
  --saida "legendas/K01 faixa.mov" --so-overlay --formato vertical --inicio 62.4 --fim 91.0            # ProRes 4444
python3 "$LEG/legendar.py" --video render/final.mp4 --cues "legendas/K01 faixa.cues.json" \
  --saida "legendas/K01 faixa.webm" --so-overlay                                                         # VP9 com alfa, das mesmas cues
python3 "$LEG/legendar.py" … --saida "legendas/K01 faixa.mov" --so-overlay --codec ambos                 # os dois de uma vez
```

O `--video` continua obrigatório: é dele que saem o tamanho (quando não há `--formato`), o fps, a duração do trecho e os quadros da conferência de contraste. O vídeo não entra no arquivo.

## O que é gravado (conferido por ffprobe nesta máquina)

| | `.mov` | `.webm` |
|---|---|---|
| codec | ProRes 4444 (`prores_ks`, perfil 4444) | VP9 (`libvpx-vp9`) |
| pixel | `yuva444p12le` (alfa de verdade) | `yuva420p` (alfa de verdade) |
| quadro | o de saída inteiro (ex.: 1080×1920), transparente fora da legenda | idem |
| fps | o da base (ex.: 30000/1001) | idem |
| duração | a do trecho, quadro a quadro (`round(duração × fps)` quadros) | idem |
| áudio | nenhum | nenhum |
| 3 s a 1080×1920 | 6,9 MB (≈ 140 MB por minuto) | 94 kB |
| carimbo | `<arquivo>.da.json`, `ferramenta: video-legendas`, `parametros.so_overlay: true`, cues como insumo | idem |

Tempo medido: 13 s para gravar os dois arquivos de 3 s a 1080×1920 e 29,97 fps (cada quadro inteiro passa pelo codificador: cerca de 2 s de máquina por segundo de vídeo, por codec). Para um vídeo de vários minutos, prefira queimar direto — o `.mov` de 10 minutos passaria de 1 GB.

O alfa é **direto** (não pré-multiplicado): os estados são PNGs RGBA comuns.

## No editor

1. Sequência com o **mesmo tamanho e fps** da faixa.
2. A faixa vai na trilha acima do vídeo, começando no quadro que corresponde a `--inicio` do vídeo de origem (o quadro 0 da faixa é o início do trecho).
3. Não escale, não reposicione: a posição da legenda já é a da direção de arte, dentro da zona segura da plataforma. Se o corte mudar de enquadramento, a legenda continua no lugar certo — é essa a vantagem.
4. Se o corte mudar de **tempo** (tirou um respiro, trocou a ordem), a faixa deixa de bater: gere de novo com o trecho novo, ou legende o export final.

Use o `.mov` no editor. **Não testado dentro de nenhum editor nesta máquina** (Premiere, DaVinci, Final Cut, CapCut): o que foi conferido é a especificação do arquivo e a composição por ffmpeg, abaixo. Se o editor mostrar franja escura na borda das letras, a interpretação do alfa está como pré-multiplicado: troque para direto.

## Compor pelo kit (sem editor)

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(os.environ["CRIABR_SKILLS"] + "/video-direcao-de-arte/kit").expanduser()))
import da, video
d = da.carregar()
video.compor_overlay("cortes/_K01 base.mp4", "legendas/K01 faixa.webm", "cortes/K01.mp4", da_obj=d)
# base e faixa do mesmo tamanho; o carimbo do resultado lista a base e a faixa como insumos
```

`video.compor_overlay` lê o alfa do WebM com `-c:v libvpx-vp9` (sem isso o ffmpeg ignora o alfa). Por cima de um corte já legendado ainda cabe um GC: `compor_overlay("cortes/K01.mp4", "animacoes/gc.webm", …)`.

**Equivalência conferida**: a mesma legenda, queimada direto e composta a partir do `.webm` sobre a mesma base (540×960, 3 s), deu quadros iguais a menos da compressão — diferença média de 0,35 a 0,58 em 255 por canal, percentil 99 de 5 em 255, nos 5 quadros comparados. A faixa é quadro a quadro a legenda queimada.

## Quando não usar

- Corte que vai direto para publicação: queime (`--saida cortes/K01.mp4`); é uma passada e o áudio já vem junto.
- Legenda oculta do YouTube: é o `.srt`, não a faixa.
- Para trocar a aparência no editor: não troque. Cor, fonte e posição são da direção de arte; o que o editor exportar não leva o carimbo da DA, e a conferência final (`da conferencia`) reprova peça sem carimbo.
