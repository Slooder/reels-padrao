# Som: trilha, efeitos e narração

Todo o áudio é sintetizado (numpy e scipy, sem samples) por `audio/synth.py`, a partir das marcações `cue()` feitas na página. O render grava as marcações em `videos/<nome>/cues.json`, com a duração, o bpm e o objeto `music`.

```bash
node render.mjs <nome> --preview=6               # (re)escreve cues.json
audio/.venv/bin/python audio/synth.py <nome>     # → audio/<nome>.wav, masterizado em −14 LUFS / −1,5 dBTP
node render.mjs <nome>                           # → out/<nome>.mp4 com o áudio junto
```

Sempre que mexer em tempos na página, refaça os três passos nessa ordem.

## Trilha

Ela é definida no `VIDEO` da página:

```js
VIDEO = { w: 1080, h: 1920, fps: 60, dur: 5, bpm: 96, music: { style: 'ambient_major', key: 'G', gain: -2 } }
```

- **Estilos:**
  - `ambient_major`: pads claros e arpejo vítreo. É o padrão para natureza e curiosidades.
  - `ambient`: menor, mais misterioso.
  - `launch` / `launch_bright`: pulso eletrônico, para listas rápidas e ranking.
  - `thriller`: tenso, para "o animal mais perigoso…".
- **Seções:** são marcadas por cues `m:*`:
  - `cue('m:intro', 0)` e `cue('m:main', .05)` fazem a trilha já começar cheia;
  - `cue('m:drop', t)` traz o bumbo (útil na virada de uma prancha);
  - `cue('m:break', t)` esvazia;
  - `cue('m:stop', t)` encerra com um acorde longo. Ponha uns 0,3 s antes do fim.
- **Volume:** `gain` em dB ajusta a trilha inteira, que é normalizada antes. Em colagem, a trilha fica discreta e quem conta a história são os efeitos de papel e marcador.

## Efeitos usados na colagem

Formato: `cue(tipo, t, { gain, pan, off })`.

- `gain`: dB relativos ao nível padrão do efeito.
- `pan`: de −1 a 1.
- `off`: deslocamento em s.

| tipo | onde |
|---|---|
| `paper` | cada slap, em `at + .04`; escrita de título |
| `swoosh` | papel rasgado descendo e peças grandes deslizando (`gain:-6`) |
| `hit_soft` | chegada do herói (`gain:-6`): dá peso sem virar "trailer" |
| `marker` | círculo, anotação à mão e seta (um por traço) |
| `bird` | ambiência de mata, 2–3 vezes com `gain` caindo (−9, −11, −13) |
| `whoosh_in` | transição de prancha (chicote) |
| `pop` | etiqueta ou ícone pequeno (`{ f: 700 }` muda o tom) |
| `scratch` | risco de caneta mais longo |
| `shutter` | foto "batida" (polaroide entrando) |
| `tick` | contador ou números trocando |

Outros disponíveis: `whoosh_out`, `whoosh_slow`, `riser`, `impact`, `hit_low`, `boom`, `sub_drop`, `click`, `ui_blip`, `chime`, `ding`, `sparkle`, `coin`, `key`, `type`, `carriage`, `thread`, `snap`, `tom`, `taiko`, `heart`, `bubble`, `zap`, `glitch`, `cut`, `reverse`, `tape_stop`, `braam`, `credit_swell`.

Para um som novo (latido estilizado, por exemplo), escreva uma função `fx_*` em `synth.py` que devolva um array mono em 48 kHz e registre em `SFX = {'nome': (lambda p: fx_nome(), pico_dBFS, abre_no_estereo)}`.

Princípios:

- **Sincronia:** o som cai **no quadro** do movimento.
- **Ambiência:** os sons de ambiente ficam bem abaixo dos sons de ação.
- **Intervalo mínimo:** nunca dois efeitos iguais a menos de 60 ms um do outro (vira um "flam" estranho).

## Narração (opcional, para vídeos explicativos mais longos)

`audio/narrate.py` usa a voz do sistema do macOS (`say`, voz Luciana, pt-BR).

1. Crie `videos/<nome>/narration.src.json`:

```json
{"voice": "Luciana", "rate": 180, "start": 0.5, "segments": [
 {"id": "titulo", "say": "O mico-leão-dourado só existe no Brasil.", "gap": 0},
 {"id": "mapa", "say": "E só num pedaço da Mata Atlântica do Rio.", "gap": 0.4}
]}
```

2. Rode `audio/.venv/bin/python audio/narrate.py <nome>`. Ele gera os wavs em `audio/narr/<nome>/` e escreve `videos/<nome>/narration.json` com `start` e `dur` de cada fala.
3. Na página, a linha do tempo segue a fala:

```js
window.SETUP = async () => {
  const N = await (await fetch('narration.json')).json(), S = Object.fromEntries(N.segments.map(s => [s.id, s]));
  VIDEO.dur = N.end + 1.2;                   // o render lê VIDEO.dur depois do SETUP
  slap('#map', S.mapa.start); /* … */
};
```

4. O `synth.py` encontra o `narration.json` sozinho. Ele aplica uma cadeia de voz (passa-altas, presença e saturação leve), abaixa a trilha −11 dB sob a fala e soma tudo.

Para escrever "Cria Bê Érre" e similares, use a grafia fonética no campo `say` e o texto certo no campo `text`.
