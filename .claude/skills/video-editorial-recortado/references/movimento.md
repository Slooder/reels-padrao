# Movimento: tempos, eases e ritmo

## Estrutura (plano único que se preenche)

A referência não tem nenhum corte: um quadro só que vai ganhando camadas. Proporções medidas (9,6 s) e como ficam em 6,8 s:

| fase | referência | % | exemplo (6,8 s) |
|---|---|---|---|
| título no lugar + título sobe | 0,0–1,7 | 18% | 0,00–1,57 |
| subtítulo palavra a palavra | 1,7–3,6 | 20% | 1,30–2,22 |
| pausa curta | 3,6–4,6 | 10% | 2,22–2,62 |
| etiquetas (4–5, sobrepostas) | 4,6–7,2 | 27% | 2,62–4,50 |
| respiro com tudo montado | 7,2–9,6 | 25% | 4,50–6,80 |

Tabela `T` do exemplo:

```js
const T = { tit: 0, traco: .26, sobe: .95, sub: 1.30, L: [2.62, 3.24, 3.58, 3.90, 4.22], cred: 4.75 };
// dur 6.8 s, 30 qps
```

Para outra duração, escale tudo pela mesma razão, mas mantenha as durações de cada entrada (abaixo): o que muda é o espaço entre elas.

## Entradas (medidas quadro a quadro)

### Palavra que sobe (título e subtítulo) — `ED.sobe`
- A palavra **aparece inteira** (sem fade) ~0,6 em abaixo da linha e sobe até a linha em **0,38–0,40 s, `power3.out`**.
- Uma palavra a cada **0,12 s** no título e **0,21 s** no subtítulo (na referência, ~0,5 s: lá o vídeo é mais longo).
- O texto inteiro já está diagramado (centralizado); cada palavra nasce no seu lugar final, não empurra as outras.

### Sublinhado de pincel — `ED.sublinhado`
- Começa ~0,25 s depois da primeira palavra do título; desenha da esquerda para a direita em **0,55 s, `power2.out`** (revelação por máscara, o traço já tem a forma final).

### Título sobe para abrir espaço
- Depois de completo, o bloco do título (com o sublinhado) sobe **96 px** em **0,62 s, `power3.inOut`**. Só então o subtítulo começa.

### Etiqueta coral — `ED.etiqueta`
Sequência medida a 30 qps na referência (rótulo "Uh huh, please tell me more"):

1. **t0:** um traço vermelho fino (3 px, altura da faixa) aparece seco e fica ~2 quadros.
2. **t0+0,05:** a faixa cresce para a direita com `power2.out` em `0,22 + 0,016 × nº de caracteres` s (máx. 0,75 s) até o tamanho final do texto.
3. **t0+0,07 →** as palavras aparecem **secas, em preto**, em **ordem aleatória**, uma a cada **0,066 s** (2 quadros), deslocadas meia linha acima ou abaixo (alternando: ±0,9–1,2 × a altura da faixa) e até ±0,45 em na horizontal.
4. **Logo depois que mais da metade apareceu,** elas pulam **em ordem de leitura**, uma a cada **0,10 s** (3 quadros), para o lugar final dentro da faixa — corte seco, sem tween — e ficam **brancas**. A faixa nunca é menor que o texto já encaixado.
5. Duração total: ~0,25 s (1 palavra) a ~0,9 s (5–6 palavras).

Entre etiquetas: a próxima começa **0,3–0,6 s** depois da anterior, ainda durante a montagem dela. A longa vai primeiro.

### Retícula — `ED.reticula`
- Aparece nos primeiros 0,5 s, da esquerda para a direita (ou ao contrário), em **7 degraus** em 0,32 s (stop-motion seco).

## Câmera

- Quase parada. Empurrão lento de toda a duração, `sine.inOut`, origem embaixo no centro:
  - camada de trás `1 → 1,022` e sobe 6 px;
  - camada da frente `1 → 1,04`.
- Isso dá um parallax quase imperceptível que mantém o quadro vivo no respiro. Texto e etiquetas não acompanham a câmera.

## Saída

Não há saída: o vídeo termina com tudo montado e parado ~2 s (respiro). Para loop, deixe o último quadro idêntico ao estado final.
