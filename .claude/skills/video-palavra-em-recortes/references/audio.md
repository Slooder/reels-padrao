# Áudio — fita, cliques, silêncio e drop

Tudo sintetizado em `audio/synth.py` (sem samples), masterizado a −14 LUFS / −1,5 dBTP.

## O que a referência faz

Espectrograma da abertura: um tom harmônico (várias parciais) **descendo** de ~500 para ~250 Hz durante a montagem, com linhas verticais (cliques) em cada troca; depois **silêncio total** (−60 dB) no preto; depois trap/drill a ~150 bpm (808 grave, palma no 3, chimbal em semicolcheias).

## Efeitos da lib (marcados sozinhos)

| cue | onde | o quê |
|---|---|---|
| `clique` | cada recorte (`var` 0–3 alterna obturador, folha, tecla, estalo) | −16 dB de pico; o último de cada palavra mais alto |
| `fita` | início de cada montagem, `d` = duração, `cortes` = instantes dos recortes, `tom` = semitons | voz de fita: soma de 13 harmônicos com formantes (900 e 2200 Hz), glissando ~520 → 250 Hz, vibrato de 5,5 Hz, re-ataque em cada corte |
| `tapa` | cada peça da colagem | baque grave (95 Hz) + papel |

`RC.frase` sobe o `tom` em 1 semitom por palavra (tensão crescente).

## Marque na página

```js
F.montagens.forEach((m, i) => cue('hit_soft', m.de, { gain: i ? -6 : -3 }));   // pancada a cada palavra
cue('riser', inicioDaUltimaPalavra + .05, { d: 1.15, gain: -4 });              // subida para o silêncio
cue('m:drop', T.drop); cue('m:outro', T.fade[0] - .2); cue('m:stop', VIDEO.dur - .2);
cue('impact', T.drop, { gain: -2 }); cue('sub_drop', T.drop, { gain: -5 });
```

O silêncio vem de graça: a trilha `drill` é zerada antes de `m:drop` e não há cue no preto. Não ponha nada ali — o vazio é a marca.

## Trilha `drill` (`VIDEO.music = {style:'drill', key:'F', gain:1}`)

- Meio-tempo a 150 bpm: 808 com glide (padrões de 2 compassos), bumbo no 1 e na semicolcheia 10, palma+caixa no 3, chimbal em colcheias com semicolcheias extras e rolo em tercinas no fim do 2º compasso, sino escuro (menor) uma nota por batida, pad grave.
- `m:outro` abaixa a trilha até `m:stop`.
- `gain`: +1 dB deixa a trilha presente depois do drop (a fita e os cliques são altos e puxam o loudness da primeira metade).

## Ordem

```bash
$N render.mjs <nn> --at=1                         # grava videos/<nn>/cues.json
audio/.venv/bin/python audio/synth.py <nn>        # audio/<nn>.wav (−14 LUFS)
$N render.mjs <nn>                                # mp4 com áudio
```

Som novo: `def fx_nome(...)` (numpy, mono, 48 kHz) e registre em `SFX = {'nome': (lambda p: fx_nome(), pico_dBFS, abre_no_estereo)}`.
