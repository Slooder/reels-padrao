# Método: construir a direção de arte de um projeto de vídeo

O SKILL.md resume o método em dez passos; este arquivo é a versão completa, com o roteiro de briefing, a leitura de referências, a tradução da análise em tokens, a construção de rotas e o checklist de aprovação. Os comandos foram executados no projeto de teste do kit (1.1.0; rotas, `extrair`, prancha e teste de movimento refeitos na 1.5.0; GC × legenda no horizontal, na 1.5.1); todos são chamadas diretas do executável `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da` — sem variável de shell, que não funciona em zsh.

## 1. Briefing — dez minutos que economizam dez revisões

Faça as perguntas em uma mensagem só, em lista, e aceite respostas curtas. Não avance para rota sem as cinco primeiras.

1. **Tema e tom.** Sobre o que é o vídeo e como ele deve soar: investigativo, didático, de opinião, de bastidor, promocional? Peça três adjetivos. ("Sóbrio, direto, com urgência" leva a uma DA; "leve, curioso, de laboratório" leva a outra.)
2. **Plataforma principal e formato.** YouTube longo (horizontal, 10–40 min) ou peça curta nativa (vertical, 20–90 s)? Haverá cortes do longo para Shorts/Reels/TikTok? Isso decide se a DA é desenhada primeiro para 1920×1080 ou para 1080×1920 — e a legenda vertical é o maior constrangimento de todos (só 61 % da largura é segura em qualquer altura).
3. **Referências.** Vídeos, canais, prints, capas, filmes, revistas. Peça links ou arquivos e, para cada um, **o que** gostou (a cor? o jeito do texto entrar? o ritmo?). "Quero parecido com X" sem o "o quê" não vira token.
4. **Restrições de marca.** Logo, cores obrigatórias (hex), fonte da marca (arquivo e licença), assinatura (@canal), marca d'água. Se a marca tem manual, peça o PDF.
5. **O que evitar.** Clichês do nicho que o usuário rejeita (robô azul em vídeo de IA, gradiente roxo, emoji, "cara de publicidade"), cores proibidas, fontes que detesta.
6. **Público e contexto de visualização.** Celular no ônibus com som baixo e legenda ligada? TV? Isso define tamanho mínimo de texto e se a legenda é protagonista.
7. **Material de que o vídeo é feito.** Só a pessoa falando para a câmera? Muito b-roll de arquivo (qualidades diferentes)? Gráficos de dados? Capturas de tela? O tratamento (`tratamento.grade`, `grao`, `moldura`) existe para unificar isso.
8. **É um canal ou um vídeo?** Se o usuário vai fazer uma série, a DA é do **canal** (vira preset pessoal) e cada vídeo herda dela com pequenas variações.

Registre as respostas em `pesquisa/briefing-da.md` (ou no próprio `conceito` do `da.json`): `frase`, `palavras_chave`, `faca`, `nao_faca` nascem daqui.

## 2. Coletar e ler referências

### Onde e como

- Imagens e prints vão para `<projeto>/da/referencias/` com nomes que digam o que são (`ref 01 vox cartela.png`, `ref 02 capa revista.jpg`). Quadros de vídeos: `extrair` amostra sozinho (`--quadros 6` por padrão) a partir do arquivo de vídeo; para um instante específico, extraia um PNG com ffmpeg sob a trava (`python3 "$CRIABR_SKILLS"/video-direcao-de-arte/kit/trava.py -- ffmpeg -ss 12.5 -i video.mp4 -frames:v 1 "da/referencias/ref 03.png"`).
- Três a oito referências. Menos que três não dá para ver padrão; mais que oito vira mural sem decisão.
- Anote cada uma em `conceito.referencias` como `{"arquivo": "referencias/ref 01 vox cartela.png", "nota": "bloco de cor atrás do texto; tipografia condensada; nada centralizado"}`. As imagens anotadas abrem a prancha (seção "Referências", com a nota de cada uma): o cliente vê a pergunta e a resposta na mesma página. Dentro de uma rota o mesmo caminho vale — a rota enxerga o `da/referencias/` do projeto.

