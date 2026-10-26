---
name: video-cortes-verticais
description: Tira cortes verticais 9:16 (YouTube Shorts, Instagram Reels, TikTok) de um vídeo longo 16:9 já pronto — lista os trechos candidatos a partir da transcrição (sempre de início a fim de frase, com duração dentro dos limites de cada plataforma), registra a escolha editorial em cortes/plano.json para o usuário aprovar e executa o plano — corte preciso no vão entre palavras, enquadramento que acha os rostos (recorte que acompanha a pessoa sem tremer, dois apresentadores empilhados, centro ou o 16:9 inteiro sobre fundo desfocado), legenda queimada pela video-legendas, gancho ou título opcional nos primeiros segundos, loudness de peça curta e carimbo. Use sempre que o usuário disser "faz os cortes desse vídeo", "tira uns shorts do episódio", "quais trechos dão um bom reels?", "corta do minuto 12 ao 13 em vertical", "deixa esse trecho em 9:16", "enquadra no rosto", "põe os dois um em cima do outro", "o corte está cortando a cabeça dele" ou "refaz o K03 seguindo a pessoa da direita" — e quando o render final do longo ficar pronto e faltarem as peças curtas. Difere das irmãs — video-legendas só queima a legenda (aqui ela é chamada por dentro); video-transcricao produz as palavras cronometradas que aqui são insumo; gerar-ganchos escreve ganchos para gravar (aqui só se usam os critérios dela para julgar trechos que já existem); video-montagem monta a timeline do longo; video-broll trata material de terceiros; video-publicacao empacota e envia os cortes prontos; video-direcao-de-arte decide a aparência e faz a conferência final (`da conferencia`).
---

# Cortes verticais: do longo 16:9 para Shorts, Reels e TikTok

Entra `render/final.mp4` (ou outro vídeo 16:9) e a transcrição palavra a palavra; saem, por corte, `cortes/K01.mp4` (9:16, legendado, loudness de peça curta), `cortes/K01.srt`, o carimbo `cortes/K01.mp4.da.json` e a folha de contato `cortes/_previa_K01.png`. O que esta skill decide é **onde cortar e o que fica no quadro**. Quais trechos valem a pena é decisão editorial: sua (com os critérios da skill `gerar-ganchos`) e do usuário, que aprova `cortes/plano.json` antes de qualquer render.

```bash
CV="$CRIABR_SKILLS"/video-cortes-verticais/scripts   # só o caminho na variável (em zsh, opção dentro de variável não roda)
cd "/caminho/do projeto"                             # ou --projeto "/caminho/do projeto" no cortar.py e no enquadrar.py
python3 "$CV/cortar.py" --help                       # python3 = python (Pillow e numpy)
```

## Passo 0 — Direção de arte

1. **Ache a DA**: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da achar --json` na pasta do projeto. Código 2 = não há `da/da.json`: **pare**, avise o usuário e chame a skill `video-direcao-de-arte`. O `cortar.py` faz a mesma checagem e sai com 2; não existe corte "só para ver" sem DA.
2. **Nada visual se decide aqui.** Legenda (estilo, cor, fonte, posição) é o bloco `legenda` da DA, aplicado pela video-legendas; a abertura é a cena `titulo` do motor do kit, nos tokens da DA; o fundo desfocado do modo `faixa` é `video.filtro_encaixe`; o loudness é `som.loudness.curto`; o encode é `video.args_encode`. Pedido como "legenda amarela" ou "título maior" é mudança de token na DA (`da revisar` → editar → `aprovar`), não opção de corte.
3. **Limites de plataforma vêm do kit** (`da.limite`): duração mínima, máxima e recomendada de shorts, reels e tiktok nunca estão escritas nesta skill. Para ver: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da plataformas`.
4. **Toda saída sai carimbada** (ferramenta `video-cortes-verticais`): `t0_origem`/`t1_origem`, plataformas, enquadramento (painéis ou trajetória), abertura, legenda, loudness medido e os insumos (vídeo de origem, cues, peça da abertura). Intermediários têm prefixo `_` (`cortes/_rostos/`, `cortes/_abertura/`, `cortes/_previa_*.png`) e ficam fora da conferência.
5. **Uma tarefa pesada por vez**: ffmpeg, Chromium (abertura), swiftc e a detecção de rosto entram na trava do kit, em fila. Não rode dois `cortar.py` ao mesmo tempo esperando ganhar tempo.

## Fluxo

