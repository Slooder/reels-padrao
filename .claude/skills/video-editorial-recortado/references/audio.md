# Áudio: trilha e efeitos

A referência é muda. O som do estilo foi desenhado para soar como **papel e escritório**: trilha calma por baixo, e cada palavra que entra tem um som curto e seco. Todo o som é sintetizado por `audio/synth.py` (sem samples) a partir dos `cue()` da página.

## Trilha

```js
VIDEO = { …, bpm: 92, music: { style: 'ambient_major', key: 'F', gain: 0 } }
cue('m:break', 0);           // pads + arpejo esparso desde o 1º quadro (o começo não pode ficar mudo)
cue('m:build', T.sub);       // arpejo em semicolcheias + baixo quando o subtítulo começa
cue('m:stop', VIDEO.dur - .2);
```

- `ambient_major`: pads lentos, arpejo vítreo e baixo em triângulo; clima de documentário leve, sem bateria.
- Evite `m:intro` em vídeo curto: ela é só pad filtrado e deixa os primeiros 2 s ~15 dB abaixo do resto.
- Não use `m:drop`/`m:main` neste estilo: entram bumbo e palmas, que brigam com a calma editorial.

## Efeitos (onde caem)

| evento | efeito | ganho | quem marca |
|---|---|---|---|
| cada palavra do título | `paper` | −1 dB | `ED.sobe(…, {som:'paper'})` |
| sublinhado de pincel | `marker` | −3 dB | `ED.sublinhado` (automático) |
| título sobe | `whoosh_slow` | −4 dB | página: `cue('whoosh_slow', T.sobe - .05, {gain:-4})` |
| cada palavra do subtítulo | `pop` | −2 dB | `ED.sobe(…, {som:'pop'})` |
| faixa da etiqueta começa a crescer | `swoosh` | −11 dB | `ED.etiqueta` (automático) |
| palavra solta aparece | `focus_tick` | +2 dB | `ED.etiqueta` (automático) |
| palavra pula para a faixa | `key` (tecla de máquina) | −5 dB | `ED.etiqueta` (automático) |
| última etiqueta montada | `chime` | −9 dB | página: `cue('chime', fimDaÚltima + .12, {gain:-9})` |

- O pan das etiquetas segue a posição na tela (esquerda/direita).
- Efeitos iguais a menos de 60 ms viram um "flam": `ED.som` empurra o segundo alguns quadros. Use-o para qualquer efeito repetido que você acrescentar.
- Evite `credit_swell` no respiro final: é um chiado largo de ~2 s que ocupa o espaço que deveria ser calmo.

## Ordem dos comandos

```bash
$N render.mjs <nn> --at=1                  # grava videos/<nn-nome>/cues.json
audio/.venv/bin/python audio/synth.py <nn> # audio/<nn-nome>.wav, −14 LUFS / −1,5 dBTP
$N render.mjs <nn>                         # mp4 com o áudio
```

Conferir: `ffmpeg -i out/<nn-nome>.mp4 -af ebur128=peak=true -f null -` → I ≈ −14 LUFS; nível parecido (±3 dB RMS) entre o começo, as etiquetas e o respiro.
