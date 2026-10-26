# Áudio — trilha e efeitos

A referência tem narração em cima de uma trilha corporativa leve e otimista. Sem narração, os efeitos contam a montagem e a trilha fica por baixo.

## Trilha `explainer` (nova, em `audio/synth.py`)

```js
VIDEO = { …, bpm: 104, music: { style: 'explainer', key: 'D', gain: -5 } }
cue('m:main', 0); cue('m:stop', VIDEO.dur - .22);
```

- Piano em acordes sincopados (1, "e" do 2, "e" do 3), marimba em colcheias, baixo redondo que decai, bumbo macio no 1 e 3, estalo no 2 e 4, chocalho em semicolcheias. Progressão I–V–vi–IV, tom maior.
- Seções: `m:main` (cheio), `m:break` (só piano e marimba), `m:stop` (acorde final de piano com cauda + glock).
- `gain: -5` deixa a trilha uns 4–6 dB abaixo dos efeitos. bpm 96–112 funciona; acima disso fica apressado para o estilo.

## Efeitos por evento

| evento | cue | nota |
|---|---|---|
| peça sobe (planeta, lixeira, faixa) | `paper` | automático em `CE.sobe`, só na primeira de um grupo (`som:false` nas outras) |
| pessoa cresce | `swoosh` −8 dB | automático em `CE.cresce` |
| objeto pipoca | `pop` com `f` subindo (480 → 920) | automático; alterne −6/−8 dB |
| peça miúda (lacre) | `tick` −10 dB | um sim, um não |
| letreiro pousa | `paper` −6 dB | só no letreiro de cima |
| lata cai e bate | `lata` (novo) | automático em `CE.cai`, no impacto |
| fogo/brasa acende | `fogo` (novo) | sopro grave + estalos |
| pan lateral | `whoosh_in` −5 dB | automático em `CE.pan` |
| grade se traça | `marker` −8 dB | automático em `CE.traca` |
| objeto-herói chega | `chime` (m 86, −6 dB) | 0,05 s depois do impacto |

- Dois sons iguais a menos de 60 ms viram "flam": os intervalos de 0,055 s do anel funcionam porque o `pop` muda de tom a cada um.
- Para um som que não existe, escreva `def fx_nome(...)` (numpy, mono, 48 kHz) e registre em `SFX`.

## Ordem

```bash
$N render.mjs <nn> --at=1                  # grava videos/<nn>/cues.json
audio/.venv/bin/python audio/synth.py <nn>  # trilha + efeitos, −14 LUFS / −1,5 dBTP
$N render.mjs <nn>                         # mp4 com áudio
```

Mudou tempo de qualquer peça? Repita os três passos (o `cues.json` sai do preview).

Confira a forma de onda (`ffmpeg -i out/x.mp4 -filter_complex showwavespic=s=1200x200 -frames:v 1 previews/onda.png`): blocos de nível constante que cortam seco indicam instrumento sustentado sem decaimento (foi o caso do baixo, corrigido com `* np.exp(-t/.28)`).
