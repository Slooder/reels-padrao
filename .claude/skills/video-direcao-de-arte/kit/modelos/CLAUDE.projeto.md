## Direção de arte (DA) — regra do projeto "{{NOME}}"

Este projeto tem **uma única fonte de verdade visual: `da/da.json`** (preset de partida: {{PRESET}}).
Resumo legível, sempre atualizado pela compilação: @da/DA.md

_Bloco gerado por `da.py init`. Não edite entre os delimitadores: rode o init de novo para atualizar._

### Regra de submissão (Passo 0 de toda tarefa visual) — vale para QUALQUER sessão, skill ou script, inclusive os antigos

1. **Sem DA não se renderiza nada.** Antes de criar ou alterar qualquer peça visual (animação, GC, tarja, legenda, moldura, b-roll tratado, corte vertical, thumbnail), localize a DA:
   `{{KIT}}/bin/da achar` — sobe as pastas até achar `da/da.json`. Código de saída 2 = não existe DA: **pare** e crie uma com a skill `{{SKILL}}`. Não improvise um visual "provisório".
2. **Ninguém decide visual por conta própria.** Cor, fonte, tamanho de texto, curva e duração de animação, transição, grade de cor, grão, moldura, estilo e posição de legenda, margens seguras, loudness: tudo vem dos tokens da DA. Se o token não existe, o caminho é propor o token novo no `da.json` — nunca improvisar na peça.
3. **Proibido valor literal em peça.** Nada de cor escrita à mão (`#FFC700`, `rgb()`, `hsl()`, `red`, tupla `(255, 199, 0)` em Python, `color=black` em filtro ffmpeg) nem fonte literal (`font-family`, `ImageFont.truetype("…")`) em HTML, CSS, JS de cena, JSON de storyboard ou script Python que desenha. Use:
   - CSS: `var(--da-cor-primaria)`, `var(--da-fonte-titulo)`, `var(--da-escala-h1)`, classes `.da-titulo`, `.da-corpo`… Cor com transparência tem uma forma só: `rgba(var(--da-cor-fundo-rgb), 0.86)` (com vírgula; a forma com barra computa transparente e é reprovada).
   - JS de cena: `ctx.cor("primaria")`, `ctx.alfa("fundo", 0.86)`, `ctx.tam("h1")`, `ctx.dur("media")`, `ctx.area_livre()` (a zona segura menos a faixa da legenda); fora do motor, `window.DA` (de `da/build/da.js`).
   - Python: `sys.path.insert(0, os.environ["CRIABR_SKILLS"] + "/video-direcao-de-arte/kit"); import da; d = da.carregar()` → `d.cor("primaria")`, `d.rgb("fundo")`, `d.rgba("texto", 0.6)`, `d.fonte_pil("legenda", px)`, `d.px(fracao, "vertical")`, `d.margens("vertical")`, `d.area_livre("vertical")`, `d.grade("horizontal")`.
   - Shell: `{{KIT}}/bin/da token legenda.cor`.
   Exceção legítima (foto, logo de terceiros, captura de tela): atributo `data-da-livre="motivo"` no elemento (vale para o lint e para o auditor, e fica listado no carimbo, que a conferência final mostra) ou comentário `da-livre` na linha (`# da-livre` em Python; vale só para o lint). `<img>`, `<video>`, `<canvas>`, `url()`, controles nativos (`<input>`, `<progress>`, `<button>`…) e emoji sem o atributo são reprovados pelo auditor. O atributo libera cor, não movimento: GIF animado, `<animate>` de SVG e vídeo tocando reprovam mesmo com ele.
4. **Toda peça leva carimbo.** Cada saída tem um sidecar `<saida>.da.json` dizendo com qual DA foi feita (`da.py carimbar`; o motor, `da.py grade` e as composições de `video.py` carimbam sozinhos, registrando as peças que entraram). Arquivo de trabalho não é peça: dê a ele (ou à pasta dele) um nome começado por `_` — `legendas/_png/`, `render/_base.mp4` — e ele fica fora da conferência. Peça sem carimbo, com DA diferente da atual, regravada por fora ou com auditoria pulada é reprovada por `da.py conferir-carimbo` e pela conferência final — e carimbar de novo não limpa uma auditoria pulada: só renderizar de novo.
5. **Mudou o gosto? Mude a DA, não a peça.** Edite `da/da.json` → `da.py validar` → `da.py compilar` → renderize de novo o que ficou com carimbo velho. Depois de aprovada, qualquer edição pede `da.py revisar` e uma nova aprovação do usuário.
   **Nada em cima da legenda:** a legenda fica onde `legenda.posicao` manda; GC, crédito, selo, gráfico e título ficam na área livre (`d.area_livre(formato)` / `ctx.area_livre()`) — no vertical e no quadrado ela já desconta a faixa da legenda; no horizontal a reserva vem desligada (o GC fica na base, na faixa da legenda): se o vídeo horizontal leva legenda queimada, ponha `"horizontal"` em `legenda.reservar_em` da DA (ou `"reservar_legenda": true` numa cena só) e, antes de queimar, confira `d.legenda_reservada(formato)`.