### 1. Confira os insumos

| precisa existir | de onde vem | se faltar |
|---|---|---|
| `da/da.json` | video-direcao-de-arte | pare (Passo 0) |
| vídeo de origem (`render/final.mp4` por padrão) | video-montagem / render final | peça o caminho; vai em `"origem"` no plano |
| `transcricao/<origem>.palavras.json` — `[{"a","b","w","p"}]` com os tempos do vídeo de origem | video-transcricao | transcreva antes; sem palavras não há fronteira de frase nem legenda |
| skill `video-legendas` instalada ao lado | — | sem ela só roda com `--sem-legenda` |

A transcrição precisa ser **do arquivo que será cortado**. Se o longo foi remontado depois da transcrição, os tempos não batem: transcreva o render final.

### 2. Liste os candidatos

```bash
python3 "$CV/candidatos.py" transcricao/final.palavras.json --min 20 --max 60 --quantos 12 --frases
```

Cada janela começa em início de frase e termina em fim de frase. Sem `--min`/`--max` vale a faixa do kit (mínimo das plataformas até a duração recomendada); pedir fora dos limites dá erro 64. Para cada janela saem **sinais**, não vereditos: `pergunta` e `número` na abertura, `abre dependente` (começa por "E", "Mas", "Isso"… e pode pedir contexto), palavras por segundo, pausas e a maior delas, confiança da transcrição e a folga antes/depois para o corte. A pontuação só ordena a lista. `--frases` lista todas as frases com tempo, para montar uma janela à mão; `--saida cortes/_candidatos.json` guarda tudo.

### 3. Escolha (decisão editorial) e escreva o plano

Leia o texto inteiro de cada candidata — não escolha pela pontuação. Critérios (os da skill `gerar-ganchos`; leia-a se estiver instalada):

- os **primeiros 2–3 segundos** param o dedo: pergunta, número, afirmação que contraria, promessa concreta;
- o trecho **se sustenta sozinho**: quem nunca viu o vídeo entende, não há "como eu disse" nem pronome sem dono;
- **termina fechando** a ideia (conclusão, virada, número), não no meio do raciocínio;
- uma ideia por corte; prefira o mais curto que fecha.

Descarte janela com `abre dependente` a menos que a frase funcione sozinha. Quando a melhor abertura está no meio de uma frase longa, não force: escolha outra janela (ou, em último caso, `--meio-de-frase`).

Veja quantos rostos há em cada trecho antes de decidir o enquadramento:

```bash
python3 "$CV/enquadrar.py" render/final.mp4 --inicio 29 --fim 38
#   pessoa 1 (esquerda): centro x 0,29 y 0,43, rosto 0,12 da largura, presente em 100% dos quadros
#   pessoa 2 (direita): …            → enquadramento sugerido: empilhado (2 rostos persistentes no trecho)
```

Dois rostos persistentes → `empilhado`; um → `rosto`; nenhum → `centro`. É sugestão: num trecho em que só um dos dois fala, `rosto` com `"pessoa"` costuma ser melhor que `empilhado`.

Grave `cortes/plano.json`:

```json
{"versao": 1, "origem": "render/final.mp4", "cortes": [
  {"id": "K01", "t0": 29.17, "t1": 37.20,
   "titulo": "…", "gancho": "…", "motivo": "por que este trecho (fica registrado no carimbo)",
   "enquadramento": "empilhado", "foco": null,
   "plataformas": ["shorts", "reels", "tiktok"], "saida": "cortes/K01.mp4"}
]}
```

| campo | regra |
|---|---|
| `id` | `K01`, `K02`… sem repetir |
| `t0`, `t1` | segundos do vídeo de origem, em fronteira de frase (tolerância de 0,35 s); copie da lista de candidatos |
| `titulo`, `gancho`, `motivo` | texto para humanos; `gancho` ou `titulo` vira a abertura na tela se você pedir |
| `enquadramento` | `rosto` · `centro` · `faixa` · `empilhado` · `auto` (decide pelo número de rostos) |
| `foco` | `null` = detecção; `[x, y]` (frações 0–1 do quadro de ORIGEM) fixa o recorte ali; no `empilhado`, `[[x, y], [x, y]]` = painel de cima e de baixo. **Foco manual sempre vence a detecção** |
| `pessoa` (opcional) | `"esquerda"` ou `"direita"`: quem o `rosto` segue; no `empilhado`, `"direita"` põe a pessoa da direita em cima |
| `abertura` (opcional) | `"gancho"`, `"titulo"` ou `"nenhuma"` só para este corte (sobrepõe `--abertura`) |
| `plataformas` | subconjunto de `shorts`, `reels`, `tiktok`; a duração é conferida contra cada uma. Uma só = zona segura dela; várias = a união |
| `saida` | `.mp4` dentro de `cortes/`, sem prefixo `_` |

