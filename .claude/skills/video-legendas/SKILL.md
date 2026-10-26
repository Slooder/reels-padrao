---
name: video-legendas
description: Queima legenda em vídeo — palavra a palavra (karaokê), uma palavra por vez ou em bloco — para Shorts, Reels, TikTok e trechos de vídeo longo, no estilo que a direção de arte do projeto define (bloco `legenda` do da/da.json) e sempre dentro da zona segura da plataforma; e gera os arquivos .srt e .vtt de frases inteiras para subir como legenda oculta. Parte das palavras cronometradas da transcrição, segmenta em cues por pausa, pontuação e sentido, aplica o glossário do projeto (trocas, censura de nomes, números em algarismo, destaques), confere zona segura e contraste contra o vídeo real e entrega vídeo legendado carimbado ou faixa com alfa para o editor. Use sempre que o usuário disser "legenda esse vídeo", "põe legenda no corte", "legenda palavra por palavra", "legenda estilo TikTok", "legenda karaokê no reels", "queima a legenda", "gera o srt", "arquivo de legenda pro YouTube", "a legenda está fora de sincronia", "a legenda está atrás dos botões", "corrige essa palavra na legenda", "censura o nome na legenda" ou "me dá a legenda com fundo transparente pro Premiere" — e quando outra skill tiver um corte pronto e só faltar a legenda. Difere das irmãs: video-transcricao produz as palavras cronometradas (aqui são insumo); video-animacao-audio faz a tela cheia de áudio com onda e karaokê a partir de um áudio (outro entregável); video-cortes-verticais escolhe os trechos, enquadra e chama esta skill; video-motion-graphics faz GC, selo e lower third; video-direcao-de-arte decide cor, fonte, tamanho, posição e animação da legenda (aqui nada disso é opção) e faz a conferência final do projeto (`da conferencia`); video-publicacao sobe o .srt; gerar-ganchos, gerar-roteiro e melhorar-roteiro escrevem texto antes da gravação.
---

# Legendas: queimada no estilo da DA, dentro da zona segura, e .srt/.vtt

Entra um vídeo e a transcrição palavra a palavra; saem **quatro coisas**: o vídeo legendado (ou a faixa com alfa), `legendas/<nome>.cues.json` (as cues, corrigíveis), `legendas/<nome>.srt` e `legendas/<nome>.vtt` (frases inteiras, para legenda oculta). A aparência não se decide aqui: estilo (`karaoke`, `palavra`, `bloco`), cor, fonte, tamanho, contorno, caixa, posição e animação vêm do bloco `legenda` da direção de arte. O que esta skill decide é **onde cortar o texto e quando cada palavra acende**.

```bash
LEG="$CRIABR_SKILLS"/video-legendas/scripts      # só o caminho na variável (em zsh, comando com opção dentro de variável não roda)
cd "/caminho/do projeto"                         # ou --projeto "/caminho/do projeto"
python3 "$LEG/legendar.py" --help                # python3 = o do Homebrew (python, com Pillow e numpy)
```

## Passo 0 — Direção de arte

1. **Ache a DA**: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da achar --json` a partir da pasta do projeto. Código 2 = não há `da/da.json`: **pare**, diga ao usuário que o projeto não tem direção de arte e chame a skill `video-direcao-de-arte`. Os scripts daqui fazem a mesma checagem e saem com 2; nunca queime legenda com um visual improvisado.
2. **Leia o que a DA manda**: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da token legenda` mostra estilo, tamanho, cores, contorno, caixa, posição, `max_palavras`, `max_linhas`, animação e `reservar_em`. As durações da animação são `movimento.duracoes.micro` (pop) e `.curta` (fade).
3. **Nenhuma cor, fonte ou tamanho é opção de linha de comando.** "Legenda maior", "em amarelo", "mais para baixo", "uma palavra por vez", "sem animação" são mudanças de token: `references/estilo-pela-da.md` diz qual token e o caminho (`da revisar` → editar `da/da.json` → `validar` → prancha → `aprovar`). Pedido pontual ("só neste corte, vermelho") não existe: ou é token, ou não entra.
4. **Toda saída sai carimbada** (`<saida>.da.json`, ferramenta `video-legendas`, com o arquivo de cues e a base como insumos). PNGs de estado e quadros de conferência moram em `legendas/_png/` e somem no fim; a prévia é `legendas/_previa_<nome>.png` (prefixo `_`: intermediário, fora do lint e da conferência final).
5. **Uma tarefa pesada por vez**: o script entra **uma vez** na trava do kit e faz tudo lá dentro (estados, quadros de conferência, ffmpeg). O tempo que ele informa inclui a fila; se ficar parado, `python3 "$CRIABR_SKILLS"/video-direcao-de-arte/kit/trava.py --estado`.