6. **Pedido que contraria a DA** ("põe esse título em vermelho"): não aplique direto na peça. Diga que foge da DA e ofereça os dois caminhos — usar o token mais próximo ou alterar a DA (nova revisão).
7. **Nada é publicado sem a conferência final.** Com o vídeo e os cortes prontos: `{{KIT}}/bin/da conferencia` — DA aprovada, lint, carimbos, loudness e limites de plataforma de `render/final.mp4` e `cortes/*.mp4`, mais a ficha de fatos e os créditos de b-roll quando o projeto os tem. Ela grava `qa/relatorio.json` e `qa/relatorio.md`; código 1 = reprovado. Conserte na origem o que o relatório apontar (cada erro diz como) e rode de novo: não edite o relatório, não carimbe à mão para passar. Não existe skill de QA: o comando é este.
8. **Uma tarefa pesada por vez** (máquina de 8 GB): ffmpeg, Chromium, whisper e swift sempre por `python3 {{KIT}}/trava.py -- <comando>` (em Python: `trava.rodar([...])`; o motor, `da.py grade` e `video.executar` já entram na trava sozinhos). Para cancelar, `kill` no comando: ele mata os filhos antes de soltar a trava. Trava presa (quem espera vê `SEM PROGRESSO há N s`): `python3 {{KIT}}/trava.py --estado` e, se o dono está parado há mais de 2 min, `python3 {{KIT}}/trava.py --liberar` (só mata dono sem progresso). Nunca apague o arquivo da trava.

### Comandos do dia a dia

A chamada é sempre esta, por extenso (funciona em zsh, bash e sh; não a guarde em variável — `DA="python3 …"; $DA …` falha em zsh):

```bash
{{KIT}}/bin/da achar                 # onde está a DA deste projeto (código 2 = não há)
{{KIT}}/bin/da mostrar               # resumo no terminal
{{KIT}}/bin/da validar               # erros e avisos (contraste, arquivos, faixas, legenda fora da zona segura)
{{KIT}}/bin/da compilar              # gera da/build/ (da.css, da.js, da.resolvida.json, grade.json, da.lock) e da/DA.md
{{KIT}}/bin/da token cor.paleta.primaria
{{KIT}}/bin/da extrair da/referencias bruto/entrevista.mp4         # paleta, cores de acento, contraste, temperatura e grão das referências
{{KIT}}/bin/da lint animacoes/       # reprova cor/fonte literal em peças (HTML, CSS, JS, JSON, SVG e Python); a conferência final usa --estrito
{{KIT}}/bin/da conferir-carimbo      # reprova peça sem carimbo ou feita com DA velha
{{KIT}}/bin/da grade --entrada broll/bruto/clipe.mp4 --saida broll/tratado/clipe.mp4
{{KIT}}/bin/da prancha               # da/prancha.png e prancha_vertical.png: a prancha que o usuário aprova
{{KIT}}/bin/da teste-movimento       # da/teste_movimento.mp4: título → GC (+ legenda, onde a DA reserva a faixa dela) → barras, na duração que a DA pede (5–8 s)
{{KIT}}/bin/da rotas listar          # DAs candidatas em da/rotas/ (criar, comparar lado a lado, adotar)
{{KIT}}/bin/da render --cena titulo --saida animacoes/abertura.mp4 --dur 4 --params '{"titulo": "…"}'   # motor HTML → vídeo/PNG
{{KIT}}/bin/da aprovar --estrito     # só quando o usuário aprovar o visual; recusa se prancha ou teste de movimento não estiverem em dia
{{KIT}}/bin/da revisar               # abre nova revisão antes de mexer numa DA aprovada
{{KIT}}/bin/da conferencia           # conferência final antes de publicar → qa/relatorio.json e qa/relatorio.md (código 1 = reprovado)
{{KIT}}/bin/da conferencia --corte K01    # só um corte; --previa enquanto a DA não está aprovada (grava qa/previa.json, que não libera publicação)
```

