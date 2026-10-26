# Áudio: trilha e efeitos

A referência é muda. O som do estilo foi desenhado como **escrivaninha**: o lápis em cada palavra, o feltro do marca-texto arrastando, um sopro no chicote — e uma trilha leve por baixo. Todo o som é sintetizado por `audio/synth.py` (sem samples) a partir dos `cue()` da página.

## Trilha

```js
VIDEO = { …, bpm: 104, music: { style: 'feira', key: 'G', gain: -6 } }
cue('m:intro', 0);              // triângulo + viola (sem zabumba): a abertura
cue('m:main', T.escreve);       // entra a zabumba quando a escrita começa
cue('m:break', fim + .1);       // respiro: volta a ficar ralo
cue('m:main', T.vermelho);      // o bloco vermelho traz a zabumba de volta
cue('m:stop', VIDEO.dur - .25); // corta e deixa um acorde dedilhado soar
```

- `feira` (nova nesta skill): baião leve em 2/4 — zabumba seca (couro grave + "bacalhau"), triângulo em semicolcheias (aberto no contratempo) e viola em Karplus-Strong no modo mixolídio. Combina com temas brasileiros/nordestinos; use `gain` −6 para ela ficar **abaixo** do lápis.
- Tema sem cara de feira: `ambient_major` (pads e arpejo vítreo) com `m:break` em 0 e `m:build` na escrita. Evite `launch`/`thriller`: bumbo e drops brigam com a calma editorial.

## Efeitos (onde caem)

| evento | efeito | ganho | quem marca |
|---|---|---|---|
| cada palavra | `lapis` (tique seco de grafite) | 0 ± 1,6 dB, pan ±0,16 | `GR.escrever` (automático) |
| grifo do rótulo | `grifo` (feltro arrastando, `d` = duração) | −2 dB | `GR.marca` (automático) |
| grifo do verso | `grifo` | −4 dB | `GR.marca` (automático) |
| chicote | `whoosh_in` | −2 dB | página: `cue('whoosh_in', T.chicote[0] + .22, {gain:-2})` |
| fim do chicote | `paper` | −6 dB | página: `cue('paper', T.chicote[1] - .05, {gain:-6})` |
| bloco vermelho | `grifo` + `hit_soft` | 0 / −13 dB | `GR.destaque` (automático) + página |

- `lapis` e `grifo` são novos no `synth.py` (`fx_lapis`, `fx_grifo`). A variação de ganho e pan entre palavras vem de `GR.escrever` e evita a "metralhadora" de tiques iguais.
- O `hit_soft` sob o vermelho é um baque grave bem baixo: dá peso ao fecho sem virar "impacto".

## Ordem dos comandos

```bash
$N render.mjs <nn> --at=1                  # grava videos/<nn-nome>/cues.json
audio/.venv/bin/python audio/synth.py <nn> # audio/<nn-nome>.wav, −14 LUFS / −1,5 dBTP
$N render.mjs <nn>                         # mp4 com o áudio
```

Conferir: `ffmpeg -i out/<nn-nome>.mp4 -af ebur128 -f null -` → I ≈ −14 LUFS. Se a zabumba dominar (graves fortes num espectrograma, `showspectrumpic`) e o lápis sumir, baixe os ganhos da zabumba em `st_feira` (hoje 0,28/0,18) ou o `gain` da trilha.