## Fluxo

### 1. Confira os insumos

| precisa existir | dono | se faltar |
|---|---|---|
| `da/da.json` | video-direcao-de-arte | pare (Passo 0) |
| o vídeo que recebe a legenda (corte, render final ou bruto) | video-cortes-verticais / video-montagem / o usuário | volte para a skill dona |
| `transcricao/<nome>.palavras.json` = `[{"a", "b", "w", "p"}]`, tempos do vídeo inteiro | video-transcricao | transcreva antes (passada palavra a palavra) |
| `legendas/glossario.json` (opcional) | esta skill, com o usuário | segue sem glossário |

As palavras têm de ser **deste** vídeo e no relógio dele. Se a legenda vai num trecho, não corte a transcrição: passe `--inicio`/`--fim` e os tempos saem rebaseados.

### 2. Glossário do projeto (uma vez por projeto)

`legendas/glossario.json` corrige o que o whisper erra sempre e o que não pode aparecer:

```json
{"trocas": {"Souza": "Sousa", "talvez da de": "talvez até de"},
 "censura": ["Fulano de Tal"],
 "numeros_em_algarismo": true,
 "destaques": ["atenção", "modelo de linguagem"]}
```

- `trocas`: maiúscula não importa, **acento importa** (`da` não é `dá`). Para palavra comum use 2–3 palavras de contexto; a troca pode ter outro número de palavras. O texto da troca foi escrito por gente: não gera aviso de confiança.
- `censura`: vira `***` (ou `"mascara": "###"`) na tela, no `.srt` e no `.vtt`, e o termo **não fica gravado** nas cues — nem a grafia original quando ele veio de uma `troca`. Não escreva o nome censurado em mensagens, rótulos ou nomes de arquivo.
- `numeros_em_algarismo`: "vinte e três por cento" → `23%`, "dois mil e dezessete" → `2017`. De um a dez fica por extenso (norma de legendagem), salvo em medida (`5%`, `3 milhões`). Fala com muito número **precisa** disso: um numeral por extenso não cabe numa cue de 4 ou 5 palavras (armadilha abaixo).
- `destaques`: a palavra fica em `cor_destaque` depois de dita (karaokê) ou sempre (bloco). No estilo `palavra` não muda nada: toda palavra já aparece nessa cor.

A sincronia é a da **fala**, não a do texto novo: o trecho trocado guarda o início da primeira palavra e o fim da fala da última (`fala_fim`), e a cue fica na tela até a fala acabar — mesmo quando "cento e cinquenta mil" (1,9 s) vira `150.000`. Chave desconhecida é erro (um `troca` digitado errado passaria em branco). O resumo diz o que **não ocorreu** no trecho.

### 3. Prévia antes de queimar

```bash
python3 "$LEG/legendar.py" --video render/final.mp4 --palavras transcricao/final.palavras.json \
  --formato vertical --inicio 62.4 --fim 91.0 --foco 0.31,0.38 --nome K01 --previa
```