### O que observar (e em que token cai)

| olhe para | pergunte | vira |
|---|---|---|
| **Cor** | É escuro ou claro? Quantas cores "vivas" existem de verdade (geralmente uma)? Qual é a cor de fundo real (raramente preto puro)? A pele está quente ou neutra? Há uma cor que aparece em todos os quadros? | `paleta.fundo/superficie/texto/primaria`, `tratamento.grade.temperatura/saturacao` |
| **Tipografia** | Quantas famílias? Serifada, grotesca, mono, condensada? Caixa alta? Tracking aberto? Títulos à esquerda ou centrados? Qual o tamanho do título em relação ao quadro (mais de 1/8 da altura?) | `tipografia.papeis`, `escala`, `papeis.*.caixa/tracking/escala_x` |
| **Composição** | Grade visível? Margens generosas ou apertadas? Texto encostado na zona segura ou no meio? Blocos chapados ou linhas finas? Cantos retos ou redondos? | `layout.grade/margem/raio/traco/densidade`, `graficos.gc.estilo`, `tarja.estilo` |
| **Movimento** | O que entra primeiro (forma ou texto)? Quica ou para seco? Rápido ou lento (meça: quantos quadros até parar)? Há máscara/revelação? Transições são cortes ou empurrões? | `movimento.curvas/duracoes/entrada_padrao/saida_padrao/transicoes/principios` |
| **Textura** | Grão? Vinheta? Footage tratado (contraste alto, dessaturado)? Duotone em fotos? Molduras nos inserts? | `tratamento.grao/vinheta/grade/duotone/moldura` |
| **Legenda** | Palavra a palavra ou bloco? Caixa atrás? Contorno? Onde fica no vertical? | `legenda.*` |
| **Som** (se a referência é vídeo) | Seco ou com música? Whoosh nas entradas? | `som.identidade/sfx/musica` |

### `extrair` — números em vez de impressão

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da extrair "da/referencias" "bruto/entrevista.mp4" --quadros 6 --cores 8      # pasta = tudo o que há dentro dela
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da extrair "da/referencias/ref 01 cartela.jpg" --regiao 0.08,0.38,0.2,0.05     # só um detalhe (x, y, largura, altura em frações)
```

Saída observada (2 referências de design — cartela preta com marca-texto amarelo e slide branco com fita amarela — mais 6 quadros de uma entrevista vertical):

```
Paleta dominante
  #0F100F   35,9%  L*   5  croma 0
  #FEFEFE     34%  L* 100  croma 0
  #252C2E   12,2%  L*  17  croma 3
  #CE9F84    3,6%  L*  69  croma 25      ← pele
  #F5C030    2,9%  L*  80  croma 73
  …
Acentos (cores vivas, mesmo em área pequena)
  #F7BF2C   2,48%  croma 75
Leitura
  · Imagem de luminosidade média (L* médio 46 de 100).  · Contraste alto (L* de 4 a 100 entre os percentis 5 e 95).
  · Dessaturada (média 0,18; p90 0,52).  · Temperatura quente (b* médio 4,1).
  · Grão limpo (desvio do ruído ≈ 0 em 255); equivale a tratamento.grao.intensidade ≈ 0.
  · Acentos (cores vivas, mesmo em área pequena): #F7BF2C (2,48% da área, croma 75).
Candidatos a token (proposta para discutir, não regra)
  fundo       #0F100F  — cor escura dominante (36% da área)
  texto       #FEFEFE  — maior contraste com o fundo (18,9:1)
  primaria    #F7BF2C  — acento: a cor viva mais presente (croma 75, 2,48% da área; contraste 11,3:1 com o fundo)
  superficie  #252C2E  — tom vizinho do fundo, para planos e caixas
