# Áudio — trilha `documental` e efeitos

Tudo sintetizado em `audio/synth.py` (sem samples), master a −14 LUFS / −1,5 dBTP.

```bash
$N render.mjs <nn> --at=1                         # grava videos/<nn-nome>/cues.json
audio/.venv/bin/python audio/synth.py <nn>        # → audio/<nn-nome>.wav
$N render.mjs <nn>                                # mp4 final com o áudio
```

## Trilha (`VIDEO.music = {style:'documental', key:'D', gain:-2}`, `bpm: 96`)

O que a referência tem: grave dominante (mais de 90% da energia abaixo de 200 Hz), sub-boom no começo, tambores de guerra a partir do primeiro acendimento, e tudo some no fim.

- **drone de cordas graves** (fundamental + quinta) cujo filtro abre em `m:drop`;
- **ostinato de cordas graves em colcheias** (staccato, alternando L/R) de `m:drop` a `m:outro`;
- **taiko** nos tempos 1 e 3, **toms** sincopados, crescendo até `m:outro`;
- **cauda**: cordas agudas em trêmulo baixinho que somem até o fim.

Seções: `cue('m:intro', 0)`, `cue('m:drop', <fim do 1º mergulho>)`, `cue('m:outro', <início do respiro>)`, `cue('m:stop', dur - .2)`.

## Efeitos (o que soa em cada evento)

| evento visual | cue | ganho típico |
|---|---|---|
| início (mapa-múndi) | `boom` em 0,02 | −3 |
| algo acende piscando (país, bordas, mancha, triângulo) | `flicker` com `{d: <duração do piscar>}` — zumbido elétrico que liga/desliga | 0 a −5 |
| mergulho de câmera | `whoosh_slow` (1º) / `whoosh_in` (2º), no início do movimento | −2 / −3 |
| fim do mergulho | `hit_low` ou `taiko` no quadro em que assenta | −2 / −3 |
| etiquetas em cascata | `ui_blip` em 1 de cada 3 | −9 |
| manchas se espalhando | `tom` em 1 de cada 2, `f` descendo (110 → 70) | −5 |
| triângulo | `flicker` + `impact` | −4 |
| linha de chamada | `swoosh` no início da linha | −7 |
| rótulo decodificando | `decode` em t0 + 0,2 (chiado de dados + blip de confirmação) | −3 |
| retrato | `pop` (f 420) + `shutter` | −6 / −8 |
| círculo tracejado | `reverse` .55 s antes + `hit_soft` na entrada | −10 / −4 |

Regras: o som cai **no quadro** do evento; dois sons iguais a menos de 60 ms viram flam (espalhe); a trilha fica por baixo e quem conta a história são os efeitos.

## Sons próprios do estilo (já em `synth.py`)

- `fx_flicker(d)` — dente-de-serra 100 Hz + quadrada 50 Hz + chiado, com portas liga/desliga a 30 qps (sempre liga no 1º quadro) e um clique inicial.
- `fx_decode(d)` — blips quadrados curtos (900–3800 Hz) que vão rareando, terminando num blip senoidal de 2,4 kHz.
- `st_documental(D, bpm, key, C)` — a trilha.

Para outra emoção: tom maior não combina com o estilo; para algo menos bélico, tire os toms sincopados e mantenha drone + ostinato.