Grava as cues e `legendas/_previa_K01.png`: 8 quadros (um por cue amostrada, no meio da palavra do meio) com a legenda no lugar e o retângulo da zona segura. **Abra e olhe reduzido a 360 px de largura** (tela de celular): lê? está sobre o rosto, sobre um GC, sobre legenda que o vídeo já tinha? Leia também os avisos — eles saem iguais no render.

**Dê nome ao trecho** (`--nome K01`, ou o nome da `--saida`). Sem nome, um trecho vira `<vídeo> <início>-<fim>s` (`legendas/final 62.4-91s.cues.json`); pedir para um trecho o nome do vídeo ou o do arquivo de palavras (`--nome final`) é erro: `legendas/final.srt` é a legenda do vídeo **inteiro**, e é esse arquivo que a video-publicacao envia com o vídeo longo.

### 4. Corrija as cues (palavra errada, quebra ruim, nome a esconder)

```bash
python3 "$LEG/cues.py" mostrar legendas/K01.cues.json --avisos          # `/` = quebra de linha · `*` = destaque · (p 0,44) = confiança baixa
python3 "$LEG/cues.py" editar legendas/K01.cues.json --cue 3 --palavra 2 --para "Nakamura"
python3 "$LEG/cues.py" editar legendas/K01.cues.json --cue 5 --texto "a denúncia pesa mais"     # os tempos do que não mudou ficam
python3 "$LEG/cues.py" editar legendas/K01.cues.json --cue 7 --dividir 2                        # também: --juntar · --linhas 2,3 · --t0/--t1 · --destacar 1 · --remover
```

Toda palavra com confiança do whisper abaixo de 0,60 vira aviso `revisar`: **ouça o trecho** antes de aceitar ou trocar. O aviso diz onde ouvir, não o que está errado: no vídeo de teste de 20 s ele apontou `E` (0,48), `galera` (0,44), `Tagiri` (0,58, pedaço de um nome próprio) e `ele` (0,54) — e deixou passar `absorvição` (0,77), grafia que não existe. Leia o texto inteiro uma vez (`mostrar`). Cada `editar` regrava `.cues.json`, `.srt` e `.vtt` e marca o arquivo como editado: daí em diante queime com `--cues` (passo 5). `--linhas` não passa de `legenda.max_linhas` (a legenda sairia da faixa que a DA reserva para ela): divida a cue. Erro que se repete no projeto inteiro vai para o glossário, não para o `editar`.

### 5. Queime

```bash
# corte vertical para as três plataformas (zona `uniao`), a partir do vídeo horizontal
python3 "$LEG/legendar.py" --video render/final.mp4 --palavras transcricao/final.palavras.json \
  --saida cortes/K01.mp4 --formato vertical --plataforma uniao --inicio 62.4 --fim 91.0 --foco 0.31,0.38
# com as cues corrigidas no passo 4 (formato, zona e trecho vêm do arquivo)
python3 "$LEG/legendar.py" --video render/final.mp4 --cues legendas/K01.cues.json --saida cortes/K01.mp4 --foco 0.31,0.38
# trecho de vídeo longo, no próprio formato (horizontal)
python3 "$LEG/legendar.py" --video render/final.mp4 --palavras transcricao/final.palavras.json \
  --saida "legendas/trecho abertura.mp4" --inicio 0 --fim 45
```