```

**Paleta por área × acentos.** A paleta dominante responde "de que é feita a imagem" (fundo, superfície, pele); a cor de assinatura quase nunca aparece nela, porque ocupa pouco: um marca-texto de 0,7 % da área some no k-means. Os **acentos** são as cores vivas (croma ≥ 45) a partir de 0,3 % da imagem, uma por família de matiz, lidas nos pixels mais puros (a borda suavizada, que é mistura com o fundo, fica de fora). Só a cartela preta, sozinha: `primaria #F9C914 — acento … 0,73% da área; contraste 12,3:1` (o amarelo pintado era `#F6C614`). O contraste com o fundo vem informado, nunca é usado como filtro: amarelo sobre branco sai `contraste 1,7:1 com o fundo — baixo: use em blocos chapados com texto por cima, não como cor de texto` — a decisão é sua. Sem acento nenhum (só footage de gente), o candidato avisa: `NENHUMA cor de acento nas referências (croma ≥ 45); esta é só a mais viva por área … pode ser pele, madeira ou luz ambiente`.

Grava `da/referencias/referencias_analise.json` (por referência: `paleta` com `hex/area/lab/croma`, `acentos`, `luminancia_media/p5/p95`, `contraste_p5_p95`, `saturacao_media/p90`, `temperatura {b_medio, rotulo}`, `grao {sigma, rotulo, intensidade_sugerida}`; e `geral` com o conjunto + `acentos` + `candidatos` + `leitura`) e `referencias_folha.png` (miniaturas, paleta de cada referência, paleta do conjunto, acentos e candidatos) — mostre a folha ao usuário. Repetir o comando é seguro: a folha e a análise anteriores não viram referência.

## 3. Da análise aos tokens

Regras de tradução que funcionaram:

- **Fundo** = a cor escura (ou clara) dominante, **nunca** `#000000`/`#FFFFFF` puros: `#0A0A0A`, `#07090D`, `#F4F1EA`. Preto puro fica em `neutros` para sombras.
- **Superfície** = fundo deslocado um degrau (L* +8 a +12): é onde caixas e GC se apoiam sem contraste gritante.
- **Texto** = o neutro derivado do `extrair` ou um off-white/off-black com ≥ 7:1 sobre o fundo (`validar` reprova abaixo de 3:1; a prancha mostra a razão de cada cor). `texto_suave` entre 4,5 e 7:1.
- **Primária** = o **acento** das referências de design — a cor viva que aparece pouco e em todo lugar (o marca-texto, a fita, o selo), não a cor de maior área: acento quase nunca tem "área relevante". Pegue-a de `Acentos` no `extrair` (ou amostre o detalhe com `--regiao`), **saturada um pouco acima** do que aparece (compressão de vídeo e tela de celular dessaturam). Se o `extrair` disser que não há acento, a cor vem do briefing, não do footage. Confira o contraste sobre o fundo: ≥ 4,5:1 se ela vai carregar texto (palavra em destaque na legenda), ≥ 3:1 se é só filete e tarja; abaixo disso (amarelo sobre branco: 1,7:1) ela só serve a bloco chapado com texto por cima — e a legenda precisa de outra `cor_destaque`.
- **Dados** = primária, texto, texto_suave e mais três cores afastadas em matiz, intercalando claras e escuras (barras vizinhas não podem se confundir em P&B). Mínimo 6; o validador reprova menos. Escreva as cores da paleta **pelo nome** (`["primaria", "texto", "texto_suave", "#FF6B35", …]`): quando uma rota trocar a primária, a série troca junto.
- **Temperatura e saturação do tratamento** = o que leva o footage **do usuário** para perto das referências: se a referência é neutra/fria e o bruto é quente (pele laranja), `temperatura: -15` a `-25` e `saturacao: 0.8–0.85`; contraste 1,05–1,12 quase sempre ajuda.
- **Grão** = a `intensidade_sugerida` do material de arquivo que o vídeo vai misturar (se o arquivo tem grão 6 e a câmera é limpa, ponha 4–6 em tudo para unificar).
- **Tipografia** = escolha pela função, não pelo nome: título precisa de peso e largura (Archivo SemiExpanded Black com `escala_x 0.66`, Bebas, Montserrat 800, Roboto wdth 82); corpo precisa de x-height e números legíveis (Roboto, IBM Plex Mono, Montserrat 500); dados pedem mono ou tabular. **Duas famílias** no máximo; a legenda usa a mesma do título.
- **Escala** = parta de display 0,12–0,13 / h1 0,08 / h2 0,055 / h3 0,04 / corpo 0,03 / nota 0,02 e ajuste pelo número de palavras do título típico (títulos longos → display 0,10).
- **Movimento** = traduza a sensação em curva: "para seco" → `entrada [0.16, 1, 0.3, 1]` ou `[0.215, 0.61, 0.355, 1]`, sem y > 1; "tem vida" → `enfase [0.2, 0, 0, 1]` em filetes; durações 0,36–0,5 s para blocos, 0,7–0,9 s para o título. Escreva os `principios` em frases que um motion designer executaria.
- **Margens seguras** = copie de `plataformas.json` (os presets já trazem); mexa só no horizontal se o vídeo for também anúncio.

