# Movimento — roteiro-tipo, tempos e eases

A referência tem 23 s num único plano. Comprimida para 8 s (fator ≈ 0,35), mantém a ordem e a proporção abaixo. Para 6 s, multiplique os tempos por 0,75; para 10–15 s, alongue os respiros (fases 1, 6 e 13), não as entradas.

## Roteiro-tipo (tabela `T` do exemplo, 8 s a 30 qps)

| fase | t (s) | o que acontece | como |
|---|---|---|---|
| 1 | 0,00–1,00 | continente escuro sobre papel quadriculado | empurrão lento (`sine.inOut`, z ×1,2) + sub-boom |
| 2 | 0,85 | país acende verde | `MD.pisca(t, .85, .42)` + zumbido `flicker` |
| 3 | 1,00–1,75 | **mergulho** até o país inteiro | câmera `power2.inOut`, z ×2,8 (zoom em log) |
| 3b | 1,20 | bordas brancas dos estados | `MD.pisca(t, 1.2, .4)` durante o mergulho |
| 4 | 1,50–2,10 | etiquetas dos estados + cidades | cascata a cada 0,042 s, cada uma pisca .3 s |
| 5 | 2,12 | 1ª mancha (origem) + chamada com ano | mancha pisca .36 s; linha desenha .3 s; rótulo decodifica |
| 6 | 2,45–3,05 | manchas se espalham (origem → destino) | uma a cada ~0,08 s, cada uma pisca e cresce .75 → 1 |
| 7 | 3,15–3,65 | periféricas apagam piscando, núcleo cresce ×1,45 e se funde; **2º mergulho** | `MD.apaga` .3 s; manchas-ponte surgem; câmera `power2.inOut` |
| 8 | 3,75 | triângulo com a palavra-chave | pisca .35 s + escala 1,12 → 1 (`power3.out`) |
| 9 | 4,10–4,60 | chamada 1 (onde/quando) | linha .3 s `power2.out`, decodifica a partir de +0,21 s |
| 10 | 4,85 | retrato P&B em círculo, ao lado do triângulo | pop `back.out(2.2)` .32 s + pisca |
| 11 | 5,45–5,95 | retrato voa para dentro do triângulo; círculo tracejado entra | retrato `power3.inOut` .5 s até o miolo; círculo ×1,35 → 1 girando −28° → 0° em .6 s (`power3.out`), depois gira 2,5°/s |
| 12 | 6,00–6,50 | chamada 2 (hoje/consequência), fora do círculo | igual à chamada 1 |
| 13 | 6,50–8,00 | respiro: empurrão final lento | câmera `sine.out` z ×1,13; créditos sobem a opacidade |

## Medidas da referência

- **Piscar (acender):** padrão liga/desliga irregular a 30 qps por 0,3–0,45 s; o 1º quadro é sempre "ligado"; quadros intermediários alternam 1 / 0,35 / 0. A probabilidade de "ligado" sobe ao longo da janela (`0,3 + 0,6·u`). Nunca use fade puro.
- **Apagar:** 0,3 s, decaindo com 2–3 tremidas (`MD.apaga`).
- **Mergulhos:** 0,5–0,75 s, `power2.inOut`, zoom interpolado em log (`MD.camera` faz isso). Pan e zoom juntos.
- **Câmera viva:** entre os mergulhos há sempre um empurrão/deriva lenta (`sine.inOut`), nunca parada.
- **Linha de chamada:** desenha do alvo para fora em 0,3 s (`power2.out`), com cotovelo; espessura 5 px, brilho branco.
- **Decodificar:** cada linha nasce como barra branca borrada que se estica (0,16 s) e some (0,22 s); as letras chegam espalhadas em 0,24 s, cada uma de `blur(9px)` → nítida em 0,22 s, piscando nos 2 primeiros quadros.
- **Círculo tracejado:** 26 traços (62% cheio), 10 px, entra ×1,35 e encolhe girando.
- **Retrato:** pop com overshoot (`back.out(2.2)`), depois encolhe ~0,5× e entra no triângulo; o miolo do triângulo assume (troca invisível).

## Ritmo

- Um evento novo a cada ~0,4–0,6 s na versão curta; nada sai de cena, exceto as manchas periféricas e as etiquetas que conflitam com um rótulo novo (`ate`).
- Etiquetas e cidades escurecem para 50–60% depois do 2º mergulho (`dim`), para o vermelho e os rótulos brancos mandarem.
- O final respira 1,5 s com tudo montado.

## Câmera do exemplo (lon, lat, z = px por grau)

```js
const cam = MD.camera([
  { t: 0,    lon: -59,    lat: -17,   z: 16 },
  { t: 1.0,  lon: -57,    lat: -15.5, z: 19, ease: 'sine.inOut' },   // empurrão lento
  { t: 1.75, lon: -47.4,  lat: -12.6, z: 53, ease: 'power2.inOut' }, // mergulho no país
  { t: 3.15, lon: -47.2,  lat: -14.0, z: 56, ease: 'sine.inOut' },   // deriva acompanhando o espalhar
  { t: 3.65, lon: -44.75, lat: -20.4, z: 86, ease: 'power2.inOut' }, // mergulho no núcleo
  { t: 8,    lon: -44.7,  lat: -20.35, z: 97, ease: 'sine.out' },    // respiro
]);
```

Para outro país: z do país inteiro ≈ `1080 / (largura_em_graus · cos(lat0) · 1,05)`; z final ≈ `1080 · 0,45 / (largura_da_região_em_graus · cos(lat0))`.