| opção | o que faz e por quê |
|---|---|
| `--formato F` | quadro de saída: formato da DA (`vertical`, `horizontal`) ou `LxA`. Sem ela, o tamanho do próprio vídeo. Proporção diferente = recorte pelo kit (âncora `tratamento.recorte.ancora` da DA) |
| `--foco X,Y` | centro do recorte em frações do vídeo de origem. Numa mesa com duas pessoas a âncora padrão cai no meio, entre elas |
| `--enquadramento encaixe` | em vez de recortar, o vídeo inteiro sobre fundo desfocado ou faixas (`tratamento.encaixe` da DA) |
| `--plataforma P` | zona segura: `uniao` (padrão do vertical: cabe nos três apps), `reels`, `tiktok`, `shorts`. Muda a **margem e o centro** do bloco, não a largura dele: o teto é `legenda.posicao.vertical.largura_max` (0,61 = 659 px em 1080 nos cinco presets, nas quatro zonas) |
| `--inicio S --fim S` | trecho, em segundos ou `m:ss`. Cues, `.srt` e `.vtt` saem no relógio do trecho |
| `--tratamento` | aplica o tratamento de cor da DA à base. **Só para material bruto**: o render final já está tratado e ficaria tratado duas vezes |
| `--pontuacao` | `limpa` (padrão: tira ponto e vírgula, mantém `?` e `!`), `manter` (padrão do estilo `bloco`), `nenhuma` |
| `--escala 0.5` | metade do tamanho, para prévias e testes (0,05 a 1; prévia reduzida não é entregável) |
| `--estrito` | sai com 1 se houver contraste ruim ou cue abaixo do tamanho mínimo legível (para automação) |
| `--json` | resultado em JSON (é o dict da função `legendar.legendar`) |

A saída é H.264 `yuv420p` no fps da base, com o áudio da base preservado, numa única passada de ffmpeg. Quando a saída fica fora de `legendas/` (ex.: `cortes/K01.mp4`), o `.srt` é copiado para o lado dela (`cortes/K01.srt`), que é onde a video-publicacao procura. Queimando um trecho — com ou sem `--cues` —, o campo `origem` das cues passa a ser o vídeo legendado.

**Horizontal com legenda queimada**: por padrão a DA só reserva a faixa da legenda no vertical e no quadrado (`legenda.reservar_em`); no horizontal, GC, crédito e gráficos do kit ficam **no mesmo lugar** da legenda. O script avisa toda vez. Se o vídeo tem ou vai ter GC, a saída é token — incluir `"horizontal"` em `legenda.reservar_em` (nova revisão da DA) e refazer as peças com GC —, não queimar por cima.

### 6. Faixa com alfa para o editor

```bash
python3 "$LEG/legendar.py" --video render/final.mp4 --palavras transcricao/final.palavras.json \
  --saida "legendas/K01 faixa.mov" --so-overlay --codec ambos --formato vertical --inicio 62.4 --fim 91.0
```

`.mov` = ProRes 4444 (editor); `.webm` = VP9 com alfa (compor por ffmpeg/kit). A faixa tem o tamanho do quadro, o fps da base e a duração do trecho: vai na trilha de cima, começando no mesmo ponto, sem escalar. Receita, tamanhos e o que foi conferido em `references/overlay-no-editor.md`.

### 7. Só a legenda oculta (.srt/.vtt) de um vídeo longo

```bash
python3 "$LEG/cues.py" gerar --palavras transcricao/final.palavras.json --video render/final.mp4 --nome final
```

Não renderiza nada (0,3 s). Grava `legendas/final.srt` — o nome que `video-publicacao` procura para `render/final.mp4`. O `.srt` é de frases inteiras (até 2 linhas de 42 caracteres, de 5/6 s a 7 s), com a pontuação da transcrição e o glossário aplicado. Um trecho nunca troca esse arquivo: o script recusa (passo 3).

### 8. Leia a conferência e aja

Toda execução imprime e devolve:

- **Zona segura**: `todos os N estados dentro`. Cue que não cabe nem no menor tamanho é **erro** e nada é gravado: divida a cue (`editar --dividir`).
- **Menor texto**: se uma cue encolheu, a causa é palavra mais larga que o bloco (ou cue editada à mão grande demais). Abaixo de 0,040 do lado menor (43 px em 1080) o aviso pede para dividir.
- **Contraste contra o vídeo**: 16 quadros amostrados; em cada um, a razão WCAG de cada cor da legenda contra o fundo real (já com a caixa ou o contorno da DA). Abaixo de **3:1** = `contraste ruim em 0:12–0:18`, com a sugestão de **token** a mudar na DA (nunca uma cor); entre 3:1 e 4,5:1 = "no limite". `fundo carregado` = há claro e escuro misturados atrás da legenda (GC ou texto do próprio vídeo): olhe a prévia.
- **Faixa não reservada** (horizontal, por padrão): ver passo 5.
- **Avisos de tempo**: cue que fica menos de 0,5 s, palavra que não chega a acender, fala acima de 25 caracteres por segundo (medidos pela duração real da cue) — quase sempre tempo ruim na transcrição; ouça o trecho.