Depois de escrever: `da.py validar` (erros são bloqueantes; leia os avisos de legenda fora da zona segura) → `da.py compilar` → `da.py mostrar`.

## 4. Rotas: duas ou três DAs **realmente** diferentes

Rota é uma DA candidata inteira, não uma troca de cor. O usuário escolhe melhor comparando extremos do que ajustando um meio-termo. Varie o **eixo** entre as rotas:

| eixo | rota A | rota B | rota C |
|---|---|---|---|
| material/metáfora | arquivo e prova (dossiê) | painel de instrumento (lab-ia) | revista impressa (editorial-claro) |
| valor | escuro | escuro frio | claro |
| tipografia | condensada caixa alta + mono | grotesca larga + mono fina | serifada/grotesca humanista |
| movimento | máscara, para seco | digita, rápido | fade, lento |
| textura | grão + vinheta + P&B nas fotos | nitidez, grão leve, frio | papel quente, grão leve, sem vinheta |

Cada rota mora em `da/rotas/<nome>/da/da.json`, herdando de um preset (ou da DA atual do projeto) e sobrescrevendo só o que a diferencia. O subcomando `rotas` cuida de tudo — da raiz do projeto:

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas criar rota-a --base neon-shorts --frase "Rota A: preto absoluto e um magenta que salta." --primaria "#FF2D95"
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas criar rota-b --base editorial-claro --frase "Rota B: papel quente e uma fita amarela." --primaria "#F7BF2B"
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas criar rota-c --primaria "#F6C614"          # sem --base: herda a DA atual do projeto
# editar da/rotas/<nome>/da/da.json: só o que diferencia (tipografia, movimento, legenda, tratamento…)
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas listar                                      # herança, primária, validação, prancha e teste em dia ou não
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas comparar --com-atual                        # da/rotas/comparacao_vertical.png (4 colunas: 2960×5809 em 10,3 s)
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas comparar --formato horizontal --movimento   # + da/rotas/comparacao_movimento.mp4
```

`criar` valida na hora, e é aí que uma troca de cor malfeita aparece. Observado com a rota A acima (herda `neon-shorts`, só a primária trocada): `cor.paleta: primaria #FF2D95 e secundaria #FF2E93 são quase idênticas (ΔE 1,3) — parece sobra de uma troca de cor`. Trocar a primária **e** o destaque para o mesmo hex deixa o gradiente `choque` chapado (`cor.gradientes.choque: todas as paradas resolvem para #FF2D95`). A série de dados acompanha sozinha: os presets escrevem `"primaria"` em `cor.dados`, então `dado-1` vira o magenta. Leia os avisos e mexa também na `secundaria` (ou no que o aviso apontar) antes de gerar a prancha.

`comparar` gera as pranchas que faltam, alinha as colunas **por seção** (paleta ao lado de paleta, componentes ao lado de componentes) e na mesma escala; o fundo das amostras é um quadro do projeto — a rota enxerga `bruto/`, `broll/` e `da/referencias/` do projeto-pai, não precisa de cópia. Para peça curta (Reels, Shorts, TikTok) compare no vertical, que é o padrão; `--formato horizontal` para o longo. As fontes do preset herdado resolvem para `kit/fontes/` (nada a copiar na fase de rota). A DA principal continua sendo achada da raiz e das pastas de trabalho; só quem estiver **dentro** de `da/rotas/<nome>/…` acha a rota — rode tudo da raiz.

