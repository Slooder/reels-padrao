# Movimento — tempos, eases e ritmo

Tudo foi medido quadro a quadro na referência (30 qps) e está pronto em `CE`.

## Stop-motion de 12 qps

A referência segura cada pose 2–3 quadros. `CE.passos(ease, d)` devolve um ease que quantiza o progresso em `round(d·12)` degraus: a curva continua (`back.out`, `power2.out`…), mas só muda a cada 1/12 s. Todos os movimentos de entrada usam isso. Rotações contínuas usam `CE.q(t)` (tempo quantizado) dentro do `onTick`.

## Entradas medidas

| movimento | referência | `CE` |
|---|---|---|
| sobe de baixo | planeta: 0,35 s, passa um pouco do ponto e volta | `CE.sobe(el, t, {d:.4, dist:1150, ease:'back.out(1.25)'})` |
| cresce do chão | pessoa: de um ponto a tamanho cheio em ~0,7 s, ancorada nos pés, opaca desde o primeiro degrau | `CE.cresce(el, t, {d:.62})` + `origem` nos pés (`'13% 97%'`) |
| pipoca em anel | aparelhos: um a cada ~2 quadros, girando em volta | `CE.pipoca(el, t, {d:.22, r0, r})`, intervalo 0,055 s |
| letreiro pousa | logo: entra ~2× maior e encolhe em 3 quadros | `CE.pousa(el, t, {d:.2, s0:2.2})` |
| cai e quica | (latas na lixeira) | `CE.cai(el, t, {d:.34, dist:-760, quique:18})` → devolve o impacto |
| amassa | (lixeira recebe) | `CE.amassa(el, impacto, {s:.93})` |
| pan lateral | 0,5 s, ease in-out, liso; a cena nova entra pela direita | `CE.pan(sai, entra, t, {d:.46})` |
| grade se traça | linhas surgem em sequência | `CE.traca(svg, t, {d:.3, s:.01})` |

## Roteiro-tipo (o do exemplo, 7,6 s)

| cena | t (s) | o que acontece |
|---|---|---|
| 1 planeta | 0,00–1,50 | planeta sobe (0,06); letreiro pousa (0,30/0,42); 12 latas pipocam (0,56 → 1,17) e 6 lacres (0,62 → 1,12); anel gira |
| 2 lixeiras | 1,50–2,78 | **corte seco**; pinheiros e lixeiras sobem (1,50–1,90); letreiro (1,64/1,76); 3 latas caem (1,98 / 2,14 / 2,30) |
| pan | 2,78–3,24 | **pan lateral**: lixeiras saem pela esquerda, semicírculo entra pela direita |
| 3 catador | 2,78–4,45 | catador cresce dos pés (3,28–3,90); letreiro (3,28/3,40); 4 latas pipocam no carrinho (3,92 → 4,13) |
| 4 fundição | 4,45–5,85 | **corte seco**; grade se traça (4,47); foto sobe (4,51); brasa acende (4,89) e tremula; fardo cresce (5,07); 2 latas amassadas (5,45/5,53) |
| 5 volta | 5,85–7,60 | **corte seco**; cidade sobe (5,88); sol pipoca (6,07); lata nova cai (6,35 → 6,71); anel e manchinhas pipocam; créditos (7,05) |

Proporções a manter quando mudar a duração:

- cada cena tem **0,3–0,5 s de respiro** montada antes de sair (na referência, segundos);
- o letreiro entra 0,1–0,15 s depois do corte, nunca junto com a primeira peça;
- a primeira peça da cena entra em até 0,1 s depois do corte (não deixe papel vazio);
- 1 pan para cada 3–4 cortes secos; o pan liga duas cenas do mesmo "lugar".

## Ritmo

- Referência: planos longos (4–10 s) que se enchem de peças; a narração dita o tempo.
- Em reels de 6–8 s sem narração, comprima para **1,3–1,8 s por cena**, 4–6 cenas.
- Última cena mais longa (≈ 1,7 s) e terminando parada: ninguém sai, a música fecha com acorde.

## Detalhes que dão vida

- Papel que ferve (automático em `CE.papel`).
- Rotação lenta em degraus: anel de objetos 4°/s, raios do sol 9°/s, círculo tracejado 6°/s.
- Acento que tremula a 12 qps (brasa: escala .92–1.08, opacidade .78–1) com `K.rng(Math.floor(t*12))`.
- Objetos pipocando com rotação inicial 25° a mais que a final.