Mostre os avisos ao usuário junto com a prévia. Aviso de contraste ou de faixa é assunto para a `video-direcao-de-arte`, não para um jeitinho na peça. A conferência final do projeto (carimbos, lint, loudness, limites de plataforma) é `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia`.

## Para outras skills

```python
import sys; sys.path.insert(0, "<skills>/video-legendas/scripts")      # achado por posição: Path(__file__).parents[2] / "video-legendas" / "scripts"
import legendar
r = legendar.legendar(video, palavras, saida, formato="vertical", plataforma="uniao", inicio=62.4, fim=91.0, foco=(0.31, 0.38))
r["saida"], r["carimbo"], r["cues_json"], r["srt"], r["srt_ao_lado"], r["avisos"], r["conferencia"]["zona"]["ok"]
```

CLI estável: `legendar.py --video V --palavras P --saida S [--formato vertical] [--plataforma uniao] [--inicio s --fim s] [--so-overlay]`. O nome das cues é o da saída (`cortes/K01.mp4` → `legendas/K01.*`); com trecho, saída ou `--nome` igual ao nome do vídeo de origem é erro 64. Códigos: 0 ok · 1 erro · **2 projeto sem DA** · 64 uso incorreto · 75 fila · 124 ffmpeg sem progresso. Erros são `comum.Erro` (com `.mensagem`, `.dica`, `.codigo`) ou os do kit (`da.SemDA`, `da.DAErro`). Campos do `cues.json`, do retorno e a regra do campo `origem` em `references/contrato.md`.

## Regras que o script aplica (detalhe e fontes em `references/regras-de-segmentacao.md`)

| regra | valor | de onde vem |
|---|---|---|
| palavras por cue, linhas por cue | `legenda.max_palavras`, `legenda.max_linhas` — tetos **sem exceção** | DA |
| a cue cabe sem encolher | medida com a fonte e o tamanho da DA, na zona segura | kit (`texto.py`) |
| fecha a cue sempre | fim de frase (`. ! ? …`) ou silêncio ≥ 0,70 s | casa |
| onde prefere cortar | depois de vírgula; antes de conjunção e preposição | Netflix, BBC |
| o que não separa | artigo/preposição/"não" do que vem depois, número da unidade, nome do sobrenome (com `de/da/dos`), numeral composto (`vinte e três`), auxiliar do verbo | Netflix, BBC; casa |
| saída da cue | 0,30 s depois da fala, ou até 2 quadros antes da próxima se o vão for < 0,5 s | Netflix (2 quadros); casa |
| toda palavra acesa pelo menos | 0,10 s (palavra de duração zero rouba tempo da anterior) | casa |
| legenda oculta | 42 caracteres × 2 linhas, 5/6 s a 7 s, 17 caracteres/s de referência | Netflix (pt-BR) |
| contraste | ruim < 3:1 · bom ≥ 4,5:1 | WCAG 2.2, critério 1.4.3 |

## Desempenho medido (M1, 8 GB)

- `cues.py gerar` de 73 palavras: 0,3 s. Prévia de 8 quadros a 540×960: 3–5 s.
- 3 s de corte 540×960 a partir de 1080p a 60 fps: 2–3 s com a fila livre. Com outros agentes renderizando, o mesmo corte levou até 30 s de parede: é a espera na trava, não o render.
- **75 s inteiros a 1280×720 (29,97 fps), 59 cues, 232 palavras, 498 estados**: 26 s, 35 s e 50 s de parede em três medidas com a máquina disputada (≈ 55 s de CPU; 0,35× a 0,67× o tempo real); 19,6 s na construção, com a fila livre. Memória máxima do Python: 265 MB. Saída de 9,8 MB.
- Faixa com alfa de 3 s a 1080×1920: 13 s para os dois codecs; ProRes 4444 = 6,9 MB (≈ 140 MB por minuto), WebM = 94 kB.