### 4. Valide, mostre a prévia e peça a aprovação

```bash
python3 "$CV/cortar.py" --validar     # contrato, fronteiras de frase e duração por plataforma; nada é renderizado
python3 "$CV/cortar.py" --previa      # só cortes/_previa_K0N.png: 4 quadros do enquadramento de cada corte (segundos)
```

**Olhe cada folha** (abra o PNG): rosto inteiro, com a cabeça inteira e centrado; no `empilhado`, uma pessoa por painel. Mostre ao usuário o plano (trecho, texto de abertura e fecho, duração, enquadramento, motivo) com as folhas e **espere o "aprovo"**. Ajustes comuns: trocar `pessoa`, dar `foco`, trocar `empilhado` por `rosto`, usar `faixa` quando o gráfico da tela importa.

### 5. Execute

```bash
python3 "$CV/cortar.py" --abertura gancho            # todos os cortes do plano, no formato vertical da DA
python3 "$CV/cortar.py" --so K02 --abertura nenhuma  # só um, sem texto de abertura
python3 "$CV/cortar.py" --formato 540x960            # rascunho rápido em tamanho reduzido (não é entregável)
```

O que acontece em cada corte:

1. **Corte no vão entre palavras**: começa `--respiro` (0,1 s) antes da primeira palavra e termina o dobro disso depois da última, nunca passando do meio do silêncio vizinho.
2. **Enquadramento** (tabela abaixo).
3. **Abertura** (`--abertura gancho|titulo`, 2,5 s por padrão, `--abertura-dur`): cena `titulo` do motor, com alfa, dentro da zona segura e fora da faixa da legenda. Se o lugar padrão cai em cima de um rosto, o bloco vai para o maior vão sem rosto da área livre; se não cabe em nenhum, fica no lugar que cobre menos rosto e sai um aviso. Texto que colide com a legenda ou sai da zona segura é erro: encurte.
4. **Som**: `loudnorm` em duas passagens no alvo `som.loudness.curto` da DA, medido só no trecho.
5. **Legenda**: `legendar.legendar(...)` da video-legendas, com as palavras do trecho; gera também `legendas/K01.cues.json` (corrigível) e copia o `.srt` para `cortes/`.
6. **Carimbo** e **folha de contato do corte pronto** (`cortes/_previa_K01.png`; com abertura, o primeiro quadro é dela).

| modo | o que faz | quando |
|---|---|---|
| `rosto` | recorte 9:16 que acompanha a pessoa. Parado enquanto o rosto está na zona morta (15% da largura do recorte para cada lado); só anda se o rosto ficar fora por 0,6 s, com rampa suave de 0,5 a 1,4 s; troca de plano = corte seco no quadro exato | uma pessoa falando |
| `empilhado` | um recorte por apresentador, um sobre o outro, cada um centrado no próprio rosto | conversa, reação |
| `centro` | recorte parado no centro (ou no `foco`) | sem rosto: tela, objeto, paisagem |
| `faixa` | o 16:9 inteiro sobre fundo desfocado | gráfico, tela ou lettering que não pode ser cortado |

### 6. Confira e entregue