Mostre a folha de comparação e os testes de movimento. Pergunte o que ficou e o que incomodou em cada uma; é comum a resposta ser "a paleta da A com o movimento da C" — isso é refinamento, não rota nova.

**Adotar a rota escolhida** (grava a rota com a herança aplicada em `da/da.json`, copia as fontes para `da/fontes/`, guarda `da.json.bak-<data>` e atualiza o bloco do CLAUDE.md — sem passar pela biblioteca de presets):

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da rotas adotar rota-b
#   Rota 'rota-b' adotada: …/da/da.json  (revisão 2, não aprovada, sha256 d8aa5304a0b5…)
#   ! 2 fonte(s) em da/fontes/ que a DA não usa mais: ArchivoSemiExpanded-Black.ttf, IBMPlexMono-Bold.ttf — apague se não forem voltar
```

Nome, slug e referências do projeto ficam; a aprovação é zerada (e a revisão sobe 1 se a DA anterior estava aprovada). Depois refine tokens direto em `da/da.json`, `validar`, `compilar`, `prancha`, `teste-movimento`, e apague `da/rotas/` quando a DA for aprovada (ou deixe como registro — `conferir-carimbo` não entra em `da/`).

## 5. Refinar com a prancha e o teste de movimento

- A prancha (`da/prancha.png`, 1920×~7 000; `prancha_vertical.png`, 1080×~7 800) é o documento que o cliente aprova. Seções: as **referências** do conceito com a nota de cada uma (quando `conceito.referencias` tem imagens); paleta com contraste WCAG de cada cor sobre o fundo; papéis e escala com amostra acentuada; componentes montados pelo motor (cartela de título, GC + legenda, moldura); **em escala 1:1**; tratamento antes/depois num quadro **do próprio projeto**; barras, curvas com durações e as transições permitidas a meio caminho; margens seguras (só na vertical: a união em tamanho grande com GC e legenda na posição real, e uma miniatura por plataforma); thumbnail com zona proibida, faça/não faça, som e marca. O cabeçalho diz `RASCUNHO — AGUARDANDO APROVAÇÃO` até o `aprovar`, e depois `APROVADA EM dd/mm/aaaa`.
- **A legenda da prancha é a da produção.** Ela não é desenhada pelo motor: é o PNG que `texto.estados_da_legenda` gera — o mesmo caminho da skill de legendas — colado na posição real. **E o GC da prancha é o da produção**: no vertical e no quadrado ele desvia da faixa da legenda e os dois aparecem juntos; no horizontal, onde a DA por padrão não reserva a faixa (`legenda.reservar_em`), o GC aparece na base — onde a cena `gc` o põe — e a legenda vem numa tira à parte, com a frase que explica. Se o cliente quer legenda queimada no horizontal, a resposta não é mexer na prancha: é pôr `"horizontal"` em `legenda.reservar_em`, regerar e mostrar de novo. O que o cliente aprova é o que sai.
- **Legibilidade se confere na seção "Em escala 1:1"**, não reduzindo a prancha: ela mostra uma faixa do quadro sem redução (1080 px de largura na vertical, 1920 na horizontal), sangrada de borda a borda. Abra a prancha vertical **no celular, na largura da tela**: o que se lê ali é o que se lê no vídeo. (Reduzir a prancha a 1/3 engana por um fator de quase 3: os quadros de componentes já estão a 0,28–0,44 do tamanho real, e uma legenda de 56 px vira 8 px.) Se o cargo do GC ou o crédito não se leem na faixa, suba `graficos.gc.tamanho_cargo` / `graficos.citacao_fonte.tamanho` — o validador avisa abaixo de 0,022 do lado menor (8,6 pt num celular).
- O quadro de referência (fundo das amostras e antes/depois) é procurado primeiro no footage — `bruto/`, `broll/bruto/`, `broll/tratado/`, `broll/` — e só depois em `da/referencias/` (que costumam ser prints de design). `--referencia <arquivo>` escolhe; `--foto <arquivo>` põe uma foto no GC e na thumbnail.
- O teste de movimento (`da/teste_movimento.mp4`, 960×540; `--formato vertical` para peça curta) tem três atos: a cartela de título entra, respira e sai; o GC entra sobre um quadro do projeto, na posição da produção — com a legenda correndo palavra a palavra onde a DA reserva a faixa dela (vertical e quadrado, por padrão; no horizontal padrão o ato mostra só o GC); as barras entram, contam até o valor final e ficam. Entre os atos, a transição padrão da DA. **A duração sai das durações da DA** — 4,7 s no `neon-shorts`, 6,7 s no `dossie`, 8,2 s no `editorial-claro` —, então nada é cortado em DA lenta; `--dur` só mexe nos respiros e `--atos gc` refaz um ato só enquanto você ajusta. Se parece "lento", mexa em `duracoes` antes de mexer em curvas; se "quica", tire o y > 1 das curvas.
- Cada mudança: `validar` → `compilar` → `prancha` (3 s) → olhar. Dez iterações cabem em dez minutos.

## 6. Checklist de aprovação

Só rode `da.py aprovar` quando tudo abaixo estiver verdadeiro **e o usuário tiver dito que aprova** olhando a prancha final e o teste de movimento:

- [ ] `validar` sem erros; avisos lidos e aceitos de propósito (ex.: legenda que encosta na zona `uniao`). Nenhum aviso de `legenda × GC`, de texto abaixo do mínimo legível ou de cor "quase idêntica" sem decisão.
- [ ] Contraste: `texto`×`fundo` ≥ 7:1; `texto_suave`×`fundo` ≥ 4,5:1; `primaria`×`fundo` ≥ 3:1 (≥ 4,5:1 se carrega texto); cada cor de `dados` ≥ 3:1 sobre o fundo.
- [ ] Legenda, nome e cargo do GC legíveis na seção "Em escala 1:1" da prancha vertical vista no celular, na largura da tela; legenda dentro da zona `uniao` com `max_linhas`, GC fora da faixa da legenda.
- [ ] `validar` sem avisos, e a nota do horizontal lida com o cliente: o longo leva legenda queimada? Se sim, `"horizontal"` em `legenda.reservar_em` **antes** de aprovar (a prancha horizontal muda: o GC sobe).
- [ ] No máximo duas famílias tipográficas; todos os papéis com `arquivo` apontando para `da/fontes/` (nada de fonte do sistema, salvo decisão explícita).
- [ ] Uma cor de destaque; `faca`/`nao_faca` com pelo menos quatro regras concretas cada.
- [ ] Antes/depois do tratamento feito com footage **do projeto** e aprovado ("unifica sem matar a pele").
- [ ] Movimento: teste assistido; `principios` escritos.
- [ ] Margens seguras conferidas com `plataformas.md` (data de verificação dentro de 3 meses).
- [ ] Se é DA de canal: `salvar-preset <canal>` depois de aprovar.
- [ ] Prancha e teste de movimento em dia com a DA: `da.py aprovar --estrito` recusa se algum estiver ausente ou tiver sido feito com outra versão dos tokens (sem `--estrito`, só avisa). Depois de aprovar, a prancha é regenerada com o cabeçalho `APROVADA EM …` — é ela que fica de registro.

A aprovação é cobrada no fim do pipeline: a conferência final (`da.py conferencia`, o portão de publicação — `kit-api.md` §18) reprova o projeto com DA não aprovada (`da.nao_aprovada`: "rode `da aprovar`") ou alterada depois da aprovação (`revisar` + `aprovar`). Vale também para a DA de vídeo que herda a do canal (`init --base <canal> --herdar`): `projeto.*` nunca é herdado, então cada vídeo nasce sem aprovação e passa pelo próprio `aprovar`. Enquanto a DA está em construção, `da.py conferencia --previa` mostra o resto do estado do projeto sem reprovar por isso (e grava `qa/previa.json`, que não libera publicação).

## 7. Exemplos de conceito → tokens

**"Dossiê investigativo"** (preset `dossie`): preto de arquivo `#0A0A0A`, superfície `#161616`, off-white `#F4F1EA`, marca-texto `#FFC700` como única cor viva; Archivo SemiExpanded Black com `escala_x 0.66`, caixa alta, tracking −0,005; IBM Plex Mono para dados; `raio 0`, `traco 0.0056`, sem sombra; entrada `mascara` (bloco abre, texto aparece depois), saída `fade`, curvas sem overshoot, durações 0,12/0,28/0,5/0,9; tratamento contraste 1,08, saturação 0,78, grão 6 temporal, vinheta 0,35, moldura `cantoneiras`; GC `barra` com cargo a 0,026; legenda karaokê 0,062 em caixa alta com contorno `fundo` 0,11; thumbnail com foto P&B (saturação 0) e contorno de pessoa amarelo.