## Referências

- `references/regras-de-segmentacao.md` — cada regra de corte, tempo e legibilidade, com a fonte conferida em 2026-10-12 e o que é decisão da casa. Leia antes de mexer nas constantes ou de discutir uma quebra com o usuário.
- `references/estilo-pela-da.md` — "quero a legenda assim" → qual token da DA; o que cada estilo e cada animação fazem; o caminho da revisão. Leia quando o pedido for de aparência.
- `references/overlay-no-editor.md` — a faixa com alfa: especificação, como compor, o que foi e o que não foi testado.
- `references/contrato.md` — `cues.json`, glossário, retorno de `legendar.legendar`, onde cada arquivo é gravado e com que nome. Leia ao integrar outra skill.
- Testes: `cd "$CRIABR_SKILLS"/video-legendas/scripts && python3 -m unittest` (86 testes; cerca de 25 s com a fila livre; sem rede, em pasta temporária com espaço e acento) e `python3 testes/ponta_a_ponta.py --help` (3 presets × 3 estilos × 2 formatos sobre vídeo real, com folhas de contato).

## Armadilhas (observadas ao testar nesta máquina)

**A legenda acende a palavra errada em "E eu vou…".** O whisper devolve palavras de duração zero coladas no início da seguinte (no vídeo de teste de 75 s: `E`, `eu`, `Você`, `Um`, `Mas`, `Para`, todas com `a == b`). Sem tratamento, elas nunca acendem e a cue `E eu` durava 0,09 s. O script puxa essas palavras para trás (para o silêncio anterior ou até 60 % da palavra anterior) e avisa quantas mexeu. Se o trecho ainda ficar estranho, o problema é a transcrição: refaça-a cortando o silêncio inicial (skill `video-transcricao`).

**Pausa que o script não vê.** A transcrição palavra a palavra vem com as palavras coladas (`b` de uma = `a` da seguinte): o silêncio fica dentro da palavra anterior (`galera,` com 0,93 s). O script estima o fim da fala (0,25 s + 0,07 s por letra) para achar pausas e para não deixar a cue pendurada. É estimativa: quebra em lugar ruim se corrige com `editar --dividir`/`--juntar`.

**A cue sumia no meio da fala depois do glossário.** A estimativa acima era feita sobre o texto **novo**: `150.000` (7 caracteres) no lugar de 1,9 s de fala tirava a cue da tela 0,5 s antes de "reais" e a jogava para a cue seguinte; nome censurado saía 1,1 s antes de acabar de ser dito. Hoje o fim da fala é o do trecho original. Se uma cue de número ou de `***` parecer curta, confira `fala_fim` na palavra (`cues.json`).

**`QUE / É REAL`.** Comparar classes de palavra sem acento fez `é` (verbo) virar `e` (conjunção) e a linha quebrar no lugar errado. Hoje a comparação é com acento — por isso as `trocas` do glossário também respeitam acento.

**Nome ou numeral maior que a cue.** `o Luiz Inácio Lula da Silva` tem 6 palavras; `cento e cinquenta mil reais`, 5. Numa DA de 4 ou 5 palavras por cue eles **vão** partir (o teto da DA não tem exceção): o corte cai antes da partícula (`… Lula | da Silva`), nunca depois dela nem com o artigo pendurado. Saídas: `numeros_em_algarismo` no glossário (`150.000 reais` cabe), `cues.py editar --juntar/--dividir` no caso isolado, ou `legenda.max_palavras` maior na DA.