No resto deste bloco, "`da.py <subcomando>`" é o nome do comando; a linha que se digita é `{{KIT}}/bin/da <subcomando>`.
Quem lê a DA por `da.carregar()` recompila sozinho quando `da/build/` está velho.

### Motor de render (peças HTML)

Toda peça HTML passa por `{{KIT}}/motor/render.mjs` (ou `{{KIT}}/bin/da render …`): ele acha a DA, injeta `da.css`/`da.js`,
**audita os estilos computados** da página inteira em dezenas de instantes da peça — inclusive o que ainda está invisível, pseudo-elementos e shadow DOM (cor e fonte fora da DA, transition/animation CSS, imagem/canvas sem `data-da-livre`, filtro ou blend que muda cor, declaração de cor que o navegador descartaria, `requestAnimationFrame`/`setTimeout`/`Math.random`/`Date.now`/`crypto`/`postMessage` → reprova antes de renderizar), confere que `seek(t)` é pura e que nada se mexe sem `seek`,
gera PNG (`--quadro T`) ou vídeo (h264 opaco; prores4444/vp9alfa com alfa) e grava o carimbo. Cenas são módulos ES
(`export const meta`, `build(palco, params, ctx)`, `seek(t)` PURA em t: aplica o estado completo de cada elemento a cada chamada, aleatoriedade só por `ctx.rng(semente)`) que só usam tokens via `ctx` — modelos em
`{{KIT}}/motor/cenas/` (titulo, gc, moldura, citacao, barras). No vertical, passe `"plataforma": "uniao"|"reels"|"tiktok"|"shorts"` nos params.
`--sem-auditoria` existe, mas fica no carimbo e reprova na conferência final.
Texto em PIL (legendas sempre dentro da zona segura, thumbnails): `{{KIT}}/texto.py`; ffmpeg (tratamento, recorte e encaixe, overlay com alfa, N legendas numa passada, transições da DA, quadros → vídeo, loudness): `{{KIT}}/video.py`.
Thumbnail: não há skill dedicada — é feita direto pelo kit, com os tokens `thumbnail.*` da DA, pela receita do §17.1 da referência abaixo; a peça vai para `thumbs/`, carimbada.
Referência completa da API para quem escreve skills: `"$CRIABR_SKILLS"/{{SKILL}}/references/kit-api.md` (conferência final e contrato do relatório no §18).

### Mapa das pastas

| pasta | o que mora ali |
|---|---|
| `da/` | `da.json` (a fonte de verdade), `DA.md` (leitura), `fontes/`, `luts/`, `texturas/`, `logos/`, `referencias/`, `build/` (gerado), `prancha.png` (gerado) |
| `pesquisa/` | ficha de fatos (`fatos.json`), fontes, links e anotações da apuração |
| `roteiro/` | ganchos, roteiro e versões; `roteiro.md` (roteiro limpo), `pauta.json` (pedidos de mídia) e `storyboard.json` (roteiro → cenas) |
| `bruto/` | gravações originais (nunca alteradas) |
| `transcricao/` | palavras e segmentos com tempo |
| `broll/` | material de apoio: `broll/bruto/` (baixado, nunca alterado) e `broll/tratado/` (com o tratamento da DA, carimbado); `licencas.json` (registro de licenças) e `creditos.md` |
| `animacoes/` | cenas explicativas, cenas de mídia e motion graphics (fontes e renders) |
| `legendas/` | cues e overlays de legenda |
| `cortes/` | cortes verticais |
| `thumbs/` | thumbnails e variações (feitas direto pelo kit, carimbadas) |
| `publicacao/` | títulos, descrições, capítulos, arquivos finais por plataforma |
| `qa/` | `relatorio.json` e `relatorio.md` da conferência final (`da.py conferencia`): o portão de publicação |
| `render/` | vídeos montados (carimbados); intermediários com nome começado por `_` |

### Ordem do pipeline

pesquisa (ficha de fatos) → roteiro → **direção de arte** (criar, compilar e aprovar a DA) → pauta de mídia → gravação e transcrição → b-roll e animações → montagem e motion → som → cortes verticais e legendas → thumbnail (direto pelo kit) → **conferência final** (`da.py conferencia`) → publicação

Nada depois de "direção de arte" começa sem `da/da.json` válido; nada vai para publicação sem `qa/relatorio.json` dizendo `"ok": true`, feito com a DA atual e depois do último render.