Olhe a folha de cada corte pronto: rosto inteiro, legenda legível e fora do rosto, abertura completa. Leia os avisos do `cortar.py` (cue rápida demais, loudness fora do alvo, queda para `centro`). Depois:

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia --corte K01 --corte K02
```

É a conferência final do kit (carimbo, loudness, resolução e duração por plataforma → `qa/relatorio.json`). Com ela aprovada, a publicação é da skill `video-publicacao`. Palavra errada na legenda: o caminho certo é o glossário do projeto (`legendas/glossario.json`, da skill `video-legendas`), que corrige a legenda queimada e o `.srt`; rode `cortar.py --so K01` de novo. Ajuste fino só na legenda queimada: edite `legendas/K01.cues.json` e rode `cortar.py --so K01 --manter-cues`.

## Detecção de rosto

- `scripts/rostos.swift` usa o framework Vision do macOS (`VNDetectFaceRectanglesRequest`), amostra 3 quadros por segundo (`--fps-rostos`) e grava as caixas normalizadas. É compilado **uma vez** com `swiftc`, sob a trava, para `$VIDEO_OPS_HOME/cache/rostos-<hash>` (uns 20 s na primeira vez).
- O resultado fica em `cortes/_rostos/<origem>.json`, por vídeo, e só o trecho ainda não visto é analisado. Se o arquivo de origem mudar (tamanho ou data), o cache é refeito sozinho.
- **Sem Vision** (não é macOS, falta `swiftc`, a compilação falha) **ou sem rosto no trecho**: `rosto` e `empilhado` caem para `centro` com um aviso que diz o motivo. Use então `foco` manual no plano ou `--sem-rostos` para nem tentar. `xcode-select --install` instala o `swiftc`.
- Rosto menor que 4% da largura do quadro (pôster, tela ao fundo) é ignorado; "persistente" = aparece em pelo menos metade dos quadros do trecho.

## Armadilhas

- **Limite mínimo não é opinião.** O Reels recusa peça abaixo do mínimo que está no kit; um corte de uma frase curta reprova na validação com "menos que o mínimo do reels". Junte a frase vizinha ou tire a plataforma do corte.
- **O `rosto` não sobe nem desce em fonte 16:9.** O recorte 9:16 usa a altura inteira do quadro; só há ajuste horizontal. Cabeça cortada em cima no vertical já estava cortada no longo. No `empilhado` há folga vertical e o rosto fica a 42% da altura do painel.
- **Troca de plano dentro do corte.** No `rosto`, quando a câmera corta dos dois apresentadores para o plano fechado de um, o recorte salta junto, no quadro exato (verificado quadro a quadro). O `empilhado` é um quadro **fixo**: se os dois rostos aparecem juntos em menos de 85% do trecho, sai o aviso "só aparecem juntos em N%" — troque por `rosto` ou encurte o corte.
- **Dois rostos e nenhum `pessoa`.** O `rosto` fica com o maior e avisa. Diga `"pessoa"` no plano; "esquerda" e "direita" são as do quadro de origem.
- **Grafismo do vídeo original é cortado.** Tarja, GC e legenda já queimados no longo ficam pela metade no `rosto`. Se o grafismo importa, use `faixa`; o ideal é cortar de um render limpo.
- **Abertura em cima do queixo.** O lugar padrão do título (logo acima da legenda) coincide com o rosto no modo `rosto`; por isso o bloco é reposicionado para o vão livre. Texto longo, de duas linhas, pode não caber em vão nenhum: mantenha o gancho em até cinco palavras.
- **A legenda é da DA.** Se ela cai sobre a testa da pessoa de baixo no `empilhado`, a correção é o token `legenda.posicao` (revisão da DA) ou inverter os painéis com `"pessoa": "direita"`, nunca um ajuste escondido aqui.
- **Última frase do vídeo.** O respiro do fim é limitado pelo fim do arquivo; um corte que acaba na última palavra termina seco. Prefira trechos com folga (`folga` na lista de candidatos).
- **Transcrição sem pontuação.** Com menos de um ponto a cada 40 palavras, a frase passa a fechar em pausa de 0,7 s; as fronteiras ficam menos confiáveis. Leia o texto antes de aprovar.
- **Tamanho reduzido é rascunho.** `--formato 540x960` serve para conferir enquadramento; a conferência final avisa que a resolução está abaixo da recomendada. O entregável sai sem `--formato`.
- **`cortar.py` reescreve o corte inteiro.** Rodar de novo substitui `K01.mp4`, o `.srt`, o carimbo e **as cues**: edição feita à mão em `legendas/K01.cues.json` some, a menos que você passe `--manter-cues`. E `--manter-cues` depois de mudar `t0`/`t1` usa cues do trecho antigo: aí não use. A edição das cues não chega ao `.srt` (ele sai das frases da transcrição); para isso existe o glossário.

## Testes

```bash
python "$CRIABR_SKILLS"/video-cortes-verticais/scripts/testes/test_cortes.py
```

Dez testes, sem rede e com vídeo sintético: janelas em fronteira de frase com limites do kit, sinais, corte no vão com respiro, reprovação de meio de frase e de duração por plataforma, trajetória (parada com tremor, suave fora da zona morta, corte seco em troca de plano), sugestão pelo número de rostos, posição da abertura e um corte real com legenda, `.srt`, carimbo e prévia.