**O vídeo já tinha legenda ou GC na mesma faixa.** As duas bases de teste tinham texto embaixo (um karaokê próprio; um GC): a legenda nova cai por cima. O aviso `fundo carregado` acusa, mas quem decide é o olho na prévia. Legende o material limpo (antes dos GCs) ou mude `legenda.posicao.<formato>.y` na DA. No vertical, as cenas do kit já deixam livre a faixa da legenda; **no horizontal não** (`legenda.reservar_em`, passo 5) — foi assim que o GC do vídeo de 75 s e a legenda ficaram um sobre o outro.

**Recorte vertical sem ninguém no quadro.** Num plano de duas pessoas, o recorte pela âncora da DA mostrou o meio da mesa. Passe `--foco X,Y` (centro do rosto em frações do vídeo de origem) — ou deixe o enquadramento para a `video-cortes-verticais`.

**Texto pequeno numa palavra só.** `ABSORVIÇÃO` no preset de legenda grande (0,092) não coube nos 659 px do bloco e encolheu para 0,081. Não é defeito: a palavra é mais larga que o bloco. `--plataforma shorts` **não** resolve (a zona cresce, o bloco não: medido 659 px nas quatro zonas). A saída é token: `legenda.tamanho` menor ou `legenda.posicao.vertical.largura_max` maior — e aí a legenda deixa de caber na `uniao`.

**`.srt` de um trecho no lugar do `.srt` do vídeo inteiro.** `--inicio 20 --fim 30 --previa` sem `--nome` gravava `legendas/final.srt` por cima da legenda do vídeo longo, e a video-publicacao a enviava (ela procura pelo nome do vídeo antes de olhar `origem`). Hoje o trecho sem nome leva o intervalo no nome, `--nome final` num trecho é erro 64 e um `cues.json` de vídeo inteiro não é trocado pelo de um trecho sem `--refazer-cues`. Não renomeie à mão um `.srt` de corte para `final.srt`.

**Rodei de novo e ele se recusou.** Depois de um `cues.py editar`, gerar as cues de novo apagaria a correção: o script para com "foi corrigido à mão". Use `--cues <arquivo>`; para descartar as correções de propósito, `--refazer-cues`.

**Mudei a DA e as cues ficaram velhas.** As cues são medidas com a fonte e o tamanho da DA. Com `--cues` e DA alterada, sai o aviso "a direção de arte mudou"; se o estilo mudou (`karaoke` → `palavra`), é erro. Gere de novo e refaça as correções — e lembre que toda peça antiga fica `DA DIFERENTE` no `conferir-carimbo`.

**Pop de um quadro só.** A duração do pop é `movimento.duracoes.micro` (0,06–0,14 s nos presets): a 30 fps são 1 a 4 quadros. É um estalo, não um salto. No karaokê a palavra cresce no máximo meio vão para cada lado (com 8 % cheios, `uma investigação` virava `umainvestigação` e o `A` ampliado cobria o acento de `DENÚNCIA` na linha de baixo). Mais presença é token (`micro` maior), não opção.

**Primeiro quadro da cue quase invisível.** Com `animacao: fade`, a cue entra em até `movimento.duracoes.curta`; um quadro tirado no começo da cue mostra a legenda semitransparente. Para conferir sincronia por imagem, olhe o meio da palavra (é o que a prévia faz).

**Máscara de censura entre colchetes.** `"mascara": "[…]"` era lida como pontuação e saía quebrada; agora é erro de glossário. Use `***` ou `###` — e lembre que o glifo precisa existir na fonte da legenda.

**Nome de formato `thumbnail` num vídeo 1280×720.** O kit dá o nome do primeiro formato da DA com aquelas dimensões, e a thumbnail tem as de um vídeo 720p. Aqui o nome só vale para formato com fps — os demais saem `1280x720` —, e o carimbo que o kit gravou como `thumbnail` é regravado com o nome certo.

**Ler quadros de teste pela saída do ffmpeg traz só os últimos 8 MB.** A captura de `trava.rodar` é limitada; 90 quadros viraram 12. Para conferir pixels, selecione os quadros e grave num arquivo provisório (é o que `testes/apoio.py` faz).