**"Laboratório de IA"** (preset `lab-ia`): fundo `#07090D` frio, ciano `#38E1FF` para "o que está ativo", violeta `#9D7BFF` para "o que é do modelo"; Roboto variável (título wght 700 / wdth 82; legenda wght 800 / wdth 88) e Fira Code; entrada `digita`, durações curtas (0,08/0,2/0,36/0,7); tratamento frio (temperatura −18, saturação 0,85, nitidez 0,15, grão 3); moldura `janela`; legenda com caixa (`fundo` com alfa) e `max_palavras 5`.

**"Revista em movimento"** (preset `editorial-claro`): papel `#F4EFE6`, tinta `#1B1A17`, vermelho editorial `#C1121F` e um azul-marinho de apoio; Montserrat 800 nos títulos, Roboto no corpo, IBM Plex Mono nos dados; entrada e saída `fade`, durações longas (0,14/0,36/0,64/1,1), só `corte` e `fade`; grão leve 3, sem vinheta, temperatura +8 (papel quente); GC em `linha` (com o painel de proteção em papel por trás, `protecao: auto`), moldura `borda`, densidade `arejada`; legenda em `bloco` 0,046 com caixa de papel quase opaca (alfa 0,94) e 7 palavras por cue.

**"Feito para o polegar"** (preset `neon-shorts`): preto `#050505`, branco puro e três neons (verde-limão `#B6FF00` como primária, magenta, ciano); Bebas Neue em caixa alta nos títulos, Montserrat 900 na legenda; entrada `escala` com curvas de overshoot de propósito (`entrada [0.34, 1.56, 0.64, 1]`, `enfase [0.68, -0.6, 0.32, 1.6]`), durações mínimas (0,06/0,16/0,28/0,5), saída `corte`, transições `empurra`/`zoom`; saturação 1,25, contraste 1,12 com gama 1,1 e vinheta 0,4 (num quadro de estúdio escuro, contraste 1,15 + vinheta 0,55 derrubavam o L* médio de 23,8 para 15,7; assim fica em 21,2), nitidez 0,4, sem grão; legenda `palavra` a palavra, **0,092** em caixa alta com contorno preto 0,14, 3 palavras por cue, y 0,56 no vertical; GC `etiqueta`, densidade `densa`.

**"Aula no quadro"** (preset `quadro-negro`): lousa `#1F2D27`, giz off-white `#F2EFE4`, amarelo `#F6D55C` como primária, azul e rosa de giz como apoio; Urbanist (800/600/500/900) e IBM Plex Mono; entrada `sobe` com leve overshoot (`enfase [0.34, 1.3, 0.64, 1]`), saída `fade`, transições `corte`/`fade`/`desliza`; grão 4, vinheta 0,5, temperatura +6; moldura `polaroid`; GC `caixa`; legenda karaokê 0,056 com contorno `fundo` 0,09.

Quando o briefing não cabe em nenhum preset, parta do mais próximo com `herda` e sobrescreva seção por seção — é mais barato e mais seguro (o validador cobre o resto) do que escrever 270 linhas do zero.
