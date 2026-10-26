# API do kit de direção de arte — para quem escreve skills irmãs

Referência do que existe em `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/` (kit 1.6.0, verificado em 2026-10-12 executando cada chamada abaixo numa pasta com espaço e acento no nome). Tudo aqui foi rodado; o que não foi rodado não está aqui. A versão 1.2.0 fechou a robustez de execução: trava que nunca fica presa (§6), motor que não trava nem deixa órfão (§8), cenas puras em toda a duração (§9) e auditor sem escapes implícitos (§11). A 1.3.0 fechou a qualidade da skill: executável `kit/bin/da` (§0, §2), uma forma só de cor com alfa no CSS (§12, §13), identidade da DA com regra exata (§7), lint que lê Python e nunca dá sinal verde para o que não leu (§12), licenças das fontes, bloco do CLAUDE.md e carimbo que não promove auditoria pulada (§2, §7), e erro de uso do `render` que não espera a fila da trava (§2, §8). A 1.4.0 fechou a API de que as irmãs dependem: legenda em PIL igual à do motor e sempre dentro da zona segura (`texto.compor_legenda`, §4), quadros PIL → vídeo e N cues numa passada (`video.Codificador`, `video.compor_cues`, §5), transições da DA executáveis (`video.juntar`, `ctx.transicao`), proveniência dos insumos no carimbo (§7), intermediários com prefixo `_` (§14), plataformas com nomes canônicos (`da.limite`, §3), peças do kit para cenas externas (`ctx.kit`, §10.1) e loudnorm em duas passagens (§5). A 1.5.0 fechou o produto visual e o método: faixa da legenda reservada — GC, título, gráfico, crédito, assinatura e moldura nunca nascem em cima da legenda queimada (`d.area_livre`, `ctx.area_livre`, parâmetro `reservar_legenda`, §3, §10), GC protegido sobre footage por token (`graficos.gc.protecao`, §9.1), rotas como subcomando (`da.py rotas criar|listar|comparar|adotar`, §2), prancha com a legenda desenhada por `texto.py` e uma faixa em escala 1:1, teste de movimento que calcula a própria duração pelas durações da DA (contrato `duracao()` de cena, §9), `extrair` com cores de acento, `cor.dados` com nomes da paleta e validador que acusa legenda × GC, texto abaixo do mínimo legível e DA incoerente depois de uma troca de cor (§2). A 1.5.1 fechou quatro pontas: a prancha e o teste de movimento mostram o GC **onde a produção o põe** — no horizontal, por padrão, na base e sem desviar da legenda; `validar` anota e `d.legenda_reservada` responde (§2, §3, §8.1); o auditor passou a ver o que o estilo computado não mostra (controles nativos, imagem por CSS, marcador de lista, seleção, emoji) e o que anima fora de `seek(t)` (SMIL, laço por mensagem, imagem animada, mais relógios e sorteios; checagem de quietude — §9, §11); e a moldura quebra e encolhe rótulo e sub para caberem (§8.1). A 1.6.0 fechou o escopo final da operação: a **conferência final** (camada C5) deixou de ser uma skill e virou comando do kit — `da conferencia` (§2, §18), que compõe `validar`, `lint --estrito`, `conferir-carimbo --exigir-aprovada`, loudness e limites de plataforma, chama por posição as conferências das skills irmãs e grava `qa/relatorio.json`, o portão de publicação; não existe skill de QA nem de thumbnail (a thumbnail sai direto pelo kit, §17.1), e o mapa do §17 ganhou a video-pauta-midia. Receita completa de legendas queimadas no §16 e o mapa "qual chamada serve a qual skill" no §17.

Leia este arquivo quando for **escrever ou corrigir uma skill que produz imagem ou vídeo** (video-broll, video-pauta-midia, video-animacao-explicativa, video-legendas, video-cortes-verticais, e as antigas video-motion-graphics / video-animacao-audio quando forem adaptadas), for fazer uma thumbnail direto pelo kit (§17.1) ou for ligar a sua skill à conferência final (video-publicacao e quem mais lê `qa/relatorio.json`: §18). Para entender o significado de cada token, leia `tokens.md`; para o método de construir uma DA, `metodo-da.md`.

## 0. Localizar o kit a partir de outra skill

As skills são instaladas lado a lado em `"$CRIABR_SKILLS"/<nome>/`. Um script em `<skills>/video-legendas/scripts/legendar.py` acha o kit **por posição relativa**, nunca por caminho absoluto embutido (a área de montagem muda, a instalação final não):

```python
from pathlib import Path
import sys
KIT = Path(__file__).resolve().parents[2] / "video-direcao-de-arte" / "kit"   # <skills>/video-direcao-de-arte/kit
if not (KIT / "da.py").is_file():
    KIT = Path(os.environ["CRIABR_SKILLS"] + "/video-direcao-de-arte/kit").expanduser()       # fallback quando o script roda fora da árvore
sys.path.insert(0, str(KIT))
import da, texto, video, trava
```

Em Node: `const KIT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../video-direcao-de-arte/kit')`. Em shell (SKILL.md, CLAUDE.md, instruções ao usuário), a linha de comando é sempre a chamada direta do executável:

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da <subcomando> [opções]     # zsh, bash e sh; espaço no caminho; acha sozinho um Python 3.10+ com Pillow
```

Não escreva `DA="python3 ~/…/da.py"; $DA …` na sua skill: em zsh a variável não é dividida em palavras (código 127) e, em bash, o til entre aspas não expande (código 2, o mesmo de "sem DA"). `kit/bin/da` escolhe o Python nesta ordem — `VIDEO_OPS_PYTHON` (sem conferir), `python`, `/usr/local/bin/python3`, `python3` do `PATH`, `/usr/bin/python3` — e sai com **127** se nenhum servir. Se a instalação perder o bit de execução do arquivo (o shell responde `permission denied`, código 126), `chmod +x …/kit/bin/da` resolve; `sh …/kit/bin/da <subcomando>` funciona mesmo sem o bit. Scripts Python da sua skill usam `#!/usr/bin/env python3` só se o ambiente garantir Pillow; na dúvida, rode-os com o mesmo intérprete (`python`).

Importar o kit liga `sys.dont_write_bytecode` no seu processo e apaga `kit/__pycache__/`: a skill instalada não acumula `.pyc` (faça o mesmo nos seus scripts se quiser a sua pasta limpa).

Dependências: Python 3 com Pillow e numpy (nada de pip), Node 18+ (o kit acha em `VIDEO_OPS_NODE`, `PATH`, `~/.nvm/versions/node/*/bin/node`), `playwright-core` já dentro de `kit/node_modules/`, Chromium headless shell em `~/Library/Caches/ms-playwright/chromium_headless_shell-*` (ou `VIDEO_OPS_CHROME`), ffmpeg/ffprobe no `PATH` ou em `/opt/homebrew/bin`.

## 1. Texto-padrão da seção "Passo 0 — Direção de arte"

Toda skill visual começa por esta seção (copie e adapte os exemplos à sua saída):

> ### Passo 0 — Direção de arte
> 1. **Ache a DA**: `"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da achar --json` a partir da pasta do projeto (ou `da.carregar()` em Python). Código de saída 2 = não há `da/da.json`: **pare**, diga ao usuário que o projeto não tem direção de arte e chame a skill `video-direcao-de-arte` para criar uma. Nunca renderize com um visual improvisado "só para mostrar".
> 2. **Leia tokens, não invente**: cor (`d.cor("primaria")`, `var(--da-cor-primaria)`, `ctx.cor('primaria')`), fonte (`d.fonte_pil("legenda", px)`, `.da-legenda`, `ctx.texto('legenda', …)`), tamanhos (`d.px(d["legenda"]["tamanho"], "vertical")`, `ctx.tam('h1')`), curvas e durações (`d.facilitar("entrada")`, `d.dur("media")`, `ctx.prog(...)`), margens seguras (`d.margens("vertical", "uniao")`, `ctx.area_segura('uniao')`), tratamento (`d.grade("horizontal")`), loudness (`video.filtro_loudnorm(d, "longo")`), transições (`d.transicao()`), limites de plataforma (`da.limite("reels", "hashtags_max")`).
> 3. **Nenhuma cor ou fonte literal** em HTML/CSS/JS de cena, JSON de storyboard ou código Python que desenha (tupla RGB, hex, nome de cor, `ImageFont.truetype("…")`, `color=red` em filtro ffmpeg). Cor da DA com transparência tem uma forma só: `rgba(var(--da-cor-<nome>-rgb), a)` no CSS, `ctx.alfa(token, a)` em cena, `d.rgba(token, a)` em Python. Foto, logo de terceiros e captura de tela são a única exceção: `data-da-livre` no elemento ou comentário `da-livre` na linha (`# da-livre` em Python). Rode `da.py lint --estrito <suas peças e scripts>` antes de entregar: sem `--estrito`, arquivo que o lint não sabe ler aparece como `NÃO CONFERIDO` mas não reprova.
> 4. **Carimbe cada saída**: o motor, `da.py grade` e as funções de `video.py` que gravam peça (`compor_overlay`, `compor_cues`, `juntar`, `Codificador`) carimbam sozinhos; o que você gerar por PIL/ffmpeg próprio leva `d.carimbar(saida, ferramenta="<sua skill>", formato="vertical", parametros={…}, insumos=[peças que entraram])` (auditoria `n/a`: `ok` é o resultado do auditor do motor). Peça sem carimbo é reprovada pela conferência final (`da conferencia`, §18). Intermediário (quadro solto, PNG de cue, base recortada) mora em pasta ou arquivo de nome começado por `_` e não precisa de carimbo (§14).
> 5. **Pedido que contraria a DA** ("põe em vermelho"): não aplique na peça. Ofereça o token mais próximo ou uma nova revisão da DA (`da.py revisar` → editar → `aprovar`).
> 6. **Uma tarefa pesada por vez**: ffmpeg, Chromium e whisper sempre por `trava.rodar([...])` / `trava.py -- <cmd>` (ou `video.executar`, que já entra na fila). Nunca `subprocess.run` cru de um processo pesado: é o `rodar` que fecha o stdin, mata a árvore em SIGTERM e vigia a inatividade.

## 2. CLI `da.py` (núcleo + extensão do motor)

`<kit>/bin/da [--da CAMINHO] [--de PASTA] <subcomando> …` (o executável; equivale a `python3 <kit>/da.py …` com um Python que tenha Pillow — nas tabelas abaixo, "`da.py x`" — ou só "`da x`" — é o nome do subcomando). Códigos de saída: **0** ok · **1** reprovado/erro · **2** nenhuma DA · **64** uso incorreto · **75** desistiu de esperar a trava (`--espera-max`) · **124** comando morto pelo vigia de inatividade · **127** `bin/da` não achou Python utilizável ou o `da.py` · **128+N** interrompido pelo sinal N (143 = SIGTERM; os filhos já estão mortos e a trava solta). Defeito interno sai em uma linha (`erro interno: Tipo: mensagem`, código 1); `DA_DEBUG=1` mostra o traceback. Ordem de descoberta da DA: `--da` > variável `DA_JSON` > `da/da.json` na pasta atual (ou `--de`) ou em qualquer pasta acima.

| subcomando | o que faz (e o que foi observado) |
|---|---|
| `init <pasta> --nome "…" [--base preset] [--herdar] [--forcar]` | Cria `CLAUDE.md` (bloco `<!-- DA:INICIO -->…<!-- DA:FIM -->`), `da/` com `da.json` copiado do preset (`--herdar` grava só `{"herda": "<preset>", "projeto": {…}}`, 14 linhas), copia as fontes do preset para `da/fontes/` e a licença de cada uma para `da/fontes/LICENCAS/`, cria as 12 pastas de trabalho (e, dentro de `broll/`, as subpastas `bruto/` e `tratado/` — §14). Reexecutar não sobrescreve nada ("nada foi sobrescrito"; bloco do CLAUDE.md inalterado). 0,13 s. `--forcar` recria o `da.json` (o anterior vira `da.json.bak-<data>`); sem `--base`, a partir da **mesma base** da DA existente (`projeto.base` ou `herda`), com aviso. Bloco do CLAUDE.md: os delimitadores só valem quando ocupam a linha inteira (menção em prosa não conta) e tem de haver exatamente um par — senão, erro e nada muda; antes de regravar um CLAUDE.md existente o `init` guarda `CLAUDE.md.bak-<data>`. Nome, preset e delimitadores do CLAUDE.md são conferidos **antes** de criar qualquer coisa: um `init` que falha (preset inexistente, `--nome` faltando, CLAUDE.md com um delimitador só, caminho que é um arquivo) não deixa pasta nem troca o `da.json`. |
| `achar [--raiz\|--build\|--json]` | Caminho do `da.json`; `--json` → `{"da_json", "raiz", "build"}`. Sem DA: mensagem com o comando de `init` sugerido e código 2. |
| `validar [arquivo] [--estrito] [--json]` | Esquema + semântica. Observado reprovando: `cor.dados` com < 6 cores, enum inválido (`entrada_padrao: "quica"`), `legenda.tamanho` acima do máximo, arquivo de fonte inexistente, contraste texto×fundo e texto×superficie < 3:1, legenda×fundo < 3:1. Avisos: legenda que sai da zona segura na vertical (com `max_linhas`) **ou na horizontal** (`legenda.largura_max = 0,8: no vertical a zona segura 'uniao' só deixa 0,611 da largura … declare legenda.posicao.vertical.largura_max ≤ 0,61`; `legenda.posicao.vertical.x` que põe o bloco para fora), "DA ALTERADA DEPOIS DA APROVAÇÃO"; **legenda × GC** nos formatos de `legenda.reservar_em` (`legenda × GC no vertical: a faixa da legenda (6 linha(s) a 130 px, de y 326 a 1220 px) deixa 25 px livres na zona segura 'uniao' e o GC precisa de ≈ 127 px — os dois se sobrepõem`) e, nos formatos **fora** dela, quando o GC (na zona inteira, onde a produção o põe) e a faixa da legenda se tocam — aviso no vertical e no quadrado (`legenda × GC no vertical: "vertical" não está em legenda.reservar_em e o GC (…) e a faixa da legenda (…) se sobrepõem`); **texto abaixo do mínimo legível** em `graficos.gc.tamanho_cargo`, `graficos.citacao_fonte.tamanho` e `tipografia.escala.nota` (< 0,022 do lado menor) e em `legenda.tamanho` (< 0,04), com o tamanho em pt num celular; GC estilo `linha` com `protecao: "nenhuma"` e texto do GC com menos de 3:1 contra o próprio apoio; e **incoerência depois de trocar uma cor** — duas cores da paleta quase idênticas (`primaria #FF2D95 e secundaria #FF2E93 são quase idênticas (ΔE 1,3)`), hex de `cor.dados` que é quase uma cor da paleta (`escreva "primaria" no lugar do hex`), dois itens de `cor.dados` que resolvem para a mesma cor e gradiente com todas as paradas iguais. `--estrito` faz avisos reprovarem. **Notas** (`NOTAS (n) — não reprovam, mas leia`; `notas` no `--json`) dizem o que a DA entrega sem ser defeito — hoje, uma: `horizontal sem reserva de legenda: "horizontal" não está em legenda.reservar_em, então o GC (inferior esquerda, y 872 a 1026 px) e a faixa da legenda (y 798 a 937 px) ocupam o mesmo lugar e as cenas não desviam. Tudo certo se o vídeo horizontal NÃO leva legenda queimada … Se levar, inclua "horizontal" em legenda.reservar_em` (neon-shorts; os 5 presets saem com `Sem erros nem avisos.` e essa nota). Nota não reprova nem com `--estrito`; `aprovar` também a imprime. |
| `compilar [--se-preciso] [--json]` | Gera `da/build/{da.resolvida.json, da.css, da.js, grade.json, da.lock}` e `da/DA.md` (0,12 s). `--se-preciso` só recompila se o lock estiver velho (edição do `da.json`, de um ancestral, de fonte/LUT/logo, ou atualização do kit). |
| `mostrar` | Resumo no terminal: paleta com contraste sobre o fundo, papéis, escala, movimento, cadeia ffmpeg, legenda, formatos. |
| `token <caminho> [--bruto] [--formato NOME]` | `cor.paleta.primaria` → `#38E1FF`; `legenda.cor` → hex resolvido, `--bruto` → `texto`; `cor.dados.1` → 2ª cor; `legenda.tamanho --formato vertical` → `56` (px do lado menor); objetos saem em JSON. Erro com sugestão ("Quis dizer 'primaria'?") e código 1. |
| `presets [--json]` | Embutidos (`dossie`, `editorial-claro`, `lab-ia`, `neon-shorts`, `quadro-negro`) e pessoais (`$VIDEO_OPS_HOME/da-presets/`, padrão `~/.config/video-ops/da-presets/`), cada um com a frase de conceito. |
| `salvar-preset <nome> [--forcar]` | Grava a DA resolvida do projeto + fontes/LUTs/texturas/logos em `da-presets/<nome>/`. Usar depois com `init --base <nome>` ou `"herda": "<nome>"`. |
| `extrair <imagens/vídeos/pastas…> [--quadros N] [--cores 6-8] [--regiao X,Y,L,A] [--saida PASTA] [--json]` | Analisa referências (vídeo é amostrado por ffmpeg sob a trava; uma **pasta** vale pelas imagens e vídeos dentro dela): paleta k-means em Lab com área e croma, **acentos** (cores vivas — croma ≥ 45 — mesmo em área pequena, a partir de 0,3 % da imagem; de cada família de matiz, a cor dos pixels mais puros, sem a borda suavizada), L* médio/p5/p95, saturação, temperatura (b*), grão (sigma → `grao.intensidade` sugerida) e **candidatos a token** (fundo, texto, primaria, superficie) com o motivo. A `primaria` proposta é o acento mais presente, com o contraste contra o fundo informado e nunca usado como filtro (cartela preta com um marca-texto de 0,7 % da área → `primaria #F9C914 — acento: a cor viva mais presente (croma 82, 0,73% da área; contraste 12,3:1 com o fundo)`); sem acento nenhum (footage de gente), o motivo diz `NENHUMA cor de acento nas referências … pode ser pele, madeira ou luz ambiente`. `--regiao 0.08,0.38,0.2,0.05` (frações do quadro) analisa só um recorte — para amostrar a cor de um detalhe. Grava `referencias_analise.json` e `referencias_folha.png` em `da/referencias/` — e ignora esses dois arquivos quando vêm na lista (o glob `da/referencias/*.png` da segunda execução traz a folha de volta; sai `1 ignorada(s)` e a paleta não muda). `--cores` fora de 6–8 ou `--quadros` fora de 1–24 é erro de uso (64). 1 imagem 1080p + 2 quadros de vídeo: 0,9 s. |
| `aprovar [--estrito] [--sem-prancha]` | Grava `aprovada=true`, `aprovada_em`, `aprovada_sha256`, recompila. Recusa (código 1) se a DA foi editada depois de aprovada: "Abra uma nova revisão com `da.py revisar`". Idempotente. Antes de aprovar confere os documentos que o cliente viu — `da/prancha.png`, `da/prancha_vertical.png`, `da/teste_movimento.mp4` — pelo sha do carimbo: sem nenhuma prancha em dia ou com o teste de movimento ausente/desatualizado, **avisa** (`! nenhuma prancha em dia — o que o cliente aprovou não é o que está em disco`); com `--estrito`, recusa (código 1, `a DA NÃO foi aprovada`). Depois de aprovar, regenera as pranchas que estavam em dia (mesmo quadro de referência, mesma escala) para o cabeçalho passar de `RASCUNHO — AGUARDANDO APROVAÇÃO` a `APROVADA EM dd/mm/aaaa` (`--sem-prancha` desliga; sem prancha em disco, nada é renderizado). |
| `rotas criar <nome> [--base PRESET\|ARQ\|atual] [--frase "…"] [--primaria #hex] [--cor chave=#hex]… [--forcar]` | Cria uma DA candidata em `da/rotas/<nome>/da/da.json`, herdando de um preset (ou da DA atual do projeto, o padrão) e sobrescrevendo só `conceito.frase` e as cores pedidas; valida na hora e imprime os avisos (é aqui que a troca de cor incoerente aparece). Não cria pastas de trabalho: a rota enxerga `da/referencias`, `bruto/` e `broll/` do projeto-pai (prancha, teste de movimento e `conceito.referencias`). Preset inexistente, nome inválido ou rota que já existe: erro, nada é criado. |
| `rotas listar [--json]` | Uma rota por bloco: de quem herda, primária e fundo, estado da validação, frase, e se a prancha (vertical/horizontal) e o teste de movimento estão `em dia`, `desatualizada` ou `ausente`. Funciona da raiz do projeto ou de dentro de uma rota. |
| `rotas comparar [nomes…] [--formato vertical\|horizontal] [--com-atual] [--largura PX] [--movimento] [--regerar] [--saida ARQ]` | Pranchas **lado a lado**, na mesma escala e alinhadas por seção (o mapa de seções vem do carimbo de cada prancha) em `da/rotas/comparacao_<formato>.png`; gera as pranchas que faltam ou estão desatualizadas. Padrão: todas as rotas, vertical, 720 px por coluna (960 no horizontal); `--com-atual` põe a DA do projeto na primeira coluna; `--movimento` gera também `da/rotas/comparacao_movimento.mp4` (os testes de movimento lado a lado, cada um parado no último quadro até o mais longo acabar). Medido: 4 colunas (atual + 3 rotas) → 2960×5809 em 10,3 s, com 3 pranchas geradas na hora. A folha não é peça (mistura DAs): não leva carimbo. |
| `rotas adotar <nome>` | A rota vira a DA do projeto **sem passar pela biblioteca pessoal**: grava `da/da.json` com a herança aplicada, copia para `da/` as fontes/LUTs/logos que ela usa (com as licenças), guarda `da.json.bak-<data>`, atualiza o bloco do CLAUDE.md e recompila. Nome, slug, data de criação e `conceito.referencias` do projeto ficam; a aprovação é zerada e a revisão sobe 1 se a DA anterior estava aprovada; `projeto.rota_adotada` registra a origem. O sha passa a ser o da rota (a identidade não inclui `projeto.*`). Avisa as fontes que sobraram em `da/fontes/` sem uso (`! 2 fonte(s) … que a DA não usa mais`) — não apaga. |
| `remover-preset <nome>` | Apaga um preset da biblioteca **pessoal** (`$VIDEO_OPS_HOME/da-presets/<nome>/`); embutido é recusado (código 1). |
| `revisar` | `revisao` +1, zera a aprovação. Não muda o sha (`projeto.*` está fora da identidade — §7). |
| `plataformas [nome] [--chave CHAVE] [--json]` | Limites e specs de `kit/plataformas.json` com os nomes canônicos `youtube`, `shorts`, `reels`, `tiktok` (apelidos valem: `instagram`, `yt`, `tt`…). Sem nome: uma linha por plataforma (título, texto, hashtags, duração, tamanho, proporção) e a data de verificação; `plataformas reels --chave hashtags_max` → `5` (código 1 se o valor não existe); `--json` → a ficha de `da.plataforma(nome)`. Não precisa de DA. |
| `lint [caminhos…] [--estrito] [--json]` | Reprova cor literal (hex, `rgb()/hsl()/…`, nomes CSS) e `font-family` literal em `.html .htm .css .js .mjs .cjs .json .svg` e, em `.py`, tupla RGB(A), hex, nome de cor, cor em filtro ffmpeg e fonte por caminho literal (§12). Padrão sem caminhos: `animacoes legendas cortes thumbs render`. Cada achado vem com linha:coluna, regra e **o token mais próximo com ΔE**. Aviso (não erro) para `transition`/`animation` CSS. O que foi pedido e o lint não leu sai como `NÃO CONFERIDO  <arquivo> — <motivo>` e **não** entra na contagem de conferidos: arquivo passado pelo nome com outra extensão, fonte de peça em linguagem não coberta dentro de uma pasta (`.ts .scss .sh .swift`…), Python com erro de sintaxe, arquivo > 2 MB. `--estrito` (o modo da conferência final) reprova com aviso **ou** com não conferido. Com 0 arquivos lidos a última linha diz `Nada foi lido: isto não é um sinal verde`. Ignora `node_modules`, `build`, `da.resolvida.json`, `package.json` e, **ao varrer pastas**, tudo cujo nome começa por `_` (intermediários — §14; sai uma nota `N intermediário(s) com prefixo _ fora do lint`; passado pelo nome, o arquivo é lido). |
| `carimbar <saida> --ferramenta X [--formato F] [--parametros JSON\|@arq] [--auditoria ok\|pulada\|n/a] [--sha-esperado SHA] [--origem ARQ] [--insumo ARQ]…` | Grava `<saida>.da.json` (ver §7). Exige que a saída exista. `--insumo` (repetível) registra as peças que entraram na composição: a auditoria gravada é a pior entre a pedida e as delas (avisa `auditoria gravada como "pulada": um insumo foi renderizado com --sem-auditoria`). `n/a` (padrão) é o valor de toda peça que não passa pelo motor; `ok`/`pulada` são gravados pelo motor. **Nunca promove**: se a peça já tem carimbo `pulada` e o arquivo é o mesmo, pedir `ok` ou `n/a` sai com código 1 (`o carimbo continua "pulada"`) e nada é regravado — só um render novo com o auditor ligado limpa. `--sha-esperado` = identidade da DA com que a peça foi desenhada: se a DA atual for outra, recusa com código 1 e não grava. `--origem` = arquivo provisório (o `.parcial`) que ainda será renomeado para `<saida>`. Avisa no stderr quando a DA foi alterada depois da aprovação. |
| `conferir-carimbo [caminhos…] [--exigir-aprovada] [--json]` | Estados: `ok`, `SEM CARIMBO`, `CARIMBO ILEGÍVEL`, `DA DIFERENTE` (sha ≠ atual, com as duas revisões na mensagem), `AUDITORIA PULADA` (da peça **ou de um insumo dela**: `insumo(s) renderizado(s) com --sem-auditoria: gc.webm`), **`INSUMO DE OUTRA DA`** (composição feita com peça de outra identidade), `ARQUIVO ALTERADO` (regravado depois do carimbo), **`DA ALTERADA APÓS APROVAÇÃO`** (o `da.json` foi editado depois do `aprovar`: reprova todas as peças até `revisar` + `aprovar`) e, só com `--exigir-aprovada` (é como a conferência final chama), **`DA NÃO APROVADA`**. O detalhe de cada peça lista os elementos `data-da-livre` dela (e o `--json` traz `pecas[].livres`). Sem caminhos varre `animacoes legendas cortes thumbs render` e `broll/tratado` (não `broll/bruto`, que é material baixado). Ignora `<saida>.parcial`, `<nome>.parcial.<ext>`, o `da/build/` e toda pasta ou arquivo de nome começado por `_` (intermediários — §14; passado pelo nome, o arquivo é conferido). Caminho fora da pasta atual sai absoluto. Código 1 se alguma reprovar. |
| `grade [--formato F] [--parte completa\|cor\|acabamento] [--verificar] [--json]` | Imprime a cadeia ffmpeg do tratamento; `F` é um formato da DA ou `LxA` (`--formato 640x360`, igual a `d.grade(640, 360)`). `--verificar` confere se este ffmpeg tem todos os filtros. |
| `grade --entrada ARQ --saida ARQ [--inicio S] [--duracao S] [--crf 18]` | Aplica a cadeia (ffmpeg sob a trava; encode da casa: H.264 yuv420p marcado bt709, preset medium, `-threads 2`, **fps da fonte preservado** em forma racional — tratar não muda a cadência) e carimba com `ferramenta: da.py grade` e a proveniência da entrada (tratar uma peça `pulada` dá uma peça `pulada`). |
| `conferencia [ALVO…] [--corte ARQ\|NOME]… [--plataforma NOME]… [--previa] [--saida PASTA\|ARQ.json] [--json]` | A **conferência final** do projeto (camada C5), compondo o que as linhas acima já fazem — nenhuma validação própria: `validar` sem erros + DA aprovada e não alterada depois da aprovação, `lint --estrito` nas pastas de peças, `conferir-carimbo --exigir-aprovada` (com `broll/tratado` e os insumos carimbados das composições), `video.conferir_loudness` de `render/final.mp4` (`som.loudness.longo`) e de `cortes/*.mp4` (`som.loudness.curto`), duração/orientação/resolução/tamanho/fps de cada entregável contra `da.plataforma(nome)`, e — se o projeto tiver — a ficha de fatos (`fatos.py validar --estrito`, `conferir-roteiro --estrito`, `conferir-storyboard` da video-pesquisa-ia, chamados por posição) e os créditos de `broll/licencas.json` em `broll/creditos.md`. Grava `qa/relatorio.json` no contrato do §18 e `qa/relatorio.md`; imprime o resumo (`--json`: o relatório). `ALVO…` e `--corte` restringem carimbo, loudness e técnica aos arquivos pedidos (`--corte K01` = um corte só, sempre peça curta); `--previa` rebaixa "DA não aprovada" a aviso e grava `qa/previa.json`. Não renderiza nada. Códigos: 0 ok · 1 há erro · 2 sem DA · 64 alvo inexistente, fora do projeto ou plataforma desconhecida. Tudo no §18. |
| `prancha [--formato horizontal\|vertical\|ambos] [--referencia ARQ] [--foto ARQ] [--saida PASTA] [--escala F] [--sem-auditoria]` | `da/prancha.png` (1920×~7 000) e `da/prancha_vertical.png` (1080×~7 800), carimbadas. Seções: [referências do conceito, se houver imagens em `conceito.referencias`] · paleta · tipografia · componentes · **em escala 1:1** · tratamento · dados e movimento · margens (só na vertical) · thumbnail e regras. A amostra de **legenda é o PNG de `texto.estados_da_legenda`** (o caminho da produção; `da/build/prancha/legenda_<formato>.png`), posta sobre o quadro do projeto, e a seção 1:1 mostra GC e legenda sem redução (com a prancha na largura da tela do celular, é o tamanho real no vídeo). **O GC da prancha é o da produção** (`reservar_legenda: null`, sem parâmetro de posição): nos formatos de `legenda.reservar_em` (vertical e quadrado, por padrão) ele desvia da faixa da legenda e os dois aparecem juntos; onde a DA não reserva e os dois ocupam a mesma faixa (o horizontal padrão), o quadro de componentes traz só o GC, na base, e a seção 1:1 traz **duas tiras** — o GC na posição da produção e a legenda sozinha — com a frase que diz como mudar. Até 1.5.0 a prancha horizontal forçava a reserva e mostrava o GC ~200 px acima de onde a cena `gc` o punha. O quadro de referência (fundo das amostras e antes/depois) é procurado primeiro em footage — `bruto/`, `broll/bruto/`, `broll/tratado/`, `broll/` — e só depois em `da/referencias` (prints de design); numa rota, também no projeto-pai; `--referencia` escolhe; sem nada, um quadro sintético. `--foto` vale para o GC e para a thumbnail. O carimbo traz `parametros.layout.mapa` (`[{n, titulo, y, h}]` das seções, em px de layout) e `faixa_1x1` (`{gc, legenda, juntos, reservou_legenda, faixa_legenda, tiras: [{y0, y1, conteudo}]}`: a caixa `gc` é a mesma da cena `gc` renderizada no formato — há teste comparando). 6–8 s para as duas (3,1 s + 2,8 s no neon-shorts; eram 2–3,5 s antes da checagem de quietude). |
| `teste-movimento [--formato horizontal\|vertical\|quadrado] [--escala 0.5] [--dur S] [--atos titulo,gc,barras] [--referencia ARQ] [--saida ARQ] [--sem-auditoria]` | `da/teste_movimento.mp4` (960×540 por padrão) em três atos: cartela de título entra, respira e sai · GC sobre um quadro do projeto, **na posição da produção**; a legenda corre palavra a palavra junto com ele onde a DA reserva a faixa dela (vertical e quadrado, por padrão) ou onde os dois não se tocam — no horizontal padrão o ato mostra só o GC, e o `layout` do carimbo traz `gc_e_legenda_juntos: false` e `legenda_omitida` com o motivo · barras entram, contam até o valor final e ficam. Entre os atos, a transição padrão da DA. **A duração sai das durações da DA** (entrada completa + respiro de 0,7 s + saída, por ato): 4,66 s no `neon-shorts`, 6,71 s no `dossie`, 8,16 s no `editorial-claro`. `--dur` só estica ou encolhe os respiros (mínimo 0,2 s cada): pedir menos que o mínimo da DA devolve o mínimo, com aviso — nenhuma animação é cortada. `--atos gc` renderiza um ato só (≈ 2 s). Medido a 480×270: 6,7 s de peça em 12 s de parede. |
| `render <args do motor…>` | Repassa a `motor/render.mjs` já com `--da` (na frente dos seus argumentos) e sob a trava, em grupo de processos próprio. `da.py render --cena titulo --saida x.mp4 …` funciona sem `--`. Ajuda do motor: `da.py render -- --help` (não precisa de DA nem espera a fila). Erros de uso do motor atravessam com código 64 **sem esperar a fila**: com a trava ocupada, o `render` confere argumentos, cenas e params antes de entrar nela (medido com a trava presa por outro processo: `--params '{"titlo": …}'` → erro 64 em 0,7 s; antes esperava a fila inteira); `--validar` só confere e nunca entra na trava; `kill`/Ctrl-C no `da.py render` mata node, Chromium e ffmpeg e sai com 143/130. |

Em Python, as mesmas operações: `da.iniciar(pasta, nome, base, herdar, forcar)`, `da.achar(de, da, obrigatorio)`, `da.validar(caminho)` → `{erros, avisos, notas, …}`, `da.compilar_da(caminho)`, `da.precisa_compilar(da_json)` → `(bool, motivo)`, `da.listar_presets()`, `da.salvar_preset(nome)`, `da.extrair(refs, saida, quadros, cores, regiao=None)` → `{geral: {paleta, acentos, candidatos, leitura, …}, referencias, ignoradas}`, `da.aprovar()`, `da.documentos_de_aprovacao(caminho)` → `{"prancha.png": {arquivo, estado: "em dia"|"desatualizada"|"ausente", detalhe}, …}`, `da.revisar()`, `da.criar_rota(nome, base=None, frase=None, cores=None, caminho=None, forcar=False)`, `da.listar_rotas(caminho)`, `da.adotar_rota(nome, caminho)`, `da.caminho_da_rota(nome, caminho)`, `da.projeto_pai(da_json)` (raiz do projeto de uma rota, ou `None`), `da.remover_preset(nome)`, `da.fontes_orfas(da_json)`, `da.plataformas()`, `da.plataforma(nome)`, `da.limite(plataforma, chave)`, `da.nome_plataforma(apelido)` (§3), `da.lint(caminhos, estrito=False)` → `{ok, arquivos, erros, avisos, achados: […], nao_conferidos: [{arquivo, motivo}], notas}` (`arquivos` = quantos foram lidos; com `estrito=True`, aviso ou não conferido derruba o `ok`), `da.carimbar(saida, ferramenta, formato, parametros, auditoria, da=None, sha_esperado=None, origem=None, reauditada=False, insumos=None)` (`reauditada` é de uso do motor; `insumos` = caminhos das peças que entraram), `da.ler_carimbo(peca)` → dict ou `None`, `da.proveniencia(insumos)`, `da.conferir_carimbo(caminhos, exigir_aprovada=False)` → `{ok, da_aprovada, da_alterada_apos_aprovacao, pecas: [{arquivo, estado, detalhe, livres, insumos}]}`, `da.aplicar_grade(entrada, saida, …)`, `da.licenca_da_fonte(arquivo)` → `Path` da licença que acompanha a fonte (ou `None`), `da.e_saida_do_extrair(caminho)`, `da.identidade(fundida, bases)`. Constantes úteis: `da.DA_CLI` (a chamada `~/…/kit/bin/da`, para mensagens), `da.EXT_LINT`, `da.FORA_DA_IDENTIDADE`, `da.PREFIXOS_LIVRES`, `da.PLATAFORMAS`, `da.TRANSICOES`, `da.PASTAS_COM_PECAS`, `da.PREFIXO_INTERMEDIARIO`, `da.MINIMO_LEGIVEL` (0,022), `da.MINIMO_LEGENDA` (0,04), `da.RESERVA_PADRAO` (`("vertical", "quadrado")`), `da.FOLGA_DA_LEGENDA` (0,012), `da.DOCUMENTOS_DE_APROVACAO`, `da.APOS_APROVAR` (lista de ganchos `fn(da_json, documentos, args)` que rodam depois do `aprovar` da CLI — é por onde a extensão do motor regenera a prancha). Na extensão do motor (`import da_ext_motor as motor`): `motor.gerar_prancha(d, formatos, referencia=None, foto=None, escala=1.0, reaproveitar=False)`, `motor.gerar_teste_de_movimento(d, formato, escala, dur, saida, atos, referencia)` → `(resultado, saida, plano)`, `motor.duracao_do_teste(d, atos=None, pedida=None)` → `{total, natural, minima, respiro, atos}`, `motor.comparar_rotas(nomes, formato, com_atual, largura, saida, regerar, caminho, movimento)`, `motor.achar_referencia(d)`, `motor.referencia_tratada(d, referencia)` → `{antes, depois, origem}`, `motor.legenda_de_amostra(d, formato, destino)`. Na extensão da conferência (`import da_ext_conferencia as conferencia`): `conferencia.conferir(caminho=None, de=None, alvos=None, cortes=None, plataformas=None, previa=False, saida=None, gravar=True)` → o relatório (dict no contrato, com `.json`, `.md`, `.raiz`, `.entregaveis` em atributos), `conferencia.listar_entregaveis(raiz, alvos, cortes, plataformas)`, `conferencia.caminhos_do_relatorio(raiz, saida, previa)`, `conferencia.texto_resumo(rel)`, `conferencia.texto_md(rel)` (§18). Exceções: `da.SemDA` (código 2), `da.DAInvalida` (erros de validação), `da.DAErro` (mensagem + `dica` + `codigo`).

## 3. API Python — `da.py`

```python
d = da.carregar()                        # acha da/da.json a partir do cwd; recompila build/ se velho; levanta SemDA (2) / DAInvalida
d = da.carregar("/caminho/projeto")      # equivale a --da (da.json ou pasta do projeto)
d = da.carregar(de="/pasta/dentro/do/projeto")     # equivale a --de
d = da.carregar(compilar=False)          # resolve só em memória, sem tocar em da/build/
```

`d` é um `dict` com o mesmo conteúdo de `da/build/da.resolvida.json` mais atalhos. Saídas observadas (preset lab-ia, projeto de teste):

| chamada | devolve |
|---|---|
| `d.raiz`, `d.caminho`, `d.pasta`, `d.build`, `d.css`, `d.js` | `Path`s: raiz do projeto, `da.json`, `da/`, `da/build/`, `da.css`, `da.js` |
| `d.sha256`, `d.revisao`, `d.aprovada`, `d.meta` | `"eb7fad0a…"`, `2`, `True` (False se foi alterada depois da aprovação), dict `_meta` (`nome`, `slug`, `aprovada_em`, `alterada_apos_aprovacao`, `ancestrais`, `compilado_em`, `kit_versao`) |
| `d.cor("primaria")`, `d.cor("dado-2")`, `d.cor("neutro-1")`, `d.cor("#07090D")` | `"#38E1FF"`, `"#9D7BFF"`, `"#000000"`, o próprio hex normalizado. Token inexistente → `DAErro` listando os nomes válidos |
| `d.rgb("fundo")`, `d.rgba("texto", 0.5)` | `(7, 9, 13)`, `(230, 237, 243, 128)` — prontos para o PIL |
| `d.contraste("texto", "fundo")` | `16.9` (razão WCAG) |
| `d.fonte("legenda")` | dict do papel + `caminho` absoluto (ou `None` = fonte do sistema), `variavel`, `eixos_efetivos` (`{'wght': 800, 'wdth': 88}`), `eixos_ordem`, `css_familia`, `css_variacao` |
| `d.fonte_pil("legenda", 56)` | `ImageFont.FreeTypeFont` já com os eixos variáveis aplicados; `DAErro` se o papel usa fonte do sistema |
| `d.texto("subtitulo", "ação")` | `"AÇÃO"` quando o papel tem `caixa: alta`; senão inalterado |
| `d.formato("vertical")` | `(1080, 1920, Fraction(30000, 1001))`; thumbnail devolve fps `None` |
| `d.dimensoes("vertical")`, `d.dimensoes("540x960")`, `d.dimensoes(320, 180)` | `(1080, 1920)`, `(540, 960)`, `(320, 180)` — o que um script recebe em `--formato` (nome da DA ou `LxA`) vira largura e altura; formato inexistente é `DAErro` com sugestão |
| `d.px(0.058, "vertical")`, `d.px(0.058, 960, 540)` | `63`, `31` — fração do **lado menor** → px inteiros |
| `d.margens("vertical")` | `{'topo': 288, 'direita': 300, 'base': 672, 'esquerda': 120, 'x0': 120, 'y0': 288, 'x1': 780, 'y1': 1248, 'largura': 660, 'altura': 960, 'plataforma': 'uniao'}` (teto com folga de 0,1 px: 0,2778 × 1080 = 300,02 é 300 — igual a `plataformas.json` e a `ctx.margens()`); `d.margens("vertical", "tiktok")`, `d.margens("horizontal")` (padrão `padrao`), `d.margens("vertical", largura=540, altura=960)`. A plataforma aceita nome canônico ou apelido — `d.margens("vertical", "reels")` é a zona `instagram` do `da.json` — e zona que só existe em outro formato cai no padrão deste: `d.margens("horizontal", "uniao")["plataforma"]` → `'padrao'` (o mesmo roteiro serve aos dois formatos); nome inexistente (`"kwai"`) é `DAErro` |
| `d.faixa_legenda("vertical")`, `d.faixa_legenda("540x960")`, `d.faixa_legenda("vertical", "shorts")` | `{'x0': 120.6, 'y0': 1071.34, 'x1': 779.4, 'y1': 1238.01, 'linhas': 2, 'tamanho': 66.96, 'formato': 'vertical'}` (dossie) — a faixa que a legenda da DA pode ocupar no **pior caso**: `legenda.max_linhas` linhas (1 no estilo `palavra`) no tamanho pedido, na largura máxima, com contorno ou caixa e a sombra para baixo, dentro da zona segura. É a mesma conta de `ctx.faixa_legenda()` no motor (diferença ≤ 0,6 px no teste) |
| `d.area_livre("vertical")`, `d.area_livre("horizontal")`, `d.area_livre("horizontal", legenda=True)`, `d.area_livre(largura=540, altura=960)` | A zona segura **menos a faixa da legenda**: onde GC, título, gráfico, crédito e assinatura ficam sem encostar na legenda queimada. Mesmas chaves de `margens()` + `reservou`, `faixa_legenda`, `lado` (`'acima'`/`'abaixo'`: fica com o lado maior). Dossie vertical: `{'x0': 120, 'y0': 288, 'x1': 780, 'y1': 1058, 'largura': 660, 'altura': 770, 'reservou': True, 'lado': 'acima', …}` (a zona `uniao` vai até 1248). `legenda`: `True` reserva sempre, `False` nunca, `None` (padrão) segue `legenda.reservar_em` da DA — por padrão `["vertical", "quadrado"]`, por isso `d.area_livre("horizontal")["reservou"]` é `False`; `"thumbnail"` nunca reserva. Skill em PIL que desenha qualquer coisa além da legenda no vertical usa esta área, não `margens()` |
| `d.legenda_reservada("horizontal")`, `d.legenda_reservada("vertical")`, `d.legenda_reservada("540x960")` | `False`, `True`, `True` (5 presets) — as peças deste formato **desviam** da faixa da legenda? Onde é `False`, GC, crédito e gráficos ficam na zona inteira e ocupam a faixa: quem vai queimar legenda ali (video-legendas, video-cortes-verticais) confere antes e, se a peça tem GC ou crédito no ar, pede `"horizontal"` em `legenda.reservar_em` (nova revisão da DA + peças refeitas) em vez de queimar por cima. A mesma resposta vem em `info["faixa_reservada"]` de `texto.compor_legenda`/`estados_da_legenda` (§4) |
| `d.zona_proibida()`, `d.zona_proibida("thumbnail")`, `d.zona_proibida(1920, 1080)` | `thumbnail.zona_proibida` como retângulo: `{'x': 0.75, 'y': 0.78, 'w': 0.25, 'h': 0.22}` (frações) e `{'x0': 960, 'y0': 562, 'x1': 1280, 'y1': 720, 'largura': 320, 'altura': 158, 'canto': 'inferior_direita'}` (px); `None` quando é `nenhuma`. O tamanho é `thumbnail.zona_proibida_tamanho` (padrão `[0.25, 0.22]`, a reserva do selo de duração em `plataformas.json`) |
| `d.transicao()`, `d.transicao("fade")` | `{'tipo': 'corte', 'duracao': 0.0, 'permitidas': ['corte', 'mascara', 'fade']}` — `duracao` = 0 no corte, `movimento.duracoes.media` nas demais; tipo fora de `movimento.transicoes.permitidas` é `DAErro` |
| `d.curva("entrada")`, `d.facilitar("entrada")(0.5)`, `d.dur("media")` | `(0.16, 1, 0.3, 1)`, `0.972`, `0.36` — a curva vira função pura p(x) para animar em Python |
| `d.grade("horizontal")`, `d.grade(640, 360, parte="cor")`, `d.grade("640x360")` | cadeia ffmpeg pronta para `-vf` (`"null"` quando tudo é neutro); `parte` = `completa`/`cor`/`acabamento` |
| `d.token("legenda.cor")`, `d.token("legenda.cor", resolver_cores=False)`, `d.token("cor.dados.0")` | `"#E6EDF3"`, `"texto"`, 1ª cor da série (sempre hex: no `da.json`, um item de `cor.dados` pode ser o **nome** de uma cor da paleta — `"primaria"` — e a série acompanha a paleta; o nome escrito fica em `d["cor"]["dados_tokens"][i]`, `None` quando o item é hex) |
| `d["legenda"]["tamanho"]`, `d["som"]["loudness"]["longo"]`, `d["tratamento"]["moldura"]["cor_hex"]` | acesso direto ao dict; campos de cor têm o irmão `<chave>_hex` já resolvido; arquivos têm `<chave>_abs` |
| `d.carimbar(saida, ferramenta, formato=None, parametros=None, auditoria="n/a", insumos=None)` | grava `<saida>.da.json` e devolve o `Path`; `insumos=[…]` registra a proveniência (§7). Como `d` foi carregado no início do seu script, o carimbo leva a identidade do **início** do trabalho (se o `da.json` mudar no meio, `conferir-carimbo` acusa `DA DIFERENTE`) |

Funções soltas úteis: `da.contraste(hexA, hexB)`, `da.delta_e(a, b)`, `da.pt_no_celular(fracao)` (fração do lado menor → pontos num celular de 390 pt de largura: `0.022` → `8.58`), `da.orientacao_de(largura, altura)`, `da.faixa_da_legenda(dados, L, A, zona)` e `da.area_livre_de(dados, L, A, zona, reservar)` (as contas de `d.faixa_legenda`/`d.area_livre` sobre um dict qualquer), `da.hex_do_item(item, d["cor"])`, `da.hex_para_rgb`, `da.rgb_para_hex`, `da.resolver_cor(valor, d["cor"])`, `da.nome_do_token(hex, d["cor"])`, `da.fps_racional("29.97")` → `Fraction(30000, 1001)` (aceita `"30000/1001"`, `"25"`, `29.97`, `"29.97"`, `"23,976"`; decimais NTSC viram N/1001), `da.sondar(arquivo)` (ffprobe curto), `da.ler_json`, `da.gravar_json`, `da.slugificar`.

**Plataformas** (não precisam de DA; leem `kit/plataformas.json`, cujas seções `specs`, `limites_texto`, `margens_seguras_vertical`, `capas` e `thumbnail` usam todas os nomes canônicos `youtube`, `shorts`, `reels`, `tiktok` — até 1.3.0 a mesma plataforma era `youtube_longo`, `instagram_reels` ou `instagram` conforme a seção):

| chamada | devolve (medido) |
|---|---|
| `da.plataformas()` | o JSON inteiro, em cópia (`verificado_em`, `plataformas`, `apelidos`, seções); mexer no dict devolvido não altera o kit |
| `da.nome_plataforma("instagram")`, `("IG")`, `("youtube_longo")`, `("tt")` | `'reels'`, `'reels'`, `'youtube'`, `'tiktok'`; nome desconhecido → `DAErro` com sugestão |
| `da.limite("reels", "hashtags_max")`, `da.limite("youtube", "titulo_max_caracteres")`, `da.limite("tiktok", "duracao_max_s")` | `5`, `100`, `3600` — procura em `limites_texto`, depois `specs`, `capas` e `thumbnail` (ou só em `grupo="specs"`); `None` = não encontrado em fonte confiável (não é zero nem "sem limite"). O Short herda do YouTube os campos de texto que a seção dele não traz (`da.limite("shorts", "hashtags_exibidas_junto_ao_titulo")` → `3`) |
| `da.limite("tiktok", "texto_max")`, `da.limite("reels", "tamanho_max_mb")` | `2200`, `300` — chaves **normalizadas**, iguais para as quatro: `titulo_max`, `texto_max` (descrição ou legenda), `hashtags_max`, `duracao_min_s`, `duracao_max_s`, `duracao_max_recomendada_s`, `tamanho_max_mb` (o menor teto publicado, GB convertido), `proporcao`, `resolucao_px`, `loudness_lufs`, `pico_real_dbtp` |
| `da.plataforma("reels")` | `{'nome': 'reels', 'texto': {…}, 'specs': {…}, 'margens': {'topo': 0.14, …}, 'capa': {…}, 'thumbnail': None, 'titulo_max': None, 'texto_max': 2200, 'hashtags_max': 5, 'duracao_min_s': 3, 'duracao_max_s': 1200, 'tamanho_max_mb': 300, 'proporcao': '9:16 (…)', …, 'verificado_em': '2026-10-05', 'idade_dias': 1, 'vencida': False}` — `vencida` = passou de `revalidar_a_cada_meses` |

No `da.json` a zona segura do Reels continua na chave `instagram` de `formatos.margens_seguras.vertical` (contrato do esquema v1); `d.margens`, `ctx.margens`, o tipo de parâmetro `plataforma` e `compor_legenda` aceitam os dois nomes.

## 4. API Python — `texto.py` (PIL fiel aos papéis e igual ao motor)

```python
L, A = 1080, 1920
est  = texto.Estilo.legenda(d, L, A)                 # bloco `legenda` inteiro: papel, tamanho, cor, contorno, sombra, fundo, caixa
dest = texto.Estilo.legenda(d, L, A, destaque=True)  # cor_destaque (palavra falada);  falada=True → cor_falada (já ditas)

# LEGENDA: várias linhas, sempre dentro da zona segura da plataforma (D11)
img, info = texto.compor_legenda(["dinheiro", "público", "desaparece"], [est, dest, est], d, L, A)
# → RGBA 1080×1920. Dossiê: info["linhas"] = [['DINHEIRO', 'PÚBLICO'], ['DESAPARECE']], info["caixa"] = (170.1, 1071, 729.02, 1232.31)
#   dentro da zona 'uniao' (x 120–780), centrada no RETÂNGULO da zona (x = 450), info["encolheu"] = False,
#   info["faixa_reservada"] = True (as cenas do kit desviam desta faixa no vertical; em 1920×1080 vem False — veja d.legenda_reservada, §3)
img, info = texto.compor_legenda(palavras, estilos, d, L, A, plataforma="tiktok", x=None, y=None, max_linhas=None,
                                 largura_max=None, linhas=None, recortar=False)
img, info = texto.desenhar_linha(["A", "conta", "que", "não"], [est, dest, est, est], d, L, A)    # compor_legenda com max_linhas=1
estados = texto.estados_da_legenda(["dinheiro", "público", "desaparece"], d, L, A, plataforma=None)   # [(imagem recortada, info), …]: os estados da cue
# conforme legenda.estilo — karaoke: um por palavra (bloco inteiro, palavra i acesa); palavra: um por palavra (só ela); bloco: um só. info["indice"], info["x"], info["y"]

# TEXTO de um papel e BLOCO palavra a palavra (thumbnail com palavra em destaque)
est2 = texto.Estilo.do_papel(d, "titulo", tamanho_px=d.px(d["tipografia"]["escala"]["h1"], L, A), cor="texto",
                             contorno=("fundo", 0.06), sombra={"dy": 0.04, "desfoque": 0.08, "alfa": 0.6}, alinhamento="centro")
bloco, info = texto.desenhar("A conta que não fecha: para onde vai o dinheiro", est2, largura_max=int(L * 0.84), max_linhas=2)
th, thd = texto.Estilo.thumbnail(d), texto.Estilo.thumbnail(d, destaque=True)                    # bloco `thumbnail` da DA
titulo, info = texto.compor_bloco(["A", "CONTA", "NÃO", "FECHA"], [th, th, th, thd], largura_max=700, max_linhas=3, alinhamento="esquerda")
credito, info = texto.credito_fonte(d, "IBGE, 2024", L, A, plataforma=None, recortar=True)       # graficos.citacao_fonte (igual a ctx.kit.credito):
# dentro da zona segura e FORA da faixa da legenda (d.area_livre) — no dossie vertical, info["caixa"] = (120, 1036, 383, 1058), acima da faixa
# que começa em y = 1071; reservar_legenda=True/False força, None segue legenda.reservar_em; plataforma="quadro" = sem zona

texto.quebrar_linhas("Como o dinheiro some no caminho até Brasília", est, 700)   # ['Como o dinheiro', 'some no caminho', 'até Brasília'] (sem palavra órfã na última linha)
texto.medir("Brasília", est)                       # {'largura', 'altura', 'linhas', 'tamanho'}
texto.encolher_ate_caber(s, est, largura_max, altura_max=None, max_linhas=None, minimo=10.0)   # (tamanho_px, linhas)
texto.vao_entre_palavras(est)                      # px entre duas palavras: avanço do espaço da fonte (+ tracking), já com escala_x
texto.colar(destino, camada, x, y, ancora="centro")   # (x, y) é o ponto da camada dado pela âncora '<x>_<y>': x = esquerda|centro|direita, y = topo|centro|base.
                                                     # 'centro' = 'centro_centro' (os DOIS eixos): colar(dst, cam100x60, 200, 150, "centro") → (150, 120); 'centro_base' → (150, 90)
est.com(cor="primaria", tamanho=40)                # cópia com alterações; cor = token ("primaria", "dado-2"), hex, tupla RGB(A) ou (d, "token")
```

**`compor_legenda(palavras, estilos, d, largura, altura, plataforma=None, x=None, y=None, max_linhas=None, largura_max=None, formato=None, linhas=None, espaco_em=None, minimo=10.0, recortar=False, apenas=None)`** — a função que desenha uma cue (a skill de legendas normalmente a chama por `estados_da_legenda`, abaixo):

| parâmetro | significado |
|---|---|
| `palavras`, `estilos` | as palavras da cue e um `Estilo` por palavra (ou um só para todas). Contorno, sombra, fundo, tracking e `escala_x` vêm do **primeiro** estilo; os demais mudam cor e tamanho |
| `plataforma` | zona segura: `None` = padrão do formato (`uniao` no vertical, `padrao` no horizontal/quadrado); `"reels"`/`"instagram"`, `"tiktok"`, `"shorts"`; `"quadro"` = sem zona |
| `x`, `y` | **centro** do bloco em px. `None` = `legenda.posicao.<formato>.x`/`.y` da DA; sem `x` na DA, o centro do retângulo da zona |
| `max_linhas`, `largura_max` | padrão `legenda.max_linhas` e `legenda.posicao.<formato>.largura_max` (ou `legenda.largura_max`) × largura; a largura nunca passa da zona |
| `linhas` | força a quebra: contagens por linha (`[2, 1]`) ou listas de índices |
| `recortar` | `True` devolve só o retângulo desenhado (PNG pequeno) e `info['x']`, `info['y']` para o overlay — o formato que `video.compor_cues` recebe |
| `apenas` | índice de **uma** palavra da cue: desenha só ela, centrada, no tamanho em que todas as palavras da cue cabem sozinhas numa linha — o estilo `palavra` do motor (a fonte não muda de tamanho de uma palavra para a outra dentro da cue) |

A cue **quebra em linhas equilibradas** e só então, se ainda não couber, **encolhe** (todas as palavras juntas, passos de 6 %); se o centro pedido deixaria o bloco fora da zona, ele é empurrado para dentro. `info` (px do quadro): `caixa` (texto + contorno + fundo), `bbox` (tudo o que foi pintado, com a sombra), `caixa_texto`, `palavras` `[{'texto', 'linha', 'x0', 'x1', 'y0', 'y1'}]` (caixas de avanço: sirva-se delas para animar a palavra falada), `linhas`, `indices`, `linha_base`, `linhas_base`, `tamanho`, `tamanho_pedido`, `tamanho_fracao` (do lado menor: compare com o mínimo legível da DA), `encolheu`, `coube` (False = nem no tamanho mínimo coube), `zona`, `dentro_da_zona`, `vao`, `contorno_px`. Medido nos 5 presets em 1080×1920 com 5 cues (inclusive uma palavra de 27 letras e uma cue de 7 palavras): `dentro_da_zona` sempre `True`.

**`estados_da_legenda(palavras, d, largura, altura, plataforma=None, x=None, y=None, formato=None, recortar=True, **opcoes)`** monta os estilos e devolve os estados de uma cue na ordem das palavras, exatamente como `ctx.kit.legenda(palavras).seek(i)` os mostra no motor; é o atalho que a receita do §16 usa — e é com ele que a **prancha** desenha a amostra de legenda que o cliente aprova (`motor.legenda_de_amostra`): o que está na prancha é o PNG que a produção queima. `texto.escalar_estilo(est, k)` devolve o estilo com tamanho, contorno, sombra e caixa multiplicados por `k` (o "pop" de uma palavra; o encolher em conjunto).

`desenhar_linha(palavras, estilos, d, largura, altura, formato=None, espaco_em=None, largura_max=None, plataforma=None, x=None, y=None)` continua existindo e virou `compor_legenda` com `max_linhas=1`: **mudou de comportamento em 1.4.0** — centra e limita pelo retângulo da zona segura (no vertical `uniao`, x = 450 em vez de 540) e o vão é o espaço da fonte (era 0,28 em fixo, somado à largura da tinta: a linha saía 23–36 % mais larga que a da prancha). `espaco_em=0.28` reproduz o vão antigo.

**Paridade com o motor (D10)** — o mesmo token rende o mesmo desenho em `texto.py` e em `ctx.kit.legenda` (`motor/cenas/_legenda.js`); o teste `test_30` renderiza a mesma cue pelos dois caminhos e compara:

| token | semântica única | medido (dossiê, 1920×1080, 67 px) |
|---|---|---|
| vão entre palavras | avanço real do caractere de espaço da fonte + tracking dos dois lados, × `escala_x` | 11,01 px em PIL; o motor fica a menos de 0,3 px (limite conferido pelo `test_30`) |
| posição das palavras | avanços da fonte no tamanho **fracionário** (0,062 × 540 = 33,48 px; `Estilo.legenda` não arredonda) | x0/x1 de cada palavra a ≤ 0,3 px |
| `contorno.espessura` | fração do tamanho da fonte, espessura **externa visível** (para fora da letra), arredondada para px inteiro, **cantos redondos** nos dois (no motor, `ctx.contorno` desenha um anel de sombras de texto em vez de `-webkit-text-stroke`, cuja junção em esquadria soltava farpas em fonte variável) | 7 px no topo e na base nos dois; 5 px nas laterais nos dois (× `escala_x` 0,7) |
| `sombra.dx/dy/desfoque` | frações do tamanho; a sombra é projetada pelo texto **já com o contorno** (no motor, `filter: drop-shadow` por linha — o `text-shadow` do Chromium projeta só o preenchimento e sumia atrás de um contorno mais grosso que o deslocamento); `desfoque` = raio de desfoque do CSS (o desvio-padrão do gaussiano é a metade) | neon-shorts (contorno 0,14, sombra dura 0,07): bbox pintado do motor (117, 506, 335, 563) × PIL (117, 507, 335, 564) |
| `fundo` | UMA caixa para o bloco inteiro: caixa das linhas (`n × altura_linha × tamanho`) + `respiro`; `raio` em fração do tamanho | — |
| `escala_x` | condensa tudo na horizontal: letra, contorno, sombra e respiro (é o `scaleX` do motor) | — |
| quebra | `texto.quebrar_palavras` = `quebrarPalavras` do `_legenda.js` (enche a linha, depois equilibra) | mesmas linhas |
| `legenda.estilo: palavra` | a cue inteira tem um tamanho só (o maior em que cada palavra cabe sozinha) e só a falada aparece, em `cor_destaque` | neon-shorts, 540×960: 43,9 px nos dois (0,092 × 540 encolhido duas vezes por causa de "DESAPARECE") |
| tracking + kerning | o kerning da fonte vale também com `tracking` ≠ 0, como o `letter-spacing` do navegador (até 1.3.0 o PIL somava os avanços caractere a caractere e perdia os pares: "DESAPARECE" saía 2 px mais larga e encolhia um passo a mais que no motor) | caixas a ≤ 0,5 px nos 5 presets, horizontal e vertical |

Diferença que fica: o suavizado das bordas (antialias do Chromium × FreeType) e o "pop" — no motor a palavra falada nasce 8 % maior (`seek(i, {pulso: 0})`) e assenta em `pulso: 1`; em PIL ela é desenhada assentada, e o pop se faz com estados extras (§16).

`Estilo` é um dataclass com `arquivo, tamanho, cor (RGBA), eixos, eixos_ordem, tracking (em), caixa_alta, escala_x, altura_linha, contorno ((RGBA, px para fora)|None), sombra, fundo, alinhamento, alfa`. Contorno/sombra/fundo em `do_papel` são frações do tamanho, as mesmas chaves do bloco `legenda` do `da.json`. Fonte variável: `carregar_fonte(arquivo, tamanho, eixos, eixos_ordem)` aplica `set_variation_by_axes` (tamanho em centésimos de px). Limites reais: tracking ≠ 0 desenha caractere a caractere, cada um na posição com kerning (precisa do Pillow com libraqm — é o caso desta máquina; sem ela, perde os pares de kerning); `escala_x` é redimensionamento LANCZOS do bloco; `desenhar()` devolve `info['origem_x']` e `info['avanco']` para quem alinha blocos pela linha de base; em `desenhar()` a caixa de `fundo` também é a do bloco de linhas + respiro (até 1.3.0 abraçava a tinta, e em `desenhar_linha` era uma caixa por palavra).

## 5. API Python — `video.py` (ffmpeg da casa)

```python
s = video.sondar("bruto/x.mp4")      # {'largura': 1920, 'altura': 1080, 'fps': Fraction(30000, 1001), 'duracao': 5.839, 'tem_audio': True, 'pix_fmt': 'yuv420p', …}; WebM lê o alfa
video.filtro_tratamento(d, "horizontal")                 # cadeia do grade.json ("null" se neutro); parte="cor"|"acabamento"; aceita "LxA"
video.filtro_recorte((1920, 1080), (1080, 1920), ancora="rosto", foco=(0.5, 0.33))
# → {'filtro': 'scale=3414:1920:flags=lanczos,crop=1080:1920:1166:0', 'escala': (3414, 1920), 'corte': (1166, 0, 1080, 1920)}; ancora = centro|rosto|terco_esq|terco_dir
video.filtro_encaixe((1920, 1080), (1080, 1920), d=d)    # vídeo INTEIRO sobre fundo desfocado (tratamento.encaixe) — ver abaixo
video.args_encode(d, formato="vertical", crf=18)         # fps do formato na DA; ou args_encode("30000/1001") / args_encode(25) / args_encode() (30000/1001)
# → ['-c:v','libx264',…,'-pix_fmt','yuv420p','-x264-params','colorprim=bt709:…','-r','30000/1001',…,'-movflags','+faststart','-c:a','aac','-ar','48000',…]
video.executar(["-i", "a.mp4", "-vf", cadeia, *video.args_encode(d)], "render/x.mp4", rotulo="tratar")
# → roda ffmpeg SOB A TRAVA (grupo de processos próprio, stdin em /dev/null, stderr drenado), grava render/x.parcial.mp4 e
#   renomeia só com rc 0; levanta DAErro com o stderr se falhar, se ficar 120 s sem progresso (inatividade=120; None desliga; prazo=SEG)
#   ou se o ffmpeg sair com 0 sem gravar nada (`extrair_quadro` num instante depois do fim: "não gravou nada … nenhum quadro chegou à saída")
video.executar([*video.args_png_para_yuv420("30"), *video.args_encode("30", audio=False)], "render/q.mp4", entrada=quadros_png)
# → `entrada` = bytes ou ITERÁVEL de bytes escritos no stdin do ffmpeg por uma thread, que fecha o stdin no fim e para se o ffmpeg
#   sair antes. `-i -` SEM `entrada` é DAErro imediato. Para quadros PIL prefira o Codificador (abaixo): cuida de formato, alfa e carimbo.
video.entrada_com_alfa("animacoes/gc.webm")              # ['-c:v', 'libvpx-vp9', '-i', 'animacoes/gc.webm'] — obrigatório para LER o alfa de WebM
video.filtro_loudnorm(d, "curto")                         # 'loudnorm=I=-14:TP=-1:LRA=11' (som.loudness.curto; passagem única) → use em -af
medida = video.medir_para_loudnorm("cortes/_a.mp4", d, "curto", inicio=None, duracao=None, folga_pico=0.5)   # 1ª passagem, só áudio (0,2 s para 4 s de fala)
# → {'input_i': -21.55, 'input_tp': -2.28, 'input_lra': 3.5, 'input_thresh': -31.55, 'target_offset': 1.8}; trecho em silêncio → DAErro
video.filtro_loudnorm(d, "curto", medida=medida, folga_pico=0.5)
# → 'loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=-21.55:measured_TP=-2.28:measured_LRA=3.5:measured_thresh=-31.55:offset=1.8:linear=true'
video.medir_loudness("render/final.mp4")                  # {'lufs': -19.8, 'lra': 10.3, 'pico_real': -2.0, 'limiar': -30.5} (ebur128)
video.conferir_loudness(d, "render/final.mp4", tipo="curto")   # {'ok': False, 'medido', 'alvo': {'lufs': -14, 'pico_real': -1.0}, 'desvio_lufs': -5.8, 'estoura_pico': False}
video.extrair_quadro("render/final.mp4", 0.6, "qa/_q.png", largura=360, tratamento=None)   # `_q.png`: intermediário, fora do conferir-carimbo
video.folha_de_contato([q1, q2], ["t=0,6 s", "citação"], "qa/folha.png", colunas=2, largura_celula=360, da_obj=d, titulo="Conferência", proporcao=None)
# → célula na proporção do PRIMEIRO quadro (peça vertical gera célula vertical; ou proporcao="9:16" | (9, 16) | 0.5625); cada quadro entra
#   INTEIRO, centrado sobre a cor `superficie` — até 1.3.0 era cortado para 16:9 e a folha de conferência perdia o topo e a base do vertical
```

Toda função que recebe a DA aceita `da_obj=d` ou o sinônimo `da=d`. **Tudo o que grava peça carimba a saída** com o formato lido do próprio arquivo e a proveniência dos insumos (§7).

**Loudness em peça curta pede duas passagens.** Medido num trecho de 4 s de fala (−20,6 LUFS de origem, alvo `curto` −14 LUFS / −1 dBTP, saída em AAC): passagem única → −15,7 LUFS (`conferir_loudness` reprova: desvio −1,7); duas passagens (`medida=`) → −14,4 LUFS, mas pico −0,8 dBTP (o AAC devolve o pico ~0,2 dB acima do que o limitador deixou, e `estoura_pico` acusa); duas passagens com `folga_pico=0.5` → −14,4 LUFS e −1,5 dBTP, `ok: True`. Use a mesma `folga_pico` na medida e no filtro. O mix final do vídeo longo continua sendo trabalho da video-mixagem.

### 5.1 Compor sobre vídeo

```python
r = video.compor_overlay("bruto/fala.mp4", "animacoes/gc.webm", "render/com gc.mp4", t0=0.2, x="(W-w)/2", y="H-h-40", fim=1.0, da_obj=d,
                         inicio=12.0, duracao=4.0, tratamento_base=video.filtro_recorte((1920, 1080), (1080, 1920), "rosto")["filtro"])
# → {'saida', 'filtro', 'carimbo'}; overlay WebM/MOV/PNG. `inicio`/`duracao` = trecho da BASE, sem encode intermediário (t0 e fim contam a
#   partir dele); `tratamento_base` (ou `filtro_base`) = cadeia aplicada à base antes. Áudio da base copiado (AAC quando há `inicio`).
#   O carimbo leva o formato da SAÍDA: base 320×180 recortada para 90×160 → formato '90x160' (era 'horizontal', o da base) e
#   insumos [base, overlay]. A saída tem sempre os quadros da base: PNG sem `fim` fica até o último quadro.

r = video.compor_cues("cortes/corte 01.mp4", cues, "legendas/corte 01 legendado.mp4", da_obj=d, inicio=None, duracao=None,
                      tratamento_base=None, tamanho=None, parametros={"cues_json": "legendas/corte 01.cues.json"})
# cues = [{"imagem": PIL.Image | "caminho.png", "t0": 0.00, "t1": 0.16, "x": 174, "y": 1071}, …]   (x, y = canto da imagem no quadro de saída)
# → {'saida', 'cues', 'estados', 'quadros_gerados', 'regiao': (x, y, w, h), 'filtro', 'carimbo'}
```

`compor_cues` queima **N estados de overlay numa única passada**: o ffmpeg tem duas entradas — a base e uma faixa RGBA gerada em Python e entregue por pipe —, não uma entrada (nem um reencode) por cue. A faixa cobre só a união dos retângulos das cues (legenda de 660×200 px num quadro 1080×1920 = 0,5 MB por quadro, não 8 MB), cada estado é composto uma vez e reaproveitado enquanto durar, e cues podem se sobrepor no tempo (empilham na ordem da lista). Cue do tamanho do quadro faz a faixa cobrir o quadro inteiro (1080 × 1920 × 4 = 8,3 MB por quadro pelo pipe): gere as imagens com `recortar=True`. Tempos são arredondados para o quadro da base; `tamanho=(L, A)` é necessário quando `tratamento_base` muda as dimensões. Medido (`test_22`): 64 cues de karaokê em 10 s a 320×180 → 1 ffmpeg, 2 entradas, 64 estados, 0,23–0,46 s; a palavra em destaque conferida em três instantes. O carimbo registra a base e as cues em arquivo que tenham carimbo.

```python
enc = video.filtro_encaixe((1920, 1080), (1080, 1920), modo=None, d=d)
# → {'filtro': 'split[enc_a][enc_b];[enc_a]scale=854:480…,gblur=sigma=9.45,lutyuv=…,scale=1080:1920…[enc_f];[enc_b]scale=1080:608…[enc_v];[enc_f][enc_v]overlay=0:656,setsar=1',
#    'modo': 'desfocado', 'janela': (0, 656, 1080, 608), 'saida': (1080, 1920)}       — uma entrada, uma saída: serve em -vf
```

`modo` (padrão `tratamento.encaixe.modo`): `'desfocado'` = o vídeo inteiro por cima de uma cópia dele ampliada, desfocada (`tratamento.encaixe.desfoque` = sigma em fração do lado menor da saída; calculado a ¼ da resolução, 4× mais rápido) e escurecida (`encaixe.escurecer`); `'recorte'` = amplia e corta (`filtro_recorte` com `tratamento.recorte.ancora`); `'faixas'` = vídeo inteiro com faixas na cor `tratamento.encaixe.cor`. `janela` diz onde o vídeo original ficou (para pôr legenda ou GC fora dele). **`tratamento.desfoque` é outra coisa**: borra o footage inteiro na cadeia de acabamento.

```python
r = video.encaixar_em_janela("render/_fundo.mp4", "broll/tratado/arquivo.mp4", "render/insert.mp4", layout, moldura="animacoes/moldura.webm", da_obj=d)
# layout = da.ler_carimbo("animacoes/moldura.webm")["parametros"]["layout"]  (usa `janela_girada`: centro, tamanho e ângulo da polaroid inclinada)
```

O insert cobre a janela da moldura (amplia e corta pelo centro), gira com ela e a moldura vai por cima, numa passada. Moldura e base precisam do mesmo tamanho (erro claro se não: a janela está em px do quadro da moldura). Conferido em `test_34`: nos quatro cantos da janela girada há insert, sem cunhas.

### 5.2 Quadros PIL → vídeo (`Codificador`)

```python
with video.Codificador("animacoes/onda.webm", formato="vertical", da_obj=d, ferramenta="video-animacao-audio", parametros={"cena": "onda"}) as cod:
    for i in range(n):
        cod.escrever(desenhar_quadro(i))       # PIL.Image de qualquer modo, bytes RGBA L×A×4 ou array numpy A×L×(3|4); repetir=N repete o quadro
cod.resultado   # {'saida', 'quadros', 'carimbo', 'largura', 'altura', 'fps', 'codec'}
video.codificar_quadros(iteravel_de_quadros, "legendas/_faixa.mov", largura=1080, altura=1920, fps="30000/1001", da_obj=d)   # o mesmo, para um iterável
```

| opção | significado |
|---|---|
| `codec` | `'h264'` (.mp4/.mov, opaco, yuv420p bt709 +faststart), `'vp9alfa'` (.webm, alfa, para compor via ffmpeg), `'prores4444'` (.mov, alfa, Premiere). Padrão pela extensão. Em h264, quadro com transparência é achatado sobre a cor `fundo` da DA (`fundo="superficie"` troca o token) |
| `formato` / `largura`, `altura`, `fps` | nome de formato da DA ou `LxA` (dá tamanho e fps), ou os valores; sem tamanho vale o do primeiro quadro; lados pares |
| `audio` | arquivo de áudio muxado junto (AAC em h264; opcional) |
| `crf`, `carimbar`, `ferramenta`, `parametros`, `insumos`, `inatividade`, `espera_max` | qualidade; carimbo da peça (padrão liga); vigia de inatividade (120 s) e teto de espera na fila |

Garantias (cada uma com teste em `test_20`/`test_21`): a trava é pedida no `with` e solta na saída dele, aconteça o que acontecer — exceção dentro do `with` mata o ffmpeg e não deixa peça, `.parcial` nem carimbo; ffmpeg que morre no meio faz a escrita seguinte levantar `DAErro` com o stderr (`ffmpeg falhou (código 9) … (quadro 37 …; nada foi gravado)`) em vez de pendurar; ffmpeg que para de ler é morto pelo vigia de inatividade e a escrita levanta; quadro de tamanho errado é `DAErro` (`quadro 1 tem 100×90, o vídeo é 160×90`). Conferido por ffprobe: vp9alfa → `yuva420p` com alfa real, prores4444 → `yuva444p12le`, h264 → `yuv420p`; 15 quadros de 160×90 em 0,08–0,14 s. `video.args_codec(codec, fps, crf)` devolve os argumentos de saída de cada codec (os mesmos do motor) para quem monta o próprio comando.

### 5.3 Transições da DA (`movimento.transicoes`)

```python
r = video.juntar(["cortes/_a.mp4", "cortes/_b.mp4", "cortes/_c.mp4"], "render/sequencia.mp4", transicao=None, da_obj=d, duracao=None, formato=None)
# → {'saida', 'duracao': 3.5667, 'transicoes': [{'tipo': 'fade', 'inicio': 1.0, 'duracao': 0.5}, …], 'filtro', 'carimbo'}
video.filtro_transicao("mascara", d.dur("media"), inicio=2.14)    # 'xfade=transition=wipeleft:duration=0.36:offset=2.14' (None para 'corte')
```

| `transicao` (padrão `movimento.transicoes.padrao`) | ffmpeg | no motor (`ctx.transicao`) |
|---|---|---|
| `corte` | `concat` | troca seca |
| `fade` | `xfade=transition=fade` | B aparece por opacidade sobre A |
| `empurra` | `xfade=transition=slideleft` | A sai para a esquerda, B entra da direita |
| `mascara` | `xfade=transition=wipeleft` | B é revelado da direita para a esquerda |
| `desliza` | `xfade=transition=coverleft` | B desliza por cima de A |
| `zoom` | `xfade=transition=zoomin` | A amplia e some sobre B |

Tipo fora de `movimento.transicoes.permitidas` é `DAErro` (`transição 'empurra' não está em movimento.transicoes.permitidas desta DA (corte, mascara, fade)`); `transicao=["fade", "corte"]` dá o tipo de cada junção. Duração = `movimento.duracoes.media` (0 no corte; `duracao=` troca) e cada transição come esse tempo do total; o `xfade` é linear (as curvas da DA valem no motor). Os clipes são levados ao tamanho do primeiro (ou a `formato`) cobrindo o quadro, ao fps do formato na DA e a áudio 48 kHz estéreo cruzado junto (`acrossfade`); clipe sem áudio entra com silêncio. Medido (`test_23`): 3 clipes de 1,5 s com `empurra` → 0,4–0,7 s, duração 4,5 − 2 × 0,3 s.

Constantes: `video.THREADS = "2"` (todo ffmpeg do kit roda com `-threads 2`, inclusive `da.py grade`), `video.FFMPEG`/`FFPROBE` resolvidos por `da._bin`, `video.CODECS`, `video.XFADE`, `video.MODOS_ENCAIXE`; `video.nome_do_formato(d, L, A)` → `'vertical'` ou `'540x960'`; `video.fps_do_formato(d, formato)`. **Este ffmpeg não tem `drawtext`, `subtitles` nem `ass`**: texto sobre vídeo só via PNG RGBA (texto.py ou motor) + `overlay`.

## 6. `trava.py` — uma tarefa pesada por vez (e nenhuma que fique presa)

```bash
# trava.py só usa a biblioteca padrão: roda com qualquer python3 ≥ 3.9 (conferido com o /usr/bin/python3 3.9.6 do macOS), sem Pillow
python3 <kit>/trava.py [--espera-max SEG] [--inatividade SEG] [--prazo SEG] [--rotulo TEXTO] [--silencioso] -- <comando…>
python3 <kit>/trava.py --estado [--json]     # "trava livre" (0) ou "trava ocupada (pid, rótulo, há N s, SEM PROGRESSO há M s)" (1)
python3 <kit>/trava.py --liberar [--se-ocioso 120]   # mata o dono (e a árvore dele) SE estiver sem progresso há ≥ 120 s
```

```python
r = trava.rodar(["ffmpeg", "-i", "a.mp4", …], rotulo="corte 3", capturar=True, inatividade=120)   # o jeito certo de rodar algo pesado
r.codigo, r.stdout, r.stderr, r.motivo, r.duracao     # motivo: None | 'inatividade' | 'prazo' (codigo 124); r.returncode == r.codigo
trava.rodar(cmd, entrada=b"…" | iteravel_de_bytes)     # escreve no stdin por uma thread e FECHA no fim; sem `entrada` o stdin é /dev/null
trava.rodar(cmd, entrada=trava.HERDAR, vigiar=[saida_parcial], prazo=600, espera_max=30, cwd=…, env=…)
rc = trava.executar(["ffmpeg", …], espera_max=None, rotulo=None, inatividade=None, prazo=None)   # só o código; entrada e saídas de quem chamou
with trava.Trava(rotulo="legendas em PIL", espera_max=None):   # trabalho pesado DENTRO do Python (PIL, numpy); estourou a fila → trava.TempoEsgotado (75)
    ...
trava.sob_trava()             # pid do dono se ESTE processo já está dentro da trava, senão None
trava.estado()                # {'livre': bool, 'dono': {'pid', 'rotulo', 'desde', 'grupos', 'batimento', 'ocioso_s'} | None, 'ocioso_s': float | None}
trava.liberar_ocioso(se_ocioso=120)   # {'liberou', 'motivo', 'dono', 'ocioso_s', 'mortos'} — a mesma coisa do --liberar
trava.inatividade_padrao(120) # VIDEO_OPS_INATIVIDADE (segundos; 0 → None) ou o padrão passado
trava.descrever_vigia(r, "rótulo")    # frase pronta para o erro quando r.motivo ≠ None
```

Garantias (cada uma tem teste em `testes/test_trava.py`, com arquivo de trava privado):

- **Grupo próprio e sinais.** `rodar`/`executar` lançam o comando numa sessão/grupo de processos própria. SIGINT/SIGTERM/SIGHUP no dono são repassados à árvore inteira — filhos, netos e quem mudou de grupo, como o Chromium do Playwright — e quem ainda vive 3 s depois leva SIGKILL (sinal que já chegou ignorado de propósito, como o SIGHUP sob `nohup`, continua ignorado); só então a trava é solta e sobe `KeyboardInterrupt` (SIGINT) ou `trava.Interrompido` (SIGTERM/SIGHUP; é um `SystemExit(128+N)`, então um script que não o captura sai com 143 sem traceback). Observado: `kill -TERM` num `trava.py -- sh -c '…'` com 3 descendentes (um em outra sessão) → rc 143, 0 sobreviventes.
- **`with Trava()` também.** Enquanto segura a trava (thread principal, sem tratador próprio do programa), SIGTERM/SIGHUP viram `trava.Interrompido`: um `subprocess.run` em andamento mata o filho direto e os `finally` rodam. Netos só morrem com `rodar` — por isso processo pesado é sempre por `rodar`.
- **Dono morto = trava assumida.** O flock é do sistema: dono morto (até por SIGKILL) solta a trava na hora. Quem assume lê o registro que sobrou e **encerra os grupos órfãos** que o morto tinha registrado antes de trabalhar (`[trava] o dono anterior (pid X, rótulo) morreu sem liberar; trava assumida e 3 processo(s) órfão(s) encerrado(s)`). Só mata o que é comprovadamente dele (mesmo pid líder com o mesmo instante de início).
- **Vigia de inatividade.** `inatividade=SEG` / `--inatividade SEG`: sem progresso por SEG segundos → árvore morta, trava liberada, código **124**, `motivo == 'inatividade'`. Progresso = CPU da árvore de processos (≥ 3 % de um núcleo entre amostras do `ps`), bytes de saída capturada, bytes de entrada consumidos ou mudança de tamanho/mtime em `vigiar=[…]`. `prazo=SEG` limita o tempo total. Padrões do kit: motor 120 s por dentro (quadros) + 180 s por fora; `video.executar`, `da.py grade` e `medir_loudness` 120 s; `extrair` 60 s por quadro; `trava.py -- <cmd>` sem vigia (passe `--inatividade`). `VIDEO_OPS_INATIVIDADE=SEG` troca o padrão de todos; `0` desliga. Observado: `--inatividade 2 -- sleep 30` → 124 em 3,3 s.
- **Reentrância.** O filho recebe `VIDEO_OPS_TRAVA=<pid do dono>` (o `rodar` a injeta mesmo num `env=` montado antes) e executa direto, sem fila — `da.py grade` → ffmpeg e `render.mjs` → `da.py` não se bloqueiam. Se a variável se perder no caminho (`env -i`, sudo), quem espera descobre pelo `ps` que o dono é seu **ancestral** e também reentra, em vez do impasse eterno (o pai esperando o filho que espera o pai). Processo reentrante de outro processo fica no grupo do dono.
- **Quem espera sabe o que está acontecendo.** A cada 15 s: `[trava] aguardando trava… (30 s na fila; em uso por pid X, rótulo, há 45 s, SEM PROGRESSO há 40 s)`; passou de 60 s parado, a linha já traz o comando `--liberar`. O dono que usa `rodar` grava um batimento a cada 2 s; para dono que só usa `with Trava()`, quem espera (e o `--estado`) amostra a CPU dele.

Procedimento para trava presa (documente na sua skill): `trava.py --estado` → se aparece `SEM PROGRESSO há mais de 2 min`, `trava.py --liberar` (ele confere de novo e só mata dono parado; código 0 = liberou ou já estava livre, 1 = o dono está trabalhando). Nunca `rm` no arquivo da trava: o flock é do processo, não do arquivo.

**O rótulo é público.** Ele fica gravado no arquivo da trava (`/tmp/video-ops-render.lock`, modo 600) e é impresso no stderr de todo processo que espera na fila. Sem `--rotulo`/`rotulo=`, o padrão é só o nome do executável — e, se for um interpretador, o nome do script (`ffmpeg`, `python3 legendar.py`, `node render.mjs`) —, nunca os argumentos: até 1.2.0 ia a linha de comando inteira, e uma URL com chave apareceria no log dos outros agentes. Nunca ponha em `rotulo` caminho de cliente, URL ou texto de roteiro.

Códigos do `trava.py`: o do comando; 75 = fila passou de `--espera-max`; 124 = morto pelo vigia; 126/127 = comando sem permissão/inexistente; 64 = uso; 128+N = sinal. Em testes que provocam travamento, aponte `VIDEO_OPS_TRAVA_ARQUIVO` para um arquivo da sua área de teste.

## 7. Carimbo (C4) — `<saida>.da.json`

Gravado por `da.carimbar` / `d.carimbar` / `da.py carimbar`, pelo motor, por `da.py grade` e por tudo o que grava peça em `video.py` (`compor_overlay`, `compor_cues`, `juntar`, `encaixar_em_janela`, `Codificador`):

```json
{"carimbo_versao": 1, "arquivo": "gc_teste.webm", "da_sha256": "f815c606…", "da_revisao": 1, "da_aprovada": false,
 "da_alterada_apos_aprovacao": false, "kit_versao": "1.5.1", "ferramenta": "motor", "formato": "vertical",
 "parametros": {"cena": "gc", "params": {…}, "fps": "30000/1001", "dur": 2, "codec": "vp9alfa", "escala": 0.5,
                "ancoras": [{"t": 0, "nome": "raiz", "tipo": "entrada"}, …], "layout": {"caixa": {…}, "fim_entrada": 0.52, "inicio_saida": 1.64},
                "livres": [{"seletor": "div.gc.gc-barra > div.gc-foto:nth-of-type(1)", "motivo": "foto", "tag": "div", "elementos": 2, "area": 0.007}],
                "quadros": 60, "quadros_reaproveitados": 31, "tempo_s": 2.04},
 "auditoria": "ok", "gerado_em": "2026-10-06T10:02:…-03:00", "da_json": "/…/da/da.json",
 "saida": {"tipo": "arquivo", "bytes": 22571, "sha256": "…", "modo": "completo"},
 "midia": {"tipo": "video", "largura": 540, "altura": 960, "fps": "30000/1001", "duracao": 2.002, "quadros": 60}}
```

Uma **composição** leva também a lista dos insumos (carimbo real de `video.compor_overlay` com um GC do motor sobre um corte legendado):

```json
{"ferramenta": "video.py compor_overlay", "formato": "540x960", "auditoria": "n/a",
 "parametros": {"base": "corte 01 legendado.mp4", "overlay": "gc mariana.webm", "t0": 0.2, "fim": null, "x": 0, "y": 0, "inicio": null, "duracao": null, "tratamento_base": null},
 "midia": {"tipo": "video", "largura": 540, "altura": 960, "fps": "30000/1001", "duracao": 3.003, "quadros": 90},
 "insumos": [{"arquivo": "corte 01 legendado.mp4", "caminho": "/…/legendas/corte 01 legendado.mp4", "carimbado": true, "da_sha256": "e6a0fc0d…", "auditoria": "n/a", "ferramenta": "video-legendas"},
             {"arquivo": "gc mariana.webm", "caminho": "/…/animacoes/gc mariana.webm", "carimbado": true, "da_sha256": "e6a0fc0d…", "auditoria": "ok", "ferramenta": "motor"}]}
```

**Identidade — regra exata.** `da_sha256` = sha256 de **todo** o conteúdo do `da.json` com a herança aplicada (`cor`, `tipografia`, `layout`, `movimento`, `tratamento`, `legenda`, `graficos`, `thumbnail`, `som`, `marca`, `formatos`, `versao_esquema` e qualquer seção nova) + sha dos arquivos de fonte/LUT/textura/logo referenciados, **exceto**: `herda`; `projeto.*` (nome, slug, datas, base, revisão, aprovação); `conceito.*` (frase, palavras-chave, referências, faça/não faça); e toda chave iniciada por `_` ou `x_`, em qualquer profundidade. Padrões do esquema não entram (o hash é do que está escrito: uma versão do kit que acrescenta um token com padrão não invalida os carimbos de quem não o usa). Consequências, todas testadas: mudar uma cor, `legenda.max_palavras`, `som.musica.clima` ou `marca.assinatura` muda o sha (todas as peças ficam "DA DIFERENTE"); renomear o projeto, reescrever `conceito.frase`, anotar em `_nota`/`x_minha_skill`, `aprovar` e `revisar` **não** mudam — nem derrubam a aprovação. Por isso `x_*` serve para dados da sua skill que **não** mudam pixel (cache, preferências de segmentação); o que muda pixel precisa ser token do esquema, senão peças velhas passam em `conferir-carimbo`. Em mapas de tokens (`cor.paleta`, `tipografia.escala`, `movimento.curvas`…) nome começado por `_`/`x_` é erro de validação. `saida` é a impressão digital do arquivo: regravar a peça por fora dá `ARQUIVO ALTERADO`. Uma **pasta** de quadros também pode ser carimbada (`saida.tipo = "pasta"`, conta arquivos e bytes). Ponha em `parametros` o suficiente para reproduzir a peça (cues, tempos, origem do b-roll, versão do roteiro): é o que a conferência final, a video-publicacao e o editor vão ler (a conferência usa `parametros.plataforma` do carimbo de um corte para escolher os limites de plataforma — §18).

Regras que valem para toda skill que carimba:

- **A identidade é a do início.** Carregue a DA uma vez (`d = da.carregar()`) no começo do trabalho e carimbe com esse `d`: o carimbo leva o sha com que a peça foi desenhada. Se você carimba por CLI ou recarrega a DA no fim, passe `sha_esperado=<d.sha256 do início>` (`--sha-esperado`): com a DA mudada no meio, `carimbar` levanta `DAErro` ("a DA mudou enquanto a peça era gerada…") e não grava. O motor faz isso sozinho — observado: editar `cor.paleta.primaria` durante um render de 5 s → `FALHA … carimbo recusado: a DA mudou`, saída e carimbo antigos intactos, código 1.
- **`parametros.livres`** é a lista dos elementos `data-da-livre` que o auditor encontrou (`seletor`, `motivo` = valor do atributo, `tag`, `elementos` = tamanho da subárvore, `area` = fração do quadro): é por ela que a conferência final mostra o que escapou da auditoria (item `carimbo.livres`). Uma `area` perto de 1 com muitos `elementos` é uma peça inteira escondida atrás do escape.
- **`da_alterada_apos_aprovacao: true`** marca peça gerada com o `da.json` editado depois do `aprovar` (o motor, `da.py grade` e `da.py carimbar` avisam em destaque no stderr). Enquanto a DA estiver nesse estado, `conferir-carimbo` reprova **todas** as peças com `DA ALTERADA APÓS APROVAÇÃO`; `revisar` + `aprovar` resolvem sem rerender (o sha não muda).
- **`auditoria`**: `ok` = passou pelo auditor C3 do motor; `pulada` = renderizada com `--sem-auditoria`; `n/a` = peça que não passa pelo motor (PIL, ffmpeg). `carimbar` nunca promove: sobre um carimbo `pulada` do mesmo arquivo, `ok`/`n/a` levantam `DAErro` e o estado fica. Observado: render com `--sem-auditoria` → `conferir-carimbo` `AUDITORIA PULADA`; `da.py carimbar … --auditoria ok` → código 1; `conferir-carimbo` continua `AUDITORIA PULADA`.
- Peça renomeada ou copiada junto com o carimbo continua `ok` (o conteúdo confere), com a nota "carimbo gravado para '<nome original>'".
- **Proveniência (`insumos`)**: toda função que compõe peças lê o carimbo de cada insumo e grava `insumos: [{arquivo, caminho, carimbado, da_sha256, auditoria, ferramenta}]`; insumo sem carimbo (footage bruto, PNG intermediário) entra com `carimbado: false` e campos `null`. Os insumos **dos insumos** sobem junto, marcados com `via: "<peça intermediária>"`, para uma cadeia de composições não esconder nada. A `auditoria` da composição é a pior dos insumos: um overlay renderizado com `--sem-auditoria` deixa a saída `pulada` (observado: `compor_overlay(base, pulado.png, …)` → carimbo `pulada`; `da.py grade` sobre essa saída → `pulada` de novo, com `via`). `conferir-carimbo` reprova a composição com `AUDITORIA PULADA` (nomeando o insumo) ou `INSUMO DE OUTRA DA` (insumo carimbado com outra identidade: a base foi feita antes de a DA mudar) e apenas anota `insumo(s) sem carimbo (material bruto?)`. No que você compõe por conta própria, passe `insumos=[…]` a `d.carimbar` (CLI: `--insumo ARQ`, repetível).
- **`midia`** = `{tipo, largura, altura}` (imagem) ou `{tipo, largura, altura, fps, duracao, quadros}` (vídeo), lidos do próprio arquivo na hora do carimbo: quem confere não precisa interpretar `formato` (nome da DA ou `LxA`) nem `parametros.escala`.

## 8. CLI do motor — `motor/render.mjs`

```
node <kit>/motor/render.mjs --cena <nome|arquivo.js> --saida <arq> [--formato horizontal|vertical|quadrado|thumbnail|LxA|Lxauto]
     [--dur S] [--fps N/D] [--params '<json>'|@arq.json] [--alfa] [--quadro T|fim] [--codec h264|prores4444|vp9alfa]
     [--escala F] [--sem-auditoria] [--da <da.json>] [--de <pasta>] [--fila fila.json] [--json] [--sem-trava]
     [--validar] [--inatividade SEG]
```

Códigos: **0** ok · **1** falha de render (auditor, cena impura, ffmpeg, ffprobe, DA que mudou, fila com falha) · **2** nenhuma DA · **64** uso incorreto · **124** abortado por inatividade · **129/130/143** interrompido por SIGHUP/SIGINT/SIGTERM.

- Prefira `<kit>/bin/da render …` (mesmos argumentos): acha a DA, passa `--da`, confere os argumentos antes da fila e entra na trava. O `render.mjs` chamado direto se reexecuta sob `trava.py` sozinho quando não está nela.
- Cenas embutidas: `titulo`, `gc`, `moldura`, `citacao`, `barras` (+ `prancha` e `teste_movimento`, usadas pelos subcomandos) — parâmetros e layout de cada uma no §8.1. Cena própria: caminho `.js`.
- `--formato`: nome da DA ou `LxA` (ex.: `960x540`; dimensões pares; o fps vem da orientação equivalente da DA) ou `Lxauto` (altura pelo conteúdo, só com `--quadro`; é como a prancha é feita).
- `--quadro T` → PNG (com alfa se `--alfa`); `fim` = último instante. Vídeo: `h264` (.mp4, opaco, yuv420p bt709 marcado, crf 17, +faststart), `prores4444` (.mov, alfa, para o Premiere; ffprobe reporta `yuva444p12le`), `vp9alfa` (.webm, alfa, para compor via ffmpeg). Sem `--codec`: h264 se opaco; com alfa, `.webm` → vp9alfa, senão prores4444. Alfa em h264 → erro 64.
- `--dur S`: duração da peça (padrão `meta.dur_padrao`). Cena que exporta `duracao()` (§9; hoje, `teste_movimento`) calcula a própria duração pelas durações da DA: o `--dur` chega a ela como pedido e, se o resultado for outro, o motor avisa (`! teste_movimento.js: --dur 3: a cena teste_movimento calcula a duração pelas durações da DA e não corta animação; usei 5.21 s`, no preset dossie).
- `--escala 0.5` renderiza 960×540 com o layout de 1920×1080 (deviceScaleFactor): prévias e testes. Dimensão ímpar perde 1 px.
- **Opção desconhecida é erro 64** com sugestão (`opção desconhecida --escla. Quis dizer --escala?`); antes era ignorada em silêncio e `--escla 0.5` renderizava em resolução cheia. Valor faltando (`--quadro` no fim da linha) → `argumento --quadro: faltou o valor`; `--fps 0`/`--fps abc` → 64; `--quadro` fora de 0…dur é ajustado **com aviso** (`--quadro 99 está fora da peça (0 a 4 s): usei 4`). Chave desconhecida num job da fila também é 64 (chaves começadas por `_` são anotações livres).
- **Erros de uso saem antes da fila da trava**: argumentos, DA, cenas e params de todos os jobs são conferidos primeiro; só então o processo entra na trava e abre o browser. `--validar` para aí: imprime `VÁLIDO: N job(s), nada foi renderizado.` e a lista (com `--json`, `{ok, validado, jobs}`) — use antes de uma fila longa. Vale igual para `da.py render` e para `da_ext_motor.render(...)`: quando a trava está ocupada por outro processo, a conferência roda primeiro, fora da fila (um node sem browser, ~0,5 s); com a trava livre ela é dispensada, porque o próprio motor confere assim que entra.
- `--params` é validado contra `meta.params` **antes de abrir o browser**: parâmetro desconhecido, tipo errado, opção fora da lista, cor fora da DA, arquivo inexistente → código 64 com sugestão ("Quis dizer 'titulo'…"). Tipos: `texto numero inteiro booleano lista objeto arquivo cor papel opcao plataforma` (+ `min`/`max`: valor em número, quantidade de itens em lista). Lista e objeto são conferidos por dentro quando a cena declara: `itens: {tipo, …}` vale para cada item da lista (`null` no meio é erro: `parâmetro "palavras[1]": item vazio (null) na lista`; tipo errado: `parâmetro "dados[0].valor": esperado número, veio "dez"`) e `campos: {nome: {tipo, obrigatorio, padrao}}` para as chaves do objeto (chave desconhecida sai com "Quis dizer…"). `tipo: 'plataforma'` é a zona segura: aceita as chaves de `formatos.margens_seguras` (`uniao`, `instagram`, `tiktok`, `shorts`, `padrao`) e os nomes canônicos (`reels`, `youtube`); nome inexistente (`tiktokk`) é erro 64 **antes do browser**, e zona que só existe em outro formato (`uniao` num render horizontal) vira aviso — `! parâmetro plataforma: a zona "uniao" não existe no formato 960x540 (padrao); a cena usa "padrao"` —, de modo que o mesmo storyboard serve ao horizontal e ao vertical.
- `--fila fila.json`: lista de jobs `{cena, saida, formato, dur, fps, params, alfa, quadro, codec, escala, sem_auditoria}` num só browser. `saida` e `cena` com caminho são relativas à pasta do `fila.json`. Erro de **uso** em qualquer job (param inválido) aborta tudo com 64 antes de renderizar; falha de **render** (auditor, ffmpeg, ffprobe) não interrompe os outros — sai `RESUMO: 2 ok, 1 falha(s)` e código 1. `--json` imprime `{ok, da_sha256, renderizados: [...], falhas: [{cena, saida, erro}]}`.
- Tempos medidos (M1 8 GB, headless shell 1243): PNG 960×540 0,2–0,4 s de render (+ ~0,6 s de browser); título h264 2 s a 960×540: 2,8 s (17/60 quadros reaproveitados pelo cache); GC vp9alfa 2 s a 540×960: 2,0 s; selo ProRes 1,5 s: 1,5 s. Em 1920×1080 estime 3–4×.
- Saída: o ffmpeg grava `<saida>.parcial`; com rc 0 o ffprobe confere resolução, fps, nº de quadros e `pix_fmt` **no `.parcial`**; o carimbo é calculado sobre ele exigindo a identidade da DA lida no início; só então o `.parcial` vira `<saida>`. Qualquer falha nesse caminho apaga o `.parcial` e deixa a saída anterior (e o carimbo dela) intactos; o job conta como falha.
- **Nada espera para sempre.** A escrita de cada quadro no ffmpeg corre contra a saída do ffmpeg: se ele morrer no meio, o job falha em segundos com `o ffmpeg morreu com o sinal SIGKILL no quadro 164/360 — nada foi gravado` (antes o node ficava preso com a trava global). `--inatividade SEG` (padrão 120; `VIDEO_OPS_INATIVIDADE`; 0 desliga) aborta com 124 quando nenhum quadro avança — ffmpeg que não lê a entrada, laço sem fim em `seek()`. Observado: ffmpeg falso que sai com 9 depois de ler 200 KB → `FALHA: o ffmpeg saiu com código 9 no quadro 22/180 — nada foi gravado`, código 1, 5,8 s de parede; `seek` com `for(;;){}` e `--inatividade 3` → 124.
- **Nada fica órfão.** SIGINT/SIGTERM/SIGHUP no motor ou no `da.py render` matam ffmpeg e Chromium, apagam o `.parcial` e saem com 130/143/129 em ~1 s; o `node render.mjs` chamado direto repassa SIGINT/SIGTERM pela reexecução sob a trava (medido: `kill -TERM` em cada um dos três → código 143, nenhum processo vivo depois). O motor também se aborta sozinho quando o dono da trava ou o processo que o lançou morre (até por SIGKILL): `erro: o dono da trava (pid X) morreu — render abortado para não seguir fora da fila`.
- **DA alterada depois de aprovada**: o render sai, mas avisa em destaque (`[da] ! DA ALTERADA DEPOIS DA APROVAÇÃO (revisão N)…`), carimba `da_aprovada: false` + `da_alterada_apos_aprovacao: true` e o `conferir-carimbo` reprova até `revisar` + `aprovar`.

### 8.1 Cenas embutidas: parâmetros e o que o carimbo devolve

Todas aceitam `plataforma` (zona segura) e **`reservar_legenda`** (`true`/`false`/`null`): com a reserva ligada, a área útil da cena é `ctx.area_livre()` — a zona segura **menos a faixa da legenda** — e nada dela nasce em cima da legenda queimada. `null` (padrão) segue `legenda.reservar_em` da DA: ligada no vertical e no quadrado, desligada no horizontal — onde o GC fica na base da zona e **ocupa a faixa da legenda** (medido no neon-shorts a 960×540: GC em y 436–513, legenda de uma palavra em y 407–462, 1 916 px opacos em comum). É o que a prancha e o teste de movimento mostram e o que `validar` anota. Horizontal com legenda queimada: acrescente `"horizontal"` a `legenda.reservar_em` (vale para todas as peças e para os documentos de aprovação) ou, numa peça só, passe `"reservar_legenda": true` nos params. Os retângulos do `layout` vão para `parametros.layout` do carimbo, em px do quadro. **Mudança de comportamento em 1.5.0**: no vertical e no quadrado o GC `inferior_*`, o crédito `inferior_*`, a assinatura e o bloco de título/gráfico subiram para cima da faixa da legenda, e as molduras `janela`/`polaroid` sem `area` passaram a caber na área livre; `"reservar_legenda": false` devolve o posicionamento anterior (zona segura inteira).

| cena | params (além de `plataforma` e `reservar_legenda`) | `layout` devolvido |
|---|---|---|
| `titulo` | `titulo`\*, `sobretitulo`, `subtitulo`, `alinhar` (`esquerda`\|`centro`), `posicao` (`centro`\|`base`), `escala_titulo` (`display`\|`h1`\|`h2`), `assinatura` (bool) | `bloco`, `titulo`, `tarja`, `linhas`, `fim_entrada`, `inicio_saida`. A `marca.assinatura` fica na borda da área **oposta** à do GC da DA (GC embaixo → assinatura em cima) e reserva a própria faixa: um GC composto sobre a cartela nunca cai em cima dela |
| `gc` | `nome`\*, `cargo`, `foto` (arquivo), `selo`, `entrada_em`, `saida_em` | `caixa` (`{x, y, w, h, x1, y1}`), `estilo`, `protecao` (a efetiva: `nenhuma`\|`sombra`\|`contorno`\|`degrade`), `area`, `reservou_legenda`, `faixa_legenda`, `fim_entrada`, `inicio_saida`. No dossie vertical: `caixa` y 931–1058, `faixa_legenda` y 1071–1238 |
| `moldura` | `rotulo`, `sub`, `area` (`[x, y, w, h]` em frações), `inclinacao`, `estilo` | `janela`, `janela_girada`, `zona`, `rotulo_na_zona`, `rotulo`, `sub` (retângulos reais, px), `rotulo_empilhado`, `tamanho_rotulo`, `tamanho_sub`, `minimo_legivel`. Em `borda`, `cantoneiras` e `nenhuma` o rótulo e o sub ficam na área livre; em `janela` e `polaroid` (rótulo no cabeçalho/na base da moldura), sem `area` a moldura inteira nasce dentro da área livre — no vertical `uniao`, uma janela de 660 px de largura acima da legenda. **Rótulo e sub cabem sempre na largura que têm** (a da zona, a do cabeçalho da janela, a da base da polaroid): primeiro lado a lado numa linha, encolhendo os dois até `ctx.minimo_legivel`; se não couberem, o sub desce para baixo do rótulo e cada um quebra em até 2 linhas parelhas (o cabeçalho da janela e a base da polaroid crescem, e `janela` já vem com a altura nova — releia o `layout` antes de encaixar o insert). `rotulo_na_zona` é medido nos retângulos de rótulo **e** sub: só é `false` quando uma `area` pedida põe a moldura fora da zona ou quando nem no mínimo legível o texto cabe. Medido a 540×960 nos 5 presets com rótulo de 45 caracteres e sub de 50: tudo em x 60–390 (até 1.5.0, um rótulo de 37 chegava a x 514 e o sub a 670, cortado na borda do quadro, com `rotulo_na_zona: true`) |
| `citacao` | `texto`\*, `autor`, `cargo`, `fonte`, `foto`, `papel` | `bloco`, `credito`, `palavras`, `linhas`, `papel`, `fim_entrada`, `inicio_saida`. Autor e cargo quebram em até 2 linhas dentro da largura da frase (antes passavam da zona no vertical) |
| `barras` | `dados`\* (1–8 × `{rotulo, valor}`), `titulo`, `unidade`, `prefixo`, `casas`, `destaque`, `max`, `fonte`, `cores` (`serie`\|`primaria`), `empilhado` | `bloco`, `titulo`, `credito`, `escala_bloco`, `barras`, `max`, `cores` (a usada), `reservou_legenda`, `fim_entrada`, `inicio_saida`. Com mais barras que cores em `cor.dados`, todas saem na primária (`cores: "primaria"` no layout): cor repetida confunde categorias |
| `teste_movimento` | `titulo`, `nome`, `cargo`, `fundo` (arquivo), `atos` (lista de `titulo`\|`gc`\|`barras`) | `atos`, `janelas` (`{ato: {t0, pre, inicio, cena, entrada, saida}}`), `total`, `natural`, `minima`, `respiro`, `transicao`, `dur_transicao` e o layout de cada ato (`titulo`, `gc`, `barras`) + `legenda` (caixa, ou `null`), `gc_e_legenda_juntos` e, quando a legenda não entra, `legenda_omitida` (o motivo) |

`fonte` (em `barras` e `citacao`) é o crédito **sem** o prefixo: o kit põe `graficos.citacao_fonte.prefixo` ("Fonte: ") e não o duplica se o texto já começar por ele.

**Proteção do GC sobre vídeo** (`graficos.gc.protecao`, sempre na cor de apoio `cor_fundo`): `auto` (padrão) = `degrade` no estilo `linha` — o único sem caixa — e `nenhuma` nos demais; `sombra` = halo desfocado; `contorno` = anel de 0,09 em em volta das letras; `degrade` = painel `cor_fundo × alfa_fundo` de bordas esfumadas atrás do bloco. Medido no editorial-claro (texto escuro, GC `linha`) composto sobre um quadro de entrevista, contraste da cor do texto contra a média do que fica sob o bloco: nome 3,44:1 → 11,84:1 e cargo 1,17:1 → 4,03:1 com o painel.

## 9. Contrato de cena (módulo ES) — exemplo executado e comentado

Uma cena é um módulo ES **puro** (nada de `document`/`window` no nível do módulo), carregado dentro de `palco.html` com `da.css` + `da.js` já injetados e as fontes dos papéis carregadas (`document.fonts.load`; se uma fonte da DA não carregar, o render falha). O arquivo abaixo foi renderizado em PNG e ProRes e passou no lint e no auditor:

```js
// selo.js — exemplo mínimo de cena externa: um selo (etiqueta) que entra, fica e sai.
export const meta = {
  nome: 'selo',
  descricao: 'Selo curto no canto da zona segura (ex.: "AO VIVO", "ARQUIVO 2018").',
  dur_padrao: 3,                                   // usado quando não vem --dur
  formatos: ['horizontal', 'vertical', 'quadrado'],// formatos da DA que a cena aceita (LxA sempre passa)
  alfa_padrao: true,                               // fundo transparente por padrão (overlay)
  grao: false,                                     // true = o palco liga a camada de grão da DA (data-da-livre)
  params: {
    texto: { tipo: 'texto', obrigatorio: true, descricao: 'texto do selo (curto)' },
    cor: { tipo: 'cor', padrao: 'primaria', descricao: 'token de cor do fundo do selo' },
    canto: { tipo: 'opcao', opcoes: ['superior_esquerda', 'superior_direita'], padrao: 'superior_esquerda' },
    plataforma: { tipo: 'plataforma', padrao: null, descricao: 'zona segura (vertical: reels, tiktok, shorts, uniao)' },
  },
};

const S = {};                                      // estado da instância (padrão da casa: uma montagem por página)

export function build(palco, p, ctx) {
  const area = ctx.area_segura(p.plataforma || undefined);          // zona segura em px, já para este formato
  const fundo = p.cor;                                              // token validado pelo motor (tipo 'cor')
  const corTexto = ctx.legivel(fundo, 'fundo', 'texto');            // o que lê melhor sobre o fundo do selo

  const selo = ctx.texto('subtitulo', p.texto, { tam: ctx.tam('nota'), cor: corTexto, classe: 'selo' });
  Object.assign(selo.style, {
    background: ctx.cor(fundo),                                     // sempre via ctx.cor → hex da DA
    padding: `${ctx.px(0.008)}px ${ctx.px(0.016)}px`,
    borderRadius: ctx.raio + 'px',
    borderLeft: `${ctx.traco * 1.5}px solid ${ctx.cor('texto')}`,
  });
  palco.appendChild(selo);
  const m = ctx.medir(selo);                                        // mede DEPOIS de estar no DOM
  const x = p.canto === 'superior_direita' ? area.x1 - m.w - ctx.px(0.016) * 2 : area.x;
  ctx.place(selo, { x, y: area.y });

  const T = ctx.tl().add('selo', 0.1, ctx.dur('media'));           // timeline com a duração 'media' da DA
  Object.assign(S, { ctx, selo, T, inicioSaida: ctx.fim_saida() });
  return { caixa: ctx.rectDe(selo), fim_entrada: +T.fim.toFixed(3), inicio_saida: +S.inicioSaida.toFixed(3) }; // vai para o carimbo
}

export function seek(t) {                          // PURA em t: o motor chama fora de ordem (auditor em dezenas de instantes; checagem de pureza)
  const { ctx, selo, T, inicioSaida } = S;
  if (t >= inicioSaida) ctx.saida(selo, ctx.prog(t, inicioSaida, ctx.dur('curta'), 'saida'));   // saida_padrao da DA
  else ctx.entrada(selo, T.p(t, 'selo'));                                                         // entrada_padrao da DA
}

export function key(t) {                           // opcional: quadros iguais são reaproveitados no encode
  return t >= S.T.fim + 0.05 && t < S.inicioSaida ? 'parado' : null;
}

export function ancoras() { return S.T.ancoras(); } // opcional: [{t, nome, tipo}] para a skill de SFX
```

Render: `da.py render --cena animacoes/cenas/selo.js --saida animacoes/selo.mov --dur 1.5 --formato 960x540 --codec prores4444 --params '{"texto": "AO VIVO", "cor": "negativo"}'` → `prores | 960×540 | yuva444p12le | 30000/1001 | 45 quadros`, carimbo com `layout.fim_entrada = 0.46`, `inicio_saida = 1.14`.

Regras que o motor **impõe** (não são só recomendação):

- **`seek(t)` é função pura de t em toda a duração, inclusive na janela de saída.** A cada chamada, aplique o estado completo de *cada* elemento para aquele t e só então a saída por cima; um `if (t >= inicioSaida) { ctx.saida(raiz, …); return; }` antes de posicionar os filhos deixa os filhos como o seek anterior os deixou — no vídeo (sequencial) passa despercebido, em `--quadro T` sai um quadro diferente (era o defeito de `gc`, `barras`, `citacao` e `moldura` até 1.1.0: o GC na saída vinha sem nome). O motor confere antes de gravar: em 4 instantes (meio da entrada, repouso, janela de saída, fim; só `T` com `--quadro`) compara `seek(t)` vindo de `seek(0)`, de `seek(fim)`, do repouso e do quadro anterior; se o DOM diferir **e** os pixels também, reprova com `CENA IMPURA — seek(1.702) desenha um quadro diferente conforme o seek anterior` e mostra o elemento. O teste `test_10` compara, nas 5 cenas embutidas, o quadro N do vídeo com o PNG de `--quadro` (diferença máxima medida: 26/255, ruído do ProRes).
- **Tempo e acaso só pelos argumentos.** Relógios — `requestAnimationFrame`, `setTimeout`, `setInterval`, `requestIdleCallback`, `Date.now`, `new Date()` sem argumentos, `performance.now` (também pelo protótipo) e `performance.timeOrigin`, `document.timeline.currentTime`, `event.timeStamp`, `Intl.DateTimeFormat().format()`/`formatToParts()` **sem data** (formatam "agora"), `Temporal.Now.*` —, sorteios — `Math.random`, `crypto.getRandomValues`, `crypto.randomUUID` — e agendadores que rodam fora de `seek` — `MessageChannel`/`MessagePort.postMessage`, `window.postMessage`, `BroadcastChannel.postMessage`, `scheduler.postTask`, `new Worker`, `queueMicrotask` encadeado sem fim — são interceptados pelo palco **antes** de a cena ser importada; continuam funcionando (a cena monta), mas cada uso vira violação do auditor com arquivo e linha (`casos.js:34  API proibida: Math.random ×10 — … aleatoriedade só por ctx.rng(semente)`). Biblioteca de terceiros que use relógio (d3-timer, GSAP) cai aqui: calcule o estado você mesmo a partir de `t`. `Intl.DateTimeFormat` com data explícita (`fmt.format(new Date(2024, 0, 15))`) e `queueMicrotask` avulso passam.
- **Nada se mexe fora de `seek(t)` — nem dentro de `data-da-livre`.** `data-da-livre` libera **cor**, não relógio. Reprovam em qualquer lugar da página: SMIL (`<animate>`, `<animateTransform>`, `<animateMotion>`, `<set>`), `<marquee>`, `<video>`/`<audio>` tocando, `contenteditable` com foco (cursor piscando) e **imagem animada** — GIF, APNG, WebP animado, AVIF em sequência e SVG com animação, em `<img>`, `<image>`, `background-image`, `content`, `list-style-image` ou máscara; o motor confere o arquivo no disco (`IMAGEM ANIMADA — 1 imagem(ns) de casos2.js anima(m) no relógio do navegador, fora de seek(t): GIF animado: …/anima é.gif`), então GIF lento também é pego. Por fim, a **checagem de quietude**: com o mesmo `seek(t)`, dois retratos separados por 120 ms têm de ser idênticos, e repetir o `seek(t)` não pode mudar nada — é a rede para o que nenhuma lista cobre (laço por promessa, `ResizeObserver` que se realimenta, timer de um iframe): `PEÇA INQUIETA — em t=0.5 s, dois retratos do MESMO instante, sem nenhum seek entre eles, saíram diferentes`, com os dois PNG em `da/build/depurar/quietude_{a,b}.png`. Footage em movimento não entra na peça HTML: componha no ffmpeg (`video.compor_overlay`, `video.encaixar_em_janela`).
- **Duração própria (opcional).** `export function duracao({ DA, params, formato, pedida }) { return segundos; }` — o motor chama **no Node, antes do browser**, e usa o valor como duração da peça (`pedida` = o `--dur` da linha de comando, ou `null`). Serve a cena cujo tempo é consequência dos tokens de movimento: é assim que `teste_movimento` garante que nenhuma entrada é cortada em DA lenta. A função é pura (só `DA` e `params`; nada de DOM) e o mesmo cálculo deve ser usado dentro de `build`, com `ctx.duracao`.
- `build` retorna um objeto serializável (entra em `parametros.layout` do carimbo; devolva `fim_entrada` e `inicio_saida` em segundos — o auditor e a checagem de pureza amostram em volta deles); **sem** `transition` nem `animation` CSS; nunca o atalho CSS `text-wrap` (em Chromium ≥ 130 anula `white-space: nowrap`; use `text-wrap-style`); medidas com `offsetWidth/offsetHeight` (independem de `transform`, por isso a prancha consegue montar cenas em quadros reduzidos); elementos no DOM antes de medir; uma montagem por página quando o estado fica no módulo; erro lançado em `seek` sai em uma linha (`a cena lançou erro em seek(t=0.750): faltou o elemento X`).

## 10. `ctx` — o que a cena recebe

| grupo | membros |
|---|---|
| dimensões | `L`, `A`, `u` (lado menor), `fps`, `duracao` (= `DUR`, total da peça), `formato` (`'vertical'`, `'960x540'`…), `orientacao`, `transparente`, `params`, `DA` (o `window.DA`), `palco` |
| cor | `cor(token)` (paleta, `dado-N`, `neutro-N` ou hex **da DA**; outro hex → erro), `rgb(token)`, `alfa(token, a)` → `rgba(r, g, b, a)`, `dado(i)` (cíclico), `contraste(a, b)`, `legivel(fundo, a='texto', b='fundo')` |
| tipografia | `fonte(papel)`, `tam(nomeDaEscala)` → px, `estilo(el, papel, {tam, cor})` (classe `.da-<papel>`), `contorno(el, token, px)` (contorno de texto com a semântica da DA: `px` = espessura **externa** visível, cantos redondos; token em fração → `c.espessura * tamanhoPx`; ocupa o `text-shadow` do elemento — sombra projetada vai em `filter: drop-shadow()`), `texto(papel, str, {tam, cor, maxW, wrap, alinhar, classe, html})` → wrapper com `escala_x` por `scaleX`, `medir(w)` → `{w, h, linhas}`, `ajustar_texto(w, larguraMax, {min, alturaMax, maxLinhas})`, `sem_orfa(w)` |
| movimento | `ease(curva)`, `prog(t, t0, dur, curva='entrada')`, `lin(t, t0, dur)`, `dur(nome)` (**função** das `duracoes` da DA), `escalonamento`, `tl()` → `Timeline` (`add(nome, t0, dur, {curva, tipo})`, `escalonar(nomes, t0, dur, {passo})`, `p(t, nome)`, `lin`, `t0`, `t1`, `fim`, `ancoras()`), `entrada(el, p, tipo?, {dist, origem, n})`, `saida(el, p, tipo?, {dist, origem})`, `vida(el, t, {de, ate, entrada, saida})`, `fim_saida()` (= duracao − `dur('media')`), `transicao(camadaA, camadaB, p, tipo?, {origem})` e `dur_transicao(tipo?)` (§10.1) |
| layout | `margens(plataforma?)` → `{topo, direita, base, esquerda, plataforma, pedida}`, `area_segura(plataforma?)` → `{x, y, w, h, x1, y1, plataforma}`, **`area_livre(plataforma?, {legenda})`** → o mesmo retângulo **menos a faixa da legenda** + `{reservou, faixa_legenda, lado}` (`legenda`: `true`/`false`, ou `null` = conforme `legenda.reservar_em`; é a área que toda cena com texto deve usar — `const area = ctx.area_livre(p.plataforma || undefined, { legenda: p.reservar_legenda })`), `faixa_legenda(plataforma?)` → `{x0, y0, x1, y1, linhas, tamanho}` (pior caso da legenda da DA neste quadro; em Python `d.area_livre` / `d.faixa_legenda`, §3) (aceitam chave da DA ou nome canônico — `reels` = `instagram`, `youtube` = `padrao`; zona de outro formato cai no padrão deste e `.plataforma` diz qual foi usada; nome inexistente lança erro), `zona_proibida()` → `{x, y, w, h, x1, y1, canto}` em px deste quadro ou `null` (`thumbnail.zona_proibida` + `zona_proibida_tamanho`; em Python `d.zona_proibida(L, A)`), `plataformas()`, `grade()` → `{colunas, margem, calha, larguraCol, x(i)}`, `col(n)` (largura de n colunas), `margem`, `calha`, `raio`, `traco` (≥ 1 px) |
| peças do kit | `kit.legenda`, `kit.tarja`, `kit.credito`, `kit.moldura`, `kit.cena` — §10.1 |
| util | `px(fracao)` (do lado menor), `minimo_legivel` (px: `da.MINIMO_LEGIVEL` × lado menor — o piso ao encolher texto de apoio; é o `min` que a moldura passa a `ajustar_texto`), `el(tag, classe, texto)`, `svg(tag, atributos, filhos)`, `place(el, {x, y, w, h, direita, base})`, `rectDe(el)`, `esc`, `clamp`, `lerp`, `mapa`, `rng(seed)`, `bezier`, `grao(op)`, `sub({L, A, palco, dur, alfa})` (ctx aninhado) |

Entradas: `sobe desce desliza mascara escala fade digita`. `digita` revela caractere a caractere, **linha a linha**, com o corte na fronteira de cada glifo medida no próprio texto (em fonte proporcional nenhuma letra aparece pela metade e a 2ª linha só começa quando a 1ª terminou; sem cursor; o texto não é reescrito — só o `clip-path` muda). Saídas: `fade desce sobe mascara corte`. Sem `tipo`, `entrada`/`saida` usam `movimento.entrada_padrao`/`saida_padrao`. Curvas de ênfase podem passar de 1 (overshoot) — `entrada` tolera `p` até 2.

Desvios do contrato original (as irmãs seguem o código): `ctx.dur(nome)` é a função; a duração total é `ctx.duracao`/`ctx.DUR`. `ctx.alfa(token, a)` é a função rgba; o booleano de transparência é `ctx.transparente`.

### 10.1 Peças do kit em cena de outra skill (`ctx.kit`) e transição da DA (`ctx.transicao`)

Uma cena externa **não importa** arquivos do kit (`import { criarTarja } from '_tarja.js'` falha com "Cannot find package", e caminho absoluto embutiria o local do kit): as peças chegam por `ctx.kit`. Cada chamada devolve uma **instância nova** — várias por página —; ponha `el` no DOM, chame o método de medida e, em `seek(t)`, os métodos puros dela.

| chamada | devolve | para quê |
|---|---|---|
| `ctx.kit.legenda(palavras, {falada, plataforma, x, y, maxLinhas, linhas, largura})` | `{el, posicionar(), seek(indice, {pulso}), layout}` — `layout` = `{tamanho, encolheu, coube, linhas, caixa, palavras, vao, contorno_px, zona, dentro_da_zona}` em px do quadro | a legenda do bloco `legenda` da DA, **a mesma** que `texto.compor_legenda` desenha (§4): várias linhas, centrada e limitada à zona segura. `seek(-1)` = nenhuma palavra falada ainda; `plataforma: 'quadro'` = sem zona |
| `ctx.kit.tarja(texto, {tam, papel, inverter})` | `{el, medir(), seek(pBloco, pTexto)}` | etiqueta de `graficos.tarja` (sobretítulo, "AO VIVO"): o bloco abre antes do texto |
| `ctx.kit.credito(texto, {plataforma, area, prefixo, posicao, maxLinhas, larguraMax, reservar_legenda})` | `{el, texto, posicionar() → {faixa, em_cima, rect}, seek(p), sair(p)}` | crédito de fonte de `graficos.citacao_fonte` — papel, tamanho, cor, **prefixo** (token; não duplica se o texto já começa por ele) e as 7 posições, sempre dentro da zona e, sem `area`, fora da faixa da legenda (`ctx.area_livre`). É a peça que as cenas `barras` e `citacao` usam; em PIL, `texto.credito_fonte` (§4). `faixa` = altura a reservar no layout |
| `ctx.kit.moldura({rotulo, sub, area, estilo, inclinacao, plataforma, reservar_legenda})` | `{el, layout, seek(t), key(t), ancoras()}` — `layout.janela` e `layout.janela_girada` (`{cx, cy, w, h, angulo, cantos}`) | moldura de insert de `tratamento.moldura`; rótulo e sub dentro da zona segura; a janela girada alimenta `video.encaixar_em_janela` (§5.1) |
| `await ctx.kit.cena(nome, params, {palco, dur, L, A, alfa})` | `{meta, layout, ctx, seek(tLocal), key(tLocal), ancoras()}` | uma cena embutida inteira (`titulo`, `gc`, `moldura`, `citacao`, `barras`) montada numa camada da sua cena; cada chamada importa uma cópia própria do módulo, então duas instâncias convivem. `seek` em tempo local (0 … `dur`) |
| `ctx.transicao(camadaA, camadaB, p, tipo?, {origem})` | o tipo aplicado | troca entre duas camadas irmãs do tamanho do quadro em função **pura** de `p` (0 = só A, 1 = só B): `corte`, `fade`, `empurra`, `mascara`, `desliza`, `zoom` — os mesmos nomes de `video.juntar` (§5.3). Sem `tipo`, `movimento.transicoes.padrao`; fora de `movimento.transicoes.permitidas`, erro (`"empurra" não está em movimento.transicoes.permitidas da DA (corte, mascara, fade)`) |
| `ctx.dur_transicao(tipo?)` | segundos | 0 para `corte`, `movimento.duracoes.media` para as demais |

Exemplo executado (lint estrito sem achados; auditor e checagem de pureza ok no vídeo e nos quadros soltos; horizontal e vertical):

```js
// capitulo.js — cena de outra skill montada com as peças do kit (ctx.kit) e a transição da DA (ctx.transicao)
export const meta = {
  nome: 'capitulo',
  descricao: 'Abertura de capítulo (tarja + legenda + crédito) que troca para um gráfico de barras.',
  dur_padrao: 4,
  alfa_padrao: false,
  params: {
    titulo: { tipo: 'texto', obrigatorio: true },
    palavras: { tipo: 'lista', min: 1, itens: { tipo: 'texto' }, padrao: ['a', 'conta', 'não', 'fecha'] },
    dados: { tipo: 'lista', min: 1, obrigatorio: true,
      itens: { tipo: 'objeto', campos: { rotulo: { tipo: 'texto', obrigatorio: true }, valor: { tipo: 'numero', obrigatorio: true } } } },
    fonte: { tipo: 'texto', padrao: null },
    transicao: { tipo: 'opcao', opcoes: ['corte', 'fade', 'empurra', 'mascara', 'desliza', 'zoom'], padrao: null },
    plataforma: { tipo: 'plataforma', padrao: null },        // conferido antes do browser; 'uniao' num quadro horizontal vira 'padrao'
  },
};

const S = {};

export async function build(palco, p, ctx) {
  const plat = p.plataforma || undefined;
  const area = ctx.area_segura(plat);
  const camada = () => {                                     // duas camadas irmãs do tamanho do quadro: é o que ctx.transicao troca
    const e = ctx.el('div');
    Object.assign(e.style, { position: 'absolute', inset: '0', background: ctx.cor('fundo') });
    palco.appendChild(e);
    return e;
  };
  const A = camada(), B = camada();

  const tarja = ctx.kit.tarja(p.titulo);                     // graficos.tarja
  A.appendChild(tarja.el); tarja.medir();
  ctx.place(tarja.el, { x: area.x, y: area.y });
  const leg = ctx.kit.legenda(p.palavras, { falada: -1, plataforma: plat });   // a mesma legenda de texto.compor_legenda
  A.appendChild(leg.el); leg.posicionar();
  const cred = ctx.kit.credito(p.fonte || 'IBGE, 2024', { plataforma: plat }); // graficos.citacao_fonte (prefixo e posição da DA)
  A.appendChild(cred.el); cred.posicionar();

  const corte = ctx.duracao / 2;
  const barras = await ctx.kit.cena('barras', { dados: p.dados, fonte: p.fonte, plataforma: p.plataforma, casas: 2, prefixo: 'R$ ' },
    { palco: B, dur: ctx.duracao - corte, alfa: false });   // cena embutida inteira, com os params dela
  const tipo = p.transicao || ctx.DA.movimento.transicoes.padrao;
  Object.assign(S, { ctx, A, B, tarja, leg, cred, barras, corte, tipo, T: ctx.dur_transicao(tipo), n: p.palavras.length });
  return { legenda: leg.layout, credito: cred.rect, barras: barras.layout, corte: +corte.toFixed(3), transicao: tipo,
    fim_entrada: +(ctx.dur('curta') + ctx.dur('media')).toFixed(3), inicio_saida: +(corte + barras.layout.inicio_saida).toFixed(3) };
}

export function seek(t) {                                    // pura em t: cada peça recebe o estado completo a cada chamada
  const { ctx, A, B, tarja, leg, cred, barras, corte, tipo, T, n } = S;
  tarja.seek(ctx.prog(t, 0, ctx.dur('media')), ctx.prog(t, ctx.dur('curta'), ctx.dur('media')));
  leg.seek(Math.max(-1, Math.min(n - 1, Math.floor((t - 0.4) / 0.3))));       // índice da palavra falada (−1 = nenhuma ainda)
  cred.seek(ctx.prog(t, ctx.dur('curta'), ctx.dur('media')));
  barras.seek(Math.max(0, t - corte));                                         // tempo LOCAL da instância
  ctx.transicao(A, B, ctx.prog(t, corte - T / 2, T || 1e-6, 'suave'), tipo);   // fora de transicoes.permitidas da DA: erro
}

export function ancoras() {
  return [{ t: 0, nome: 'tarja', tipo: 'entrada' }, { t: +S.corte.toFixed(3), nome: 'transicao', tipo: 'enfase' }];
}
```

Render: `da.py render --cena animacoes/capitulo.js --saida "animacoes/capítulo 2.mp4" --formato 480x270 --dur 3 --fps 15 --params '{"titulo": "Capítulo 2", "transicao": "mascara", "dados": [{"rotulo": "Santa Catarina", "valor": 0.31}, {"rotulo": "Maranhão", "valor": 2.4}]}'` → 45 quadros em 2,4 s; em `--formato 540x960` com `"plataforma": "reels"` tarja, legenda, crédito e barras caem dentro da zona do Reels. Com `"plataforma": "uniao"` num quadro horizontal o motor avisa e usa `padrao`. O `layout` devolvido (legenda, crédito, barras, `corte`) vai para o carimbo.

## 11. Auditor (C3) — regras e o único escape

Antes de qualquer quadro ser gravado, `auditor.js` percorre a **página inteira** (`<html>`, `<body>`, o que a cena pendurar fora do `#palco`, shadow roots abertos e fechados) em vários instantes e lê os estilos **computados**. Não existe escape implícito: elemento com `opacity: 0`, `visibility: hidden`, `display: none`, fora do quadro ou com caixa zero é auditado igual — ele existe para aparecer em outro instante. A auditoria tem quatro partes, nesta ordem, e a linha de sucesso do render diz quantas amostras cada uma usou (`auditoria ok (29 instantes, pureza em 4, quietude em 1)`, GC de 4 s): **estilos** (este §), **pureza** (`seek(t)` não depende do seek anterior — §9), **imagens animadas** conferidas no disco e **quietude** (nada muda sem `seek` — §9).

**Instantes**: 0 e o fim; uma grade temporal (passo de 0,25 s em peça curta, 24 fatias em peça longa); cada âncora de `ancoras()` (o instante, +0,05 s e +0,25 s); `fim_entrada`, `inicio_saida` e `corte` devolvidos por `build` (−0,05, +0,05 e +0,15 s). Teto de 64 amostras (as âncoras ficam, a grade é rareada). Observado: GC de 4 s → 27 instantes; teste de movimento de 3 s → 24; antes eram sempre 5. Com `--quadro T`, só `T`. Custo medido em 1.5.1 (as quatro partes, contra o mesmo job com `--sem-auditoria` na mesma fila, neon-shorts): GC de 4 s a 960×540 em VP9 → 2,57 s contra 2,40 s (29 instantes, pureza em 4, quietude em 1); PNG do mesmo GC → 0,39 s contra 0,12 s — os 120 ms de espera da quietude são o grosso, e por isso prévia em lote de PNG fica mais lenta que em 1.5.0 (era +0,06 s).

**O que é conferido em cada elemento**: `background-color`; cores dentro de `background-image` e `border-image-source` (gradientes), `box-shadow`, `text-shadow`, `filter: drop-shadow()`; `border-*-color` (largura > 0 e estilo ≠ none); `outline-color`; `column-rule-color`; em elementos **com texto direto**: `color`, `text-decoration-color`, `-webkit-text-stroke-color`, `-webkit-text-fill-color`, `text-emphasis-color` e a **primeira família** do `font-family` computado; em formas SVG (inclusive dentro de `<defs>`/`<symbol>`/`<pattern>`): `fill`, `stroke` (com largura); `stop-color` de gradientes SVG, `flood-color`, `lighting-color`; `transition` com duração > 0 e `animation` declaradas; `document.getAnimations()`. **Pseudo-elementos** `::before` e `::after` com `content` passam pelas mesmas regras (e `::first-letter`, `::first-line` quando alguma folha de estilo os cita). Item de lista (`display: list-item`, inclusive `<summary>`): a cor do `::marker` — a bolinha é pintada com a cor do **item**, mesmo quando o texto dentro dele tem outra — ou a imagem de `list-style-image`. **O que o estilo computado não mostra** é tratado caso a caso (desde 1.5.1): controles nativos, imagem trocada por CSS (`content: url()` no próprio elemento, `paint()`), texto selecionado, realce por `CSS.highlights` e emoji — todos na tabela abaixo.

**O que reprova sempre** (fora de `data-da-livre`):

| situação | mensagem |
|---|---|
| cor fora de paleta + `dados` + `neutros` (tolerância 3 por canal; qualquer alfa das cores da DA passa, inclusive `color-mix(in srgb, var(--da-cor-primaria) 50%, transparent)`, que computa como `color(srgb …)`) | `cor fora da DA; mais próximo: negativo #E5484D (Δ 77)` |
| fonte fora dos papéis, ou genérica | `fonte fora da DA` / `fonte genérica (nenhum papel da DA aplicado)` |
| `<img>`, `<video>`, `<canvas>`, `<image>` e `<feImage>` de SVG, `<iframe>`, `<object>`, `<embed>` | `conteúdo que o auditor não enxerga … declare data-da-livre="foto\|logo\|captura…" no elemento` |
| controle nativo: `<input>` (checkbox, range, texto…), `<progress>`, `<meter>`, `<select>`, `<datalist>`, `<textarea>`, `<button>`, `<audio>` — quem pinta é o tema do navegador, e essas cores não aparecem em `getComputedStyle` (na verificação da 1.5.0 um `<progress>` saiu com 5 740 px de azul `(0, 117, 255)` e carimbo `auditoria: ok`); `accent-color` não muda isso | `<progress> (controle nativo): 0.7 — controle nativo: quem pinta é o tema do navegador … desenhe com div/svg e tokens, ou declare data-da-livre="captura de interface" no elemento` |
| `background-image`/`border-image` com `url()`; `content: url()` **no próprio elemento** (troca o conteúdo por uma imagem); `list-style-image` | `imagem por url() fora de data-da-livre — o auditor não enxerga os pixels` |
| imagem desenhada por código: `background-image: paint(…)` (CSS Houdini) | `imagem desenhada por código (paint() do CSS Houdini) — o auditor não enxerga os pixels` |
| `content: url()` em `::before`/`::after` | `imagem por url() em pseudo-elemento não pode ser declarada livre — use um elemento de verdade com data-da-livre` |
| marcador de lista com cor de fora (o `<ul>` com `color` literal e o texto em token dentro de um `<span>`) | `li::marker  color: rgb(255, 0, 0) — cor fora da DA; mais próximo: negativo #E5484D (Δ 77)` |
| texto **selecionado** (`getSelection()` com intervalo ativo — é pintado com as cores do sistema ou de uma regra `::selection`) e realce por `CSS.highlights` | `::selection: texto selecionado — … para marca-texto use um <span> com fundo em token; chame getSelection().removeAllRanges()` |
| emoji de apresentação colorida em texto ou em `content` (🔥, ✅, bandeiras, sequência com U+FE0F) — desenhado pela fonte de emoji do sistema; `✓ ✕ →` e outros símbolos de texto passam | `emoji: 🔥 — emoji é desenhado pela fonte de emoji do sistema, com cores que não são da DA — use um ícone SVG com tokens, ou envolva o emoji em <span data-da-livre="emoji">` |
| `filter`/`backdrop-filter` com `hue-rotate`, `invert`, `sepia`, `saturate`, `grayscale`, `contrast`, `brightness`, ou filtro SVG por `url()` (`blur()`, `opacity()` e `drop-shadow()` com cor da DA passam) | `hue-rotate() altera a cor do que está embaixo: o resultado sai da paleta` |
| `mix-blend-mode` ≠ normal, `background-blend-mode` ≠ normal | `mistura altera a cor do que está embaixo` |
| `transition`/`animation` CSS, `el.animate()` | `transition CSS declarada (proibida: o motor chama seek(t) fora de ordem)` |
| animação que não é CSS — **também dentro de `data-da-livre`**: SMIL (`<animate>`, `<animateTransform>`, `<animateMotion>`, `<set>`), `<marquee>`, `<video>`/`<audio>` tocando, `contenteditable` com foco | `<animate> (SMIL): attributeName=x dur=0.7s repeatCount=indefinite — animação SMIL roda no relógio do navegador, fora de seek(t): cada render sai diferente … (data-da-livre não libera animação)` |
| API de tempo, de acaso ou de agendamento usada pela cena (lista no §9), no build, em `seek` ou entre seeks | `casos2.js:19  API proibida: MessageChannel.postMessage ×129 — … chamada pela cena (entre seeks): a peça tem de ser função pura de t` |
| imagem animada (GIF, APNG, WebP, AVIF em sequência, SVG com animação), **mesmo em `data-da-livre`** — conferida no arquivo, depois dos estilos | `IMAGEM ANIMADA — … GIF animado: <arquivo>` / `Use um quadro parado (PNG/JPG) ou componha o trecho em vídeo no ffmpeg` |
| qualquer coisa que mude a tela sem `seek` (checagem de quietude, por último) | `PEÇA INQUIETA — em t=0.5 s, dois retratos do MESMO instante, sem nenhum seek entre eles, saíram diferentes: algo anima no relógio do navegador` |
| declaração de cor que o navegador descarta: `rgb(var(--da-cor-fundo-rgb) / 0.86)` (inválida depois de trocar as variáveis), `var(--da-cor-primara)` (variável que não existe), `style="background: rgb(10 10 / .5)"` | `declaração inválida depois de trocar as variáveis (vira "rgb(10, 10, 10 / 0.86)"): o navegador descarta e a cor computa transparente/herdada — cor da DA com alfa tem UMA forma: rgba(var(--da-cor-<nome>-rgb), a)` |
| `data-da-livre` no `#palco`, no `<body>` ou no `<html>` | `liberaria a peça inteira — marque só o elemento da foto, do logo ou da captura` |

**Cor da DA com transparência** (D6): no CSS, `rgba(var(--da-cor-<nome>-rgb), a)` — as variáveis `-rgb` valem `r, g, b` com vírgulas, e medido no Chromium do kit `rgba(var(--da-cor-primaria-rgb), 0.5)` computa `rgba(255, 199, 0, 0.5)`; em cena, `ctx.alfa(token, a)`. `color-mix(in srgb, var(--da-cor-x) 50%, transparent)` também passa no auditor, mas não é a forma da casa. A forma com barra (`rgb(var(--…-rgb) / a)`) é inválida depois da substituição: sem o auditor a peça sairia com o fundo transparente e nenhum erro — transparente é "cor permitida" —, por isso o auditor refaz cada declaração de cor com `var()` (estilo inline e folhas de estilo, inclusive em shadow roots) e pergunta ao navegador (`CSS.supports`) se o resultado vale. O que ele **não** detecta: declaração inválida sem `var()` escrita numa folha de estilo ou atribuída por `el.style.x = …` (o navegador a joga fora no parse e ela some do CSSOM) — essas o lint pega quando é a forma com barra.

**O único escape**: `data-da-livre="motivo"` no elemento (vale para a subárvore) — foto, logo de terceiros, captura de tela, gráfico em canvas, controle nativo numa captura de interface, emoji. Ele libera **cor e fonte**, não movimento: SMIL, mídia tocando, imagem animada e a checagem de quietude valem também lá dentro. O auditor pula a subárvore e **registra** o elemento em `parametros.livres` do carimbo (§7); o render mostra `· 1 elemento(s) data-da-livre: img (foto de teste)`. A camada de grão criada pelo kit (`meta.grao` / `ctx.grao()`) é a única exceção embutida: o auditor a reconhece pelo objeto, não pela classe, e não a lista. `--sem-auditoria` gera a peça, mas o carimbo sai `auditoria: "pulada"` e `conferir-carimbo` reprova.

Nada reprovado é gravado; código 1. Quando o auditor reprova, a resposta certa é **trocar o valor pelo token** (`ctx.cor`, `var(--da-*)`, `.da-<papel>`) ou, se a cor é mesmo necessária e não existe, **propor o token na DA** (nova revisão). Não é esconder com `data-da-livre` em coisa que não é foto: a conferência final mostra a lista.

Casos executados em `testes/test_motor_robustez.py` (`test_12`): 30 que têm de reprovar (alfa com barra inline e em folha de estilo, variável inexistente, declaração inválida no atributo `style`, pseudo-elemento, elemento fora do palco, fundo do body, shadow root fechado, canvas, `stop-color`, forma em `<defs>` usada por `<use>`, `<img>`, `<image>`, `url()`, `border-image`, `hue-rotate`, `backdrop-filter`, `drop-shadow` com cor de fora, `mix-blend-mode`, `data-da-livre` no palco, `opacity: 0`, `display: none`, elemento visível só de 31 % a 36 % da peça, cor trocada só de 50 % a 58 %, e as seis APIs de tempo/acaso) e 7 que têm de passar (`rgba(var(--da-cor-…-rgb), a)` inline e em folha de estilo — com o valor computado conferido —, `color-mix` com transparent, `ctx.alfa`, `drop-shadow` com cor da DA + `blur`, `<img>` e `<canvas>` com `data-da-livre`, `ctx.rng`). Em `test_20` (1.5.1), mais 35 que têm de reprovar — cada um conferido pelo **motivo** no bloco de log do próprio job — e 9 que têm de passar: SMIL (solto, dentro de `data-da-livre` e `<set>`), `<marquee>`, laço por `MessageChannel` e por `window.postMessage`, laço por promessa (pego pela quietude), `crypto.getRandomValues`, `crypto.randomUUID`, `document.timeline.currentTime`, `performance.now` pelo protótipo, `event.timeStamp`, `Intl.DateTimeFormat` sem data, `Temporal.Now`, `queueMicrotask` em laço, `seek` que sorteia, GIF e APNG animados (em `<img>` e em `background-image`, com `data-da-livre`), SVG animado em `<img>`, `contenteditable` com foco, `content: url()` no elemento, `paint()`, `list-style-image`, marcador com cor de fora, `<progress>` (com e sem `accent-color`), `<meter>`, checkbox, range, `<select>`, `<textarea>`, `<button>`, seleção com regra `::selection` e emoji; passam: listas com cor em token, emoji e `<progress>` com `data-da-livre` (e ficam em `parametros.livres`), GIF de um quadro só, `mask-image` com `url()` (máscara só mexe em alfa), `queueMicrotask` avulso, SVG parado, símbolos de texto e `Intl.DateTimeFormat` com data explícita.

**O que o auditor não faz** (limites conhecidos, para não contar com ele onde ele não chega): não lê pixels — só estilos, estrutura e comportamento; uma cor de fora que só exista dentro de um elemento `data-da-livre` passa, e é por isso que a lista `livres` vai para o carimbo e a conferência final a mostra. A quietude é medida num instante só (o repouso, ou o `T` de `--quadro`): animação por caminho não listado que só comece depois escapa dela — as listas de API e a regra estrutural (SMIL, mídia, imagem animada) é que cobrem a duração inteira. As barras de rolagem não aparecem porque o Chromium do kit roda com `--hide-scrollbars`; fora do motor, `overflow: scroll` desenharia cinzas do sistema.

## 12. Lint (C2) — o que pega, o que não lê e como escapar

**O que ele lê**: `.html .htm .svg` (marcação + `<style>` + `<script>`), `.css`, `.js .mjs .cjs`, `.json` e `.py`. **O que ele não lê nunca sai como conferido**: vai para `nao_conferidos` (linha `NÃO CONFERIDO` na CLI), fica fora da contagem e reprova com `--estrito` — arquivo passado pelo nome com outra extensão (`.md`, `.png`, sem extensão), fonte de peça em linguagem não coberta achada dentro de uma pasta (`.ts .tsx .jsx .vue .svelte .scss .sass .less .xml .yaml .toml .sh .swift .rb .php .ipynb .ass`…; mídia e documentos numa pasta são ignorados em silêncio), Python com erro de sintaxe, arquivo > 2 MB ou ilegível. Antes de 1.3.0, `lint thumbs/thumb.py` respondia "1 arquivo(s) conferido(s): 0 violação(ões). Nenhuma cor ou fonte literal." para um arquivo cheio de `(255, 0, 0)`.

**Python** (análise pela árvore sintática, não por regex) — o que reprova:

| regra | o que é pego | exemplo |
|---|---|---|
| `cor-hex` | string que É um hex (`#RGB`, `#RRGGBB`, com alfa), em qualquer lugar; hex de 6/8 dígitos em contexto CSS dentro de um texto | `COR = "#00FF00"`, `fill="#FFC700"` |
| `cor-tupla` | tupla/lista de 3 ou 4 inteiros 0–255 **em contexto de cor**: argumento de chamada de desenho (`Image.new(modo, tam, COR)`, `ImageDraw.*(xy, COR…)`, `paste(COR, caixa)`, `ImageOps.colorize`, `np.full(forma, COR)`), `putpixel(xy, COR)`, argumento nomeado de cor (`fill=`, `outline=`, `stroke_fill=`, `color=`, `cor_*=`), variável/atributo/chave de dict/padrão de parâmetro com nome de cor (`FUNDO =`, `cor_texto =`, `highlight =`, `ACENTO =`, `{"sombra": …}`, `def f(cor=…)`) e fatia de array preenchida (`arr[:] = (255, 0, 0)`, `arr[y0:y1, x0:x1] = …`; índice simples como `pontos[0] = (1, 2, 3)` não conta) | `Image.new("RGB", t, (255, 0, 0))`, `PALETA = {"primaria": (255, 199, 0)}` |
| `cor-nome` | nome CSS de cor nesses mesmos contextos | `outline="red"`, `ImageColor.getrgb("navy")` |
| `cor-ffmpeg` | cor literal em filtro ffmpeg montado em texto (`color=`, `c=`, `fontcolor=`, `bordercolor=`…) | `"pad=…:color=black"`, `"color=c=#112233"` |
| `cor-funcao`, `cor-nome`, `fonte-literal`, `alfa-invalido` | CSS/SVG/HTML montado em string passa pelas regras de CSS e de marcação | `'<rect fill="blue"/>'`, `"font-family: Arial"` |
| `fonte-literal` | `ImageFont.truetype(...)`/`FreeTypeFont(...)` com caminho literal (string, f-string, `Path("…")`), `ImageFont.load_default()`, e qualquer string que termine em `.ttf .otf .ttc .woff .woff2` | `ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)` |

Não reprova: `d.rgb(…)`, `d.rgba(…)`, `d.cor(…)`, `d.fonte_pil(…)`, `texto.Estilo.do_papel(…)`, f-string com token (`f"color={d.cor('fundo')}"`), `(0, 0, 0, 0)` (transparente), inteiro de máscara (`Image.new("L", t, 0)`), tuplas de tamanho/caixa/ponto (`(1280, 720)`, `(0, 0, 100, 50)` como primeiro argumento de desenho), docstrings e textos comuns (`"Top #100"`). A sugestão já vem na forma de Python: `use d.cor("primaria") / d.rgb("primaria") — é exatamente o token primaria (#FFC700)`; com alfa, `d.rgba("neutro-1", 0.502)`. Escape: `# da-livre` na linha do literal ou na primeira/última linha da instrução; `# da-livre:inicio` … `# da-livre:fim`; `da-livre-arquivo` nas 10 primeiras linhas. Limite conhecido: cor montada por conta (`tuple(int(x * 255) for x in …)`), tupla em variável sem nome de cor (`A = (255, 0, 0)` usada depois como `fill=A`), hex sem `#` (`"FFC700"`, `0xFFC700`), `np.array([255, 199, 0])` solto e literal passado por posição a uma função sua escapam — peça em PIL não passa pelo auditor C3, então o lint é a única barreira: dê nome de cor às variáveis de cor.

**HTML, CSS, JS, JSON, SVG** — por expressões regulares (não é parser): HTML (atributos `fill`, `stroke`, `color`, `bgcolor`, `style=`), CSS (declarações de cor, `font-family`, `border: 1px solid #333`), JS (`style.color = "tomato"`, `fontFamily = "Arial"`, hex como string inteira ou em contexto CSS), JSON (chaves de cor como `cor`, `cor_fundo`, `color`, `fill`, `background`; chaves de fonte `font_family`, `fontFamily`, `familia`), SVG. Não acusa: `var(--da-*)`, `url(...)`, chaves de referência (`id`, `href`, `alvo`, `seletor`…), `"Top #100"` dentro de string comum, hex em arquivos gerados do build. Escapes: comentário `da-livre` na linha; par `da-livre:inicio` … `da-livre:fim`; `da-livre-arquivo` nas 10 primeiras linhas; atributo `data-da-livre`, que libera **o elemento e a subárvore** (da tag de abertura à de fechamento; elemento vazio ou `/>`: só a tag) — não o resto da linha, e também vale para marcação montada em texto de JS/Python. `el.setAttribute('data-da-livre', …)` numa linha de JS não libera nada no lint (é para o auditor). **`alfa-invalido`**: `rgb(var(--da-cor-x-rgb) / a)` e `rgba(var(--da-…-rgb) / a)` são acusados em qualquer contexto com a correção pronta (`use rgba(var(--da-cor-x-rgb), a)`); toda sugestão de cor com alfa do lint sai nessa forma. Desde 1.2.0 também acusa: chave de cor em objeto JS (`{ fundo: 'navy' }`, `corBorda`, `strokeColor`), nome de cor dentro de propriedade composta em JS (`style.boxShadow = '0 0 4px black'`, `border`, `background = 'linear-gradient(red, …)'`), `color(display-p3 1 0 0)`, e no JSON nomes dentro de valor composto de chave de cor (`"background": "linear-gradient(red, blue)"`) e CSS em chaves `style`/`css`/`estilo`; e deixou de acusar `content: "red #fff"` (texto) e argumentos de `console.*`. "é exatamente o token X" só aparece quando o hex é o mesmo; cor vizinha sai como "token mais próximo (ΔE n)". Código exótico (CSS-in-JS gerado, cor montada por concatenação, template literal com `${}`) pode escapar ou dar falso positivo — o auditor pega no render o que o lint deixou passar.

## 13. `da/build/` — o que cada consumidor lê

| arquivo | consumidor | conteúdo |
|---|---|---|
| `da.resolvida.json` | Python (`da.carregar`), conferência final | herança aplicada, padrões do esquema, `<cor>_hex`, `<arquivo>_abs`, fontes inspecionadas (`variavel`, `eixos_fonte`, `eixos_efetivos`, `css_variacao`), `formatos.*.fps_num/fps_den/fps_float/lado_menor`, `cor.permitidas`, `cor.gradientes.<n>.css`, `_meta` |
| `da.css` | peças HTML, motor | `@font-face` por papel (URL `file://` codificada — espaços viram `%20` —, `font-weight: 100 900`, `font-stretch` para variáveis), `:root` com `--da-cor-<chave>`, `--da-cor-<chave>-rgb` (`10, 10, 10` — com vírgulas, para `rgba(var(--da-cor-<chave>-rgb), a)`, a única forma de alfa; `-rgb` existe também para `--da-dado-<n>` e `--da-neutro-<n>`), `--da-dado-<n>`, `--da-neutro-<n>`, `--da-gradiente-<nome>`, `--da-fonte/peso/largura/estilo/tracking/caixa/altura-linha/eixos/escala-x-<papel>`, `--da-escala-<nome>` (`calc(var(--da-lado) * 0.078)`), `--da-margem`, `--da-calha`, `--da-raio`, `--da-traco`, `--da-sombra`, `--da-dur-<nome>` (`0.36s`), `--da-escalonamento`, `--da-curva-<nome>` (`cubic-bezier(…)`); classes `.da-titulo .da-subtitulo .da-corpo .da-dados .da-legenda`. Fora do motor, defina `--da-lado` em px (lado menor do quadro) no `:root` da sua página. |
| `da.js` | peças HTML fora do motor | `window.DA` congelado (= resolvida) com `_meta` |
| `grade.json` | `video.filtro_tratamento`, `da.py grade`, video-broll | por formato: `cadeia`, `cadeia_cor`, `cadeia_acabamento`, `retorno`, `neutro`, `passos` (token → filtro); `velocidade` (setpts/atempo fora da cadeia de cor); `mapeamento` (regras token → filtro, com as aproximações: temperatura > 0 → 3500 K, < 0 → 12000 K com `mix = |t|/100`; exposição = ganho 2^(EV/2,2) em YUV) |
| `da.lock` | `precisa_compilar` | sha da DA e dos ancestrais, `gerador_sha256` (inclui o próprio `da.py`: atualizar o kit faz o primeiro `carregar()` recompilar), `kit_versao`, `compilado_em` |
| `../DA.md` | humanos, `@da/DA.md` no CLAUDE.md | conceito, faça/não faça, paleta com hex e contraste, tipografia, movimento, tratamento, legenda (com a linha `Faixa da legenda reservada … em: vertical, quadrado. Em horizontal as peças **não** desviam …` — é por ela que uma sessão que só leu o CLAUDE.md fica sabendo), formatos, "como as peças usam a DA" |

## 14. Convenções de saída e de memória

- **`.parcial`**: todo arquivo pesado nasce como `<saida>.parcial` (motor) ou `<nome>.parcial<ext>` (`video.executar`) e é renomeado só com rc 0 — no motor, só depois do ffprobe e do carimbo (falhou antes: a saída anterior e o carimbo dela ficam intactos). Interrupção por sinal apaga o `.parcial`; um que sobre é de processo morto por SIGKILL e pode ser apagado. `conferir-carimbo` ignora os dois formatos de nome. Não use a existência do `.parcial` como sinal de "o render começou": o ffmpeg só cria o arquivo depois de sondar a entrada (~5 s de peça ou 5 MB) — numa peça de 4 s a 480×270 ele apareceu só no fim.
- **Sidecar** `<saida>.da.json` ao lado de cada peça; nunca o apague nem o copie para outra peça. Pasta de quadros PNG: carimbe a pasta.
- **Intermediário começa por `_`.** Pasta ou arquivo cujo nome começa por sublinhado — `animacoes/_trabalho/`, `legendas/_png/cue 0.png`, `render/_base.mp4`, `qa/_q 0.6.png` — é material de trabalho, não peça: `conferir-carimbo` e o `lint` passam por cima ao varrer pastas (o lint anota `N intermediário(s) com prefixo _ fora do lint`) e ninguém precisa carimbá-lo. Passado **pelo nome**, o arquivo é conferido e lido normalmente. O que sai de `video.executar` e `video.extrair_quadro` não leva carimbo: ou é intermediário (nome com `_`), ou você carimba (`d.carimbar(saida, "minha-skill", insumos=[…])`). Até 1.3.0 a base recortada e os quadros soltos de uma skill eram reprovados como `SEM CARIMBO`.
- **`broll/bruto/` × `broll/tratado/`** (o `init` cria as duas): o material baixado fica em `broll/bruto/` e nunca é conferido; o tratado (`da.py grade --saida broll/tratado/…`) é peça, carimbada, e entra na varredura padrão de `conferir-carimbo` junto com `animacoes legendas cortes thumbs render`.
- **Formatos**: vídeo opaco H.264 yuv420p bt709 +faststart (`video.args_encode`); overlay com alfa `.webm` VP9 (compor via ffmpeg, lendo com `-c:v libvpx-vp9`) ou `.mov` ProRes 4444 (Premiere); imagem PNG RGBA. Fps racional da DA (`30000/1001` por padrão).
- **Memória**: um Chromium ou um ffmpeg por vez, sempre pela trava; `-threads 2`; prévias com `--escala 0.5`; testes ≤ 3 s e ≤ 960×540; apague saídas de teste > 5 MB.
- **Intermediários e bytecode**: nenhum script do kit grava `__pycache__` dentro da skill; a licença de cada fonte fica em `<pasta da fonte>/LICENCAS/OFL-<Prefixo>.txt` (prefixo = nome do arquivo até o primeiro hífen) e viaja com `init` e `salvar-preset` — se a sua skill copiar uma fonte para outro lugar, copie a licença junto (`da.licenca_da_fonte(arquivo)`).
- **Caminhos** com espaço e acento funcionam em tudo (testado em `projeto teste/`, `vídeo 2 do canal/`, `thumbs/citacao prova.png`); sempre cite caminhos entre aspas no shell.
- **Variáveis**: `DA_JSON` (sobrepõe a descoberta), `VIDEO_OPS_PYTHON` (Python que o `kit/bin/da` usa, sem conferir), `VIDEO_OPS_HOME` (biblioteca de presets; em testes aponte para a área de teste), `VIDEO_OPS_CHROME`, `VIDEO_OPS_NODE`, `VIDEO_OPS_FFMPEG`/`VIDEO_OPS_FFPROBE`, `VIDEO_OPS_INATIVIDADE` (segundos do vigia de inatividade de todos os comandos do kit; `0` desliga), `VIDEO_OPS_TRAVA` (interna, não defina), `VIDEO_OPS_TRAVA_ARQUIVO` (troca o arquivo da trava — só em testes de travamento, para não segurar a fila real), `DA_DEBUG=1` (traceback em erro interno).

## 15. Estender o `da.py` com um subcomando da sua skill

Crie `da_ext_<nome>.py` ao lado de `da.py` (só dentro do kit) ou chame em runtime:

```python
import da
def _cfg(p): p.add_argument("entrada")
def _cmd(args): d = da.carregar(getattr(args, "da", None), de=getattr(args, "de", None)); …; return 0
da.registrar_subcomando("meu-comando", "ajuda curta", _cfg, _cmd, descricao="texto longo", repasse=False)
```

Toda extensão ganha `--da`/`--de`, a tradução de erros do argparse, "sem DA = código 2" e as exceções `DAErro`. `repasse=True` é para subcomandos que repassam argumentos a outro programa (positional `argumentos` com `nargs="..."`): opções desconhecidas vão para `args.argumentos` em vez de dar erro 64 — é como `render` funciona. É assim que `da_ext_motor.py` acrescenta `prancha`, `teste-movimento` e `render`, e `da_ext_conferencia.py`, o `conferencia` (§18); dele também se importa `render(args, da_obj=d, capturar=True, inatividade=180, validar_antes=None)` (devolve um `trava.Resultado`, lido como um `CompletedProcess`: `.returncode`, `.stdout`, `.stderr`, mais `.motivo`; `validar_antes` = conferir os argumentos fora da fila antes de entrar na trava — `None` confere só quando a trava está ocupada, `True` sempre, `False` nunca; `--validar` nos argumentos nunca entra na trava), `gerar_prancha(d, formatos, referencia, foto, saida_pasta)`, `imagem_de_teste(destino)` e `achar_node()`.

## 16. Receita executada — legenda karaokê queimada num corte (video-legendas, video-cortes-verticais)

O script abaixo foi rodado como está de dentro de uma skill vizinha (`<skills>/video-legendas/scripts/legendar.py`), num projeto com espaço e acento no caminho, e passou em `da.py lint --estrito`. Ele usa só a API deste arquivo: `da.carregar` (Passo 0), `texto.estados_da_legenda` (uma imagem pequena por **estado** da cue, conforme `legenda.estilo`, sempre dentro da zona segura), `video.filtro_recorte` + `video.filtro_tratamento` (a base horizontal vira vertical já tratada) e `video.compor_cues` (tudo queimado numa passada, com carimbo e proveniência).

```python
#!/usr/bin/env python3
# legendar.py — legenda karaokê queimada num corte, numa passada de ffmpeg (receita do kit-api.md §16)
import argparse
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[2] / "video-direcao-de-arte" / "kit"
if not (KIT / "da.py").is_file():
    KIT = Path(os.environ["CRIABR_SKILLS"] + "/video-direcao-de-arte/kit").expanduser()
sys.path.insert(0, str(KIT))
import da, texto, video  # noqa: E402


def segmentar(palavras, max_palavras, pausa=0.6):
    """Palavras [{a, b, w, p}] → cues [[palavra, …], …]: até max_palavras por cue; pausa longa ou pontuação final fecha a cue."""
    cues, atual = [], []
    for p in palavras:
        if atual and (len(atual) >= max_palavras or p["a"] - atual[-1]["b"] > pausa or atual[-1]["w"][-1:] in ".!?:"):
            cues.append(atual)
            atual = []
        atual.append(p)
    if atual:
        cues.append(atual)
    return cues


def estados(cue, fim, d, L, A, plataforma):
    """Uma cue → overlays [{imagem, t0, t1, x, y}]: um por estado de legenda.estilo (karaoke e palavra: um por palavra; bloco: um só)."""
    limpa = [p["w"].strip(".,;:!?") for p in cue]
    saida, infos = [], []
    for img, info in texto.estados_da_legenda(limpa, d, L, A, plataforma=plataforma):   # recortes pequenos + onde colar
        i = info["indice"]
        t0 = cue[0]["a"] if i is None else cue[i]["a"]
        t1 = fim if i is None or i + 1 >= len(cue) else cue[i + 1]["a"]                  # a palavra fica acesa até a próxima começar
        saida.append({"imagem": img, "t0": t0, "t1": t1, "x": info["x"], "y": info["y"]})
        infos.append(info)
    return saida, infos


def main():
    ap = argparse.ArgumentParser(description="Queima legenda palavra a palavra num corte, com os tokens `legenda` da DA.")
    ap.add_argument("base", help="vídeo do corte")
    ap.add_argument("palavras", help='JSON da transcrição: [{"a": início_s, "b": fim_s, "w": "palavra", "p": confiança}]')
    ap.add_argument("saida", help="vídeo legendado (ex.: legendas/corte 01 legendado.mp4)")
    ap.add_argument("--inicio", type=float, default=0.0, help="início do trecho na base, em segundos (os tempos das palavras são da base)")
    ap.add_argument("--duracao", type=float, default=None, help="duração do trecho")
    ap.add_argument("--formato", default="vertical", help="formato da DA ou LxA do quadro de saída")
    ap.add_argument("--plataforma", default=None, help="zona segura: uniao (padrão do vertical), reels, tiktok, shorts")
    args = ap.parse_args()

    d = da.carregar()                                 # Passo 0: sem DA sai com código 2; a identidade do carimbo é a deste instante
    L, A = d.dimensoes(args.formato)
    s = video.sondar(args.base)
    fim_trecho = args.inicio + (args.duracao or s["duracao"] - args.inicio)
    palavras = [p for p in json.loads(Path(args.palavras).read_text(encoding="utf-8")) if args.inicio <= p["a"] < fim_trecho]
    if not palavras:
        raise da.DAErro("nenhuma palavra da transcrição cai no trecho pedido")
    cues = segmentar(palavras, d["legenda"]["max_palavras"])
    overlays, menor = [], 1.0
    for n, cue in enumerate(cues):
        proxima = cues[n + 1][0]["a"] if n + 1 < len(cues) else fim_trecho
        fim = min(cue[-1]["b"] + 0.25, proxima)        # segura a cue 0,25 s depois da última palavra, sem invadir a seguinte
        ests, infos = estados(cue, fim, d, L, A, args.plataforma)
        for e in ests:                                 # compor_cues conta o tempo a partir de `inicio`
            e["t0"], e["t1"] = e["t0"] - args.inicio, e["t1"] - args.inicio
        overlays += ests
        menor = min(menor, *(i["tamanho_fracao"] for i in infos))
        fora = [i for i in infos if not i["dentro_da_zona"] or not i["coube"]]
        if fora:
            print(f"aviso: a cue {n} não coube na zona segura nem no tamanho mínimo: {' '.join(p['w'] for p in cue)}", file=sys.stderr)

    # base de outra proporção: recorte para o quadro de saída + tratamento da DA, tudo na mesma passada
    cadeia = None
    if (s["largura"], s["altura"]) != (L, A):
        rec = video.filtro_recorte((s["largura"], s["altura"]), (L, A), d["tratamento"]["recorte"]["ancora"])
        cadeia = rec["filtro"] + "," + video.filtro_tratamento(d, f"{L}x{A}")
    r = video.compor_cues(args.base, overlays, args.saida, da_obj=d, inicio=args.inicio or None, duracao=args.duracao,
                          tratamento_base=cadeia, tamanho=(L, A), ferramenta="video-legendas",
                          parametros={"palavras": Path(args.palavras).name, "plataforma": args.plataforma or "uniao",
                                      "estilo": d["legenda"]["estilo"], "menor_tamanho_fracao": round(menor, 4)})
    print(f"{r['saida']}: {len(cues)} cue(s), {r['estados']} estado(s), região {r['regiao']}, menor texto {menor:.3f} do lado menor")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except da.DAErro as e:
        print(f"erro: {e}", file=sys.stderr)
        sys.exit(e.codigo or 1)
```

```bash
python3 "$CRIABR_SKILLS"/video-legendas/scripts/legendar.py bruto/fala.mp4 transcricao/palavras.json "legendas/corte 01 legendado.mp4" --inicio 1.0 --duracao 3.0 --formato 540x960
# legendas/corte 01 legendado.mp4: 3 cue(s), 8 estado(s), região (84, 532, 282, 82), menor texto 0.062 do lado menor
```

Medido (M1, 8 GB; base 1920×1080 a 29,97 fps; saída 540×960, 3 s, 8 palavras): **2,2 s de parede, um ffmpeg, duas entradas**; 90 quadros, áudio preservado; carimbo `ferramenta: video-legendas`, `formato: 540x960`, `midia` e `insumos: [fala.mp4 (sem carimbo)]`. Olhando os quadros: a palavra acesa bate com o tempo da transcrição (`CONTA` em 0,45 s; `DESAPARECE` em 2,6 s), a cue de três palavras longas quebrou em duas linhas sem encolher e o bloco ficou centrado no retângulo da zona `uniao` (x = 225 de 540), não no quadro.

O que a receita decide e você pode trocar:

- **Segmentação** (`segmentar`): até `legenda.max_palavras` por cue, quebra em pausa > 0,6 s ou pontuação final. É a parte que a skill de legendas refina (não quebrar depois de artigo, juntar numerais); o kit só garante que a cue cabe — `compor_legenda` quebra em `legenda.max_linhas` e encolhe por último, e `info["tamanho_fracao"]` diz quanto: compare com o mínimo legível da DA e **segmente de novo** em vez de aceitar texto pequeno.
- **Estilos**: quem decide é `legenda.estilo`, dentro de `texto.estados_da_legenda` — `karaoke` = o bloco inteiro com uma palavra em `cor_destaque` e as já ditas em `cor_falada` (o bloco não muda de lugar entre os estados); `palavra` = só a falada, todas no mesmo tamanho dentro da cue; `bloco` = um estado por cue. O mesmo script rodou nos três: dossiê (karaokê, 8 estados), neon-shorts com `--plataforma reels` (palavra, 8 estados, menor texto 0,081: a cue de "desaparece" encolheu inteira) e editorial-claro (bloco, 2 estados), todos `ok` no `conferir-carimbo`.
- **`legenda.animacao`** (`pop`/`fade`): a receita não anima. Para o "pop" (no motor, a palavra falada nasce 8 % maior e assenta), gere dois ou três estados curtos (`movimento.duracoes.micro`) no começo de cada palavra com o estilo dela ampliado por `texto.escalar_estilo(est, 1.08)` — `compor_cues` aceita quantos estados vierem e só compõe cada um uma vez.
- **Plataforma**: `--plataforma reels|tiktok|shorts` alarga a zona (840 e 788 px livres em 1080 no Shorts e no Reels, contra 660 na `uniao`). Corte que vai para as três fica na `uniao`.
- **GC por cima**: `video.compor_overlay("legendas/corte 01 legendado.mp4", "animacoes/gc.webm", "render/corte 01 final.mp4", t0=0.2, da_obj=d)` — o carimbo final lista a legenda (`n/a`) e o GC (`ok`) como insumos. No vertical, GC na posição padrão e legenda em y 0,60 ocupam a mesma faixa: escolha `graficos.gc.posicao` superior ou tempos que não coincidam.

## 17. Qual chamada serve a qual skill

| skill ou etapa | o que usar (tudo deste arquivo) |
|---|---|
| video-broll | `da.py grade --entrada broll/bruto/x.mp4 --saida broll/tratado/x.mp4` ou `video.filtro_tratamento` numa cadeia própria; moldura: `da.py render --cena moldura` → `video.encaixar_em_janela(base, insert, saida, layout, moldura=…)`; crédito do material: `texto.credito_fonte` ou `ctx.kit.credito`; proporção diferente: `video.filtro_encaixe` |
| video-pauta-midia | cenas de mídia (print, imagem da web, trecho citado) pelo motor: `da.py render --cena moldura` + `video.encaixar_em_janela` (a janela vem do `layout` do carimbo), ou cena própria com `ctx.kit.moldura` e `ctx.kit.credito`; captura de tela e logo de terceiros entram com `data-da-livre="captura"` (o auditor exige; a conferência final lista); trecho de vídeo entra pelo ffmpeg (`video.compor_overlay`), nunca tocando dentro da página; registro em `broll/licencas.json` pelo módulo da video-broll; carimbo de tudo o que for para `animacoes/` |
| video-animacao-explicativa | cenas próprias com `ctx` (§9, §10), peças por `ctx.kit` e trocas por `ctx.transicao` (§10.1); interface de produto desenhada com `div`/`svg` e tokens — `<input>`, `<button>`, `<progress>`, emoji, GIF e `<animate>` reprovam no auditor (§11); fila com `--validar` antes; juntar blocos renderizados: `video.juntar(clipes, saida)` com a transição da DA |
| video-legendas | §16: `texto.compor_legenda(…, recortar=True)` por estado + `video.compor_cues`; **antes de queimar**, `d.legenda_reservada(formato)` (ou `info["faixa_reservada"]`): `False` — o horizontal padrão — quer dizer que GC e crédito do kit ocupam a faixa da legenda nesse formato; avise e proponha `"horizontal"` em `legenda.reservar_em` em vez de queimar por cima; overlay solto com alfa (para o Premiere): `video.Codificador("legendas/faixa.mov", formato="vertical", da_obj=d)` |
| video-cortes-verticais | `video.filtro_recorte` (âncora da DA ou `foco` do rosto) ou `video.filtro_encaixe` (fundo desfocado); `video.compor_cues(base, cues, saida, inicio=, duracao=, tratamento_base=, tamanho=)`; áudio: `video.medir_para_loudnorm` + `video.filtro_loudnorm(d, "curto", medida=…, folga_pico=0.5)`; limites: `da.limite("shorts", "duracao_max_s")` |
| thumbnail — **sem skill: direto pelo kit** (§17.1) | PIL: `texto.Estilo.thumbnail(d)` / `(d, destaque=True)` + `texto.compor_bloco(palavras, estilos, largura_max=…, max_linhas=…)`, fora de `d.zona_proibida("thumbnail")`; motor: `ctx.texto` + `ctx.contorno` + `ctx.zona_proibida()`, formato `thumbnail`; peso do arquivo: `da.limite("youtube", "peso_max_seguro_mb")` → `2` (MB; `peso_max_mb` traz o teto por aparelho: `{'celular': 2, 'computador': 50, …}`); carimbo com `d.carimbar(…, "thumbnail", "thumbnail", …)` |
| conferência final — **sem skill: comando do kit** (§18) | `da conferencia` faz tudo e grava `qa/relatorio.json`; por dentro: `da.validar`, `da.lint(None, estrito=True)`, `da.conferir_carimbo(…, exigir_aprovada=True)` (`pecas[].estado`, `.insumos`, `.livres`), `video.sondar`, `video.conferir_loudness`, `da.plataforma(nome)`. Para olhar quadros: `video.extrair_quadro(…, "qa/_q.png")` + `video.folha_de_contato` (célula na proporção da peça) |
| video-publicacao | `da.plataforma("reels")` (ficha com `titulo_max`, `texto_max`, `hashtags_max`, `duracao_*`, `tamanho_max_mb`, `vencida`), `da.limite(plataforma, chave)`, `da.nome_plataforma(apelido)`; pastas `publicacao/<youtube|shorts|reels|tiktok>/`; **portão de publicação**: `qa/relatorio.json` gravado por `da conferencia` — `ok` = true, `da_sha256` = `d.sha256`, `verificado_em` mais novo que o arquivo, e o arquivo a publicar em `alvos` com o mesmo `sha256` (§18) |
| video-pesquisa-ia | nada visual; se gerar cartão de fonte, `texto.credito_fonte` (PIL) ou `ctx.kit.credito` (cena) — o prefixo "Fonte: " é token (`graficos.citacao_fonte.prefixo`), não texto fixo |

**Quem desenha onde, para nada colidir (vale para todas):** a legenda mora onde a DA manda (`legenda.posicao`, por `texto.compor_legenda` / `ctx.kit.legenda`); **todo o resto** que divide o quadro com ela — GC, selo, crédito, assinatura, gráfico, título, rótulo de moldura — mora na área livre: `d.area_livre(formato, plataforma)` em Python, `ctx.area_livre(plataforma, { legenda: p.reservar_legenda })` em cena (as cenas embutidas já fazem isso). No vertical e no quadrado a reserva vem ligada (`legenda.reservar_em`); no horizontal ela vem **desligada** — o GC fica na base e ocupa a faixa da legenda, como a prancha mostra e `validar` anota —, e só liga quando a DA diz que o horizontal leva legenda queimada (`"horizontal"` em `legenda.reservar_em`; numa peça só, `"reservar_legenda": true` nos params). Quem queima a legenda pergunta antes: `d.legenda_reservada(formato)`. A conferência final não refaz essa geometria: o kit garante a zona por construção (a legenda nunca é desenhada fora dela; as cenas embutidas trabalham na área livre) e `da conferencia` acusa o que o próprio kit mediu fora — `layout.rotulo_na_zona: false` ou `dentro_da_zona: false` no carimbo viram item `zona_segura`. Cena própria que desenha fora da área livre não é pega por ela: confira no seu script o que o carimbo traz — `parametros.layout.caixa` (GC) e `.reservou_legenda`, `.bloco`, `.credito`, `.rotulo`/`.sub` (moldura) — contra `d.faixa_legenda(formato)` e `d.margens(formato, plataforma)`.

### 17.1 Thumbnail — direto pelo kit, os dois caminhos executados

Não existe skill de thumbnail: a thumbnail é uma peça como as outras, feita por quem estiver conduzindo o projeto com os tokens `thumbnail.*` (`tokens.md`), um dos dois caminhos abaixo e as regras de `plataformas.md` §5 (1280×720, até 2 MB, nada no canto do selo de duração, até 3 variações para o teste A/B). O que fica por sua conta, porque o kit não faz: escolher e recortar a foto (`thumbnail.tratamento_foto` diz saturação e contraste; o recorte da pessoa é manual ou de outra ferramenta) e decidir as 3–4 palavras (`thumbnail.max_palavras`). Salve em `thumbs/` (`thumb a.png`, `thumb b.png`…) e carimbe: a conferência final confere o carimbo de `thumbs/` como o de qualquer peça.

Em PIL (sem browser; é o caminho para compor sobre foto recortada):

```python
from PIL import Image
TL, TA = d.dimensoes("thumbnail")                       # (1280, 720)
zp = d.zona_proibida("thumbnail")                       # {'x0': 960, 'y0': 562, 'x1': 1280, 'y1': 720, 'largura': 320, 'altura': 158, 'canto': 'inferior_direita'}
th, thd = texto.Estilo.thumbnail(d), texto.Estilo.thumbnail(d, destaque=True)
titulo, info = texto.compor_bloco(["A", "CONTA", "NÃO", "FECHA"], [th, th, thd, thd], largura_max=TL * 0.6, max_linhas=3, alinhamento="esquerda")
m = d.margens("horizontal", largura=TL, altura=TA)
thumb = Image.new("RGBA", (TL, TA), d.rgba("fundo"))
thumb.alpha_composite(titulo, (m["x0"], m["y0"]))        # confira info["caixa"] deslocada contra zp antes de salvar
thumb.convert("RGB").save("thumbs/thumb a.png")
d.carimbar("thumbs/thumb a.png", "thumbnail", "thumbnail", {"titulo": "A CONTA NÃO FECHA", "zona_proibida": zp})
```

No motor (passa pelo auditor; `da.py render --cena thumbs/thumb.js --saida "thumbs/thumb b.png" --formato thumbnail --quadro 0 --params '{"palavras": ["A", "conta", "não", "fecha"], "destaque": 2}'` → 1280×720 em 0,35 s, `layout.titulo` = x 64–845, y 36–347, fora da zona proibida x ≥ 960, y ≥ 562):

```js
// thumb.js — thumbnail no motor: título do bloco `thumbnail` da DA com palavra em destaque, fora da zona proibida
export const meta = {
  nome: 'thumb', dur_padrao: 1, alfa_padrao: false, formatos: ['thumbnail'],
  params: {
    palavras: { tipo: 'lista', min: 1, obrigatorio: true, itens: { tipo: 'texto' } },
    destaque: { tipo: 'inteiro', padrao: -1, descricao: 'índice da palavra em thumbnail.cor_destaque' },
  },
};

export function build(palco, p, ctx) {
  const th = ctx.DA.thumbnail;
  const area = ctx.area_segura();
  const zp = ctx.zona_proibida();                               // {x, y, w, h, x1, y1, canto} em px, ou null
  palco.style.background = th.fundo_css || ctx.cor('fundo');     // derivado: hex ou linear-gradient(…) do gradiente nomeado
  const html = p.palavras.map((w, i) => `<span style="color: ${ctx.cor(i === p.destaque ? th.cor_destaque : th.cor)}">${ctx.esc(w)}</span>`).join(' ');
  const larguraMax = (zp ? zp.x : area.x1) - area.x;            // o título acaba antes da coluna da zona proibida
  const t = ctx.texto(th.papel, '', { tam: ctx.px(th.tamanho), cor: th.cor, html, wrap: true, maxW: larguraMax });
  if (th.contorno) ctx.contorno(t._inner, th.contorno.cor, th.contorno.espessura * ctx.px(th.tamanho));
  palco.appendChild(t);
  const m = ctx.ajustar_texto(t, larguraMax, { alturaMax: area.h, maxLinhas: 3 });
  ctx.place(t, { x: area.x, y: area.y });
  const caixa = ctx.rectDe(t);
  const invade = !!zp && caixa.x1 > zp.x && caixa.y1 > zp.y;
  if (invade) throw new Error('thumb: o título entrou na zona proibida; reduza o texto');
  return { titulo: caixa, linhas: m.linhas, zona_proibida: zp };
}

export function seek() {}
```

## 18. Conferência final (C5) — `da conferencia` e o contrato de `qa/relatorio.json`

A quinta camada da submissão não é uma skill: é um comando do kit, para que o portão de publicação exista em qualquer projeto que tenha DA. Ele **compõe** o que este arquivo já descreve — `da.validar`, `da.lint`, `da.conferir_carimbo`, `video.sondar`, `video.conferir_loudness`, `da.plataforma` — e não tem regra de validação própria: se uma peça reprova aqui, o subcomando correspondente reprova do mesmo jeito. Não renderiza nada e só escreve em `qa/` (conferido em teste: nenhum outro arquivo do projeto muda — nem `da/build/` e o `DA.md`: a DA é lida em memória, mesmo com o build velho). As medições de loudness entram na trava global uma por vez; o resto é leitura.

```bash
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia                          # projeto inteiro: render/final.mp4 + cortes/*.mp4 → qa/relatorio.json e qa/relatorio.md
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia --corte K01              # só um corte (nome em cortes/, com ou sem .mp4, ou caminho)
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia render/final.mp4         # só o vídeo longo
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia --corte render/final.mp4 --plataforma reels   # peça vertical nativa que mora em render/, só para o Reels
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia --previa                 # antes de a DA estar aprovada: qa/previa.json, nunca o portão
"$CRIABR_SKILLS"/video-direcao-de-arte/kit/bin/da conferencia --json --saida "qa/rodada 2"   # imprime o JSON; grava em outra pasta
```

| opção | significado |
|---|---|
| `ALVO…` (posicionais) | entregáveis a conferir **no lugar** do padrão. Arquivo dentro de `cortes/` é peça curta; fora dela, vídeo longo. Caminho a partir do diretório atual ou da raiz do projeto |
| `--corte ARQ\|NOME` (repetível) | confere este corte como **peça curta**: caminho, ou nome em `cortes/` com ou sem `.mp4`. É também como se confere uma peça vertical nativa que mora em `render/` |
| `--plataforma NOME` (repetível) | destino das peças curtas (`shorts`, `reels`, `tiktok` e apelidos). Sem ela vale a plataforma que o carimbo do corte declara (`parametros.plataforma` ou `.plataformas`; `uniao` não restringe) e, na falta, todas as de orientação vertical em `plataformas.json`. O vídeo longo vai sempre contra as de orientação horizontal (hoje, `youtube`) |
| `--previa` | DA ainda **não aprovada** vira aviso em vez de erro (e `conferir-carimbo` roda sem `--exigir-aprovada`); o relatório vai para `qa/previa.json` + `qa/previa.md` e o `qa/relatorio.json` não é tocado (`--previa --saida qa/relatorio.json` é erro de uso, código 64). DA **alterada depois da aprovação** continua erro |
| `--saida PASTA\|ARQ.json` | onde gravar: pasta (recebe `relatorio.json` e `relatorio.md`; `previa.*` na prévia) ou o caminho do `.json` (o `.md` vai ao lado). Padrão: `<projeto>/qa/` |
| `--json` | imprime o relatório (o mesmo conteúdo do arquivo) em vez do resumo; a fila da trava continua indo para o stderr |
| `--da`, `--de` | como em todo subcomando |

Códigos de saída: **0** `ok` (pode haver avisos) · **1** há item com severidade `erro` (o relatório é gravado do mesmo jeito, inclusive com a DA inválida ou ilegível: um relatório antigo `ok` não fica valendo) · **2** nenhuma DA · **64** uso incorreto — alvo que não existe (`--corte K99` responde com os cortes do projeto), alvo fora do projeto, pasta no lugar de arquivo, plataforma desconhecida, prévia com `--saida` no arquivo do portão; nesses casos **nenhum relatório é gravado**.

**O que é conferido, e de onde vem cada item:**

| | conferência | função do kit | itens (`categoria`) |
|---|---|---|---|
| a | DA sem erros de validação, **aprovada** e não alterada depois da aprovação | `da.validar`, `d.aprovada`, `d.meta["alterada_apos_aprovacao"]` | `da`: `da.erro.N` (erro), `da.invalida` (erro: o resto não foi conferido — vale também para `da.json` que nem JSON é ou cujo `herda` não existe), `da.nao_aprovada` (erro; aviso com `--previa`; correção: "Rode `da aprovar`…"), `da.alterada_apos_aprovacao` (erro: `da revisar` + `da aprovar`), `da.aviso.N` (aviso), `da.nota.N` (info) |
| b | `lint --estrito` nas pastas de peças (`animacoes legendas cortes thumbs render broll/tratado`) | `da.lint(None, estrito=True)` | `lint`: `lint.<regra>.N` (erro; a mensagem traz linha:coluna e o trecho, a correção traz o token mais próximo), `lint.nao_conferido.N` (erro), `lint.nota.N`, `lint.resumo` ou `lint.nada_lido` (info). Aviso do lint é erro aqui: é o que `--estrito` quer dizer |
| c | carimbos, exigindo DA aprovada: as pastas de peças inteiras (com `broll/tratado`) e os insumos carimbados das composições que estiverem fora delas | `da.conferir_carimbo(…, exigir_aprovada=True)` | `carimbo`: `carimbo.sem_carimbo.N`, `.carimbo_invalido.N`, `.sha_diferente.N` (DA DIFERENTE), `.auditoria_pulada.N`, `.arquivo_alterado.N`, `.insumo_de_outra_da.N` (erro, um por peça); `carimbo.da_nao_aprovada` e `carimbo.da_alterada` (erro, **um item só** com a lista das peças — o motivo é da DA); `carimbo.livres.N` (info: elementos `data-da-livre` de cada peça), `carimbo.insumo_sem_carimbo.N`, `carimbo.resumo` (info). `zona_segura`: `zona_segura.fora_da_zona.N` (aviso) quando o carimbo de uma peça traz `layout.rotulo_na_zona` ou `dentro_da_zona` = `false` |
| d | loudness de cada entregável contra a DA: `som.loudness.longo` para o vídeo longo, `som.loudness.curto` para as peças curtas | `video.conferir_loudness(d, arq, tipo)` (ebur128, tolerância de ±1 LU da própria função) | `loudness`: `loudness.fora_do_alvo.N`, `loudness.pico.N`, `loudness.sem_medida.N` (sem trilha de áudio ou silêncio) — erro; `loudness.medido.N` (info, com os valores) |
| e | técnica de cada entregável contra os limites de **cada** plataforma de destino e os formatos da DA | `video.sondar`, `da.plataforma(nome)`, `d.dimensoes`, `video.fps_do_formato`, `video.args_encode` | `tecnico`: `tecnico.duracao_max.N`, `.duracao_min.N`, `.tamanho.N`, `.orientacao.N` (peça horizontal para plataforma vertical ou o contrário; peça quadrada é só aviso), `.ilegivel.N`, `.sem_video.N` — erro; `.duracao_recomendada.N`, `.resolucao.N` (diferente do formato da DA ou abaixo da recomendada), `.fps.N`, `.formato_de_entrega.N` (não é H.264 yuv420p), `tecnico.sem_entregavel`, `tecnico.plataformas_vencidas` — aviso; `tecnico.medidas.N` (info: o que foi medido e contra quais plataformas). Nenhum número mora no código: duração mínima, máxima e recomendada, tamanho e resolução saem de `plataformas.json` |
| f | ficha de fatos, **se** o projeto tem `pesquisa/fatos.json`: `fatos.py validar --estrito`, `conferir-roteiro roteiro/roteiro.md --estrito` (se o roteiro existe) e `conferir-storyboard` (se `roteiro/storyboard.json` existe) | o script da video-pesquisa-ia, achado **por posição** (`<skills>/video-pesquisa-ia/scripts/fatos.py`) e chamado com `--json` | `fatos`: `fatos.ficha.N`, `fatos.roteiro.N` (erro — inclusive os avisos, porque a chamada é `--estrito`), `fatos.storyboard.N` (pendência = erro, aviso = aviso), `fatos.<etapa>_nao_conferido.N` (erro: o script não devolveu resultado), `fatos.<etapa>_ok.N`, `fatos.sem_ficha`, `fatos.sem_roteiro`, **`fatos.skill_ausente` (info, nunca erro)** |
| f | créditos de b-roll, **se** o projeto tem `broll/licencas.json`: todo item com `exige_atribuicao` (os marcados em `usado_em`; sem nenhum marcado, todos) precisa ter o texto de `atribuicao` em `broll/creditos.md` | leitura dos dois arquivos (não depende da video-broll) | `licencas`: `licencas.sem_credito.N`, `licencas.sem_atribuicao.N`, `licencas.registro_ilegivel` (erro), `licencas.resumo`, `licencas.sem_registro` (info) |

A categoria `texto` do contrato fica reservada às conferências de texto de publicação (título, descrição, legenda do post), que são da video-publicacao: o kit não emite item nela.

**Entregáveis.** Sem alvo: `render/final.mp4` (vídeo longo), se existir, e `cortes/*.mp4` (peças curtas; só o primeiro nível, sem nomes começados por `_`). Sem nenhum dos dois (e sem outro erro) o relatório sai `ok` com o aviso `tecnico.sem_entregavel` e `alvos: []` — não libera a publicação de arquivo algum. Com `ALVO…` ou `--corte` a conferência é **restrita**: carimbo, loudness e técnica valem só para os arquivos pedidos (e para os insumos carimbados deles — conferir `--corte K01` confere também o `render/final.mp4` de onde ele saiu); DA, lint, fatos e licenças continuam sendo do projeto inteiro. Medido: uma peça solta sem carimbo em `animacoes/` reprova a conferência do projeto e não reprova `da conferencia render/final.mp4`; uma cena com cor literal reprova as duas.

**Contrato do relatório** (`qa/relatorio.json`; os nomes de campo não mudam — relatório real de `da conferencia --corte K02`, com os itens abreviados):

```json
{"versao": 1, "ok": false, "verificado_em": "2026-10-12T08:53:48-03:00",
 "da_sha256": "c913a9b9db63de253382979ca7090c711c43e872a1c843e75334519e50865116",
 "alvos": [{"arquivo": "cortes/K02.mp4", "sha256": "6b8e87e464703c42117f687aaeb27419d78464a3a054361b07d38a1026750065", "bytes": 136684}],
 "resumo": {"erros": 2, "avisos": 1},
 "itens": [
  {"id": "carimbo.resumo", "categoria": "carimbo", "alvo": "alvos pedidos e insumos", "severidade": "info",
   "mensagem": "conferir-carimbo --exigir-aprovada: 2 peça(s), 2 em dia (1 insumo(s) de composição conferido(s) fora da varredura)", "como_corrigir": ""},
  {"id": "tecnico.duracao_min.1", "categoria": "tecnico", "alvo": "cortes/K02.mp4", "severidade": "erro",
   "mensagem": "duração de 2 s fica abaixo do mínimo de reels (3 s)", "como_corrigir": "Alongue a peça ou tire reels do destino deste corte (--plataforma)."},
  {"id": "loudness.fora_do_alvo.1", "categoria": "loudness", "alvo": "cortes/K02.mp4", "severidade": "erro",
   "mensagem": "loudness fora do alvo — -27,8 LUFS, pico -26,2 dBTP; alvo som.loudness.curto = -14 LUFS / -1 dBTP: desvio de -13,8 LU (tolerância ±1)",
   "como_corrigir": "Normalize em duas passagens: video.medir_para_loudnorm(arq, d, \"curto\", folga_pico=0.5) + video.filtro_loudnorm(d, \"curto\", medida=…, folga_pico=0.5), como a video-cortes-verticais faz."}]}
```

| campo | regra |
|---|---|
| `versao` | `1` |
| `ok` | `true` quando nenhum item tem severidade `erro` (avisos não derrubam) |
| `verificado_em` | `da.agora_iso()` — ISO 8601 **com fuso**, tirada no **início** da conferência: arquivo regravado enquanto ela roda fica mais novo que o relatório, e quem publica percebe |
| `da_sha256` | identidade da DA conferida (`d.sha256`; com a DA inválida, a de `da.validar`; com o `da.json` ilegível, `""` — nunca igual à de uma DA de verdade) |
| `alvos` | os entregáveis conferidos, na ordem: `arquivo` relativo à raiz do projeto (com `/`), `sha256` do arquivo inteiro, `bytes`. `broll/tratado`, `animacoes/`, `thumbs/` são peças (entram em `carimbo`), não alvos |
| `resumo` | `{"erros": n, "avisos": n}` — contagem dos itens por severidade |
| `itens[].id` | `<categoria>.<regra>` ou `<categoria>.<regra>.<n>`; único no relatório e estável entre execuções enquanto o projeto não muda |
| `itens[].categoria` | `da`, `carimbo`, `lint`, `tecnico`, `loudness`, `zona_segura`, `fatos`, `licencas` (`texto`: reservada) |
| `itens[].alvo` | arquivo relativo à raiz (`cortes/K02.mp4`, `roteiro/roteiro.md:14`, `broll/licencas.json#B004`), `da/da.json`, ou o conjunto conferido |
| `itens[].severidade` | `erro` (reprova), `aviso` (não reprova; leia), `info` (o que foi medido ou por que algo não se aplica) |
| `itens[].mensagem`, `.como_corrigir` | uma linha cada; todo erro e todo aviso dizem como corrigir (`""` nos `info`) |

`qa/relatorio.md` é o mesmo relatório para gente: veredito, DA, tabela dos entregáveis (tipo, plataformas, tamanho, sha), contagem por categoria e as listas de erros, avisos e informações com a correção de cada um. O resumo impresso (real, `da conferencia` no mesmo projeto):

```
CONFERÊNCIA FINAL — Projeto Um · DA revisão 1, aprovada, sha256 c913a9b9db63…
Modo: projeto inteiro
Entregáveis (3):
  render/final.mp4  (vídeo longo → youtube)
  cortes/K01.mp4  (peça curta → shorts)
  cortes/K02.mp4  (peça curta → shorts, reels, tiktok)
  da           ok  (1 informação(ões))
  carimbo      ok  (1 informação(ões))
  lint         ok  (1 informação(ões))
  tecnico      1 erro(s), 3 aviso(s)  (3 informação(ões))
  loudness     1 erro(s)  (2 informação(ões))
  fatos        ok  (1 informação(ões))
  licencas     ok  (1 informação(ões))
ERROS (2)
  ✗ [tecnico.duracao_min.1] cortes/K02.mp4 — duração de 2 s fica abaixo do mínimo de reels (3 s)
      → Alongue a peça ou tire reels do destino deste corte (--plataforma).
  ✗ [loudness.fora_do_alvo.1] cortes/K02.mp4 — loudness fora do alvo — -27,8 LUFS, pico -26,2 dBTP; alvo som.loudness.curto = -14 LUFS / -1 dBTP: desvio de -13,8 LU (tolerância ±1)
      → Normalize em duas passagens: video.medir_para_loudnorm(arq, d, "curto", folga_pico=0.5) + video.filtro_loudnorm(d, "curto", medida=…, folga_pico=0.5), como a video-cortes-verticais faz.
AVISOS (3)
  ! [tecnico.resolucao.1] render/final.mp4 — resolução 320×180 diferente do formato horizontal da DA (1920×1080) e abaixo da recomendada por youtube (1920×1080)
      → Entregável sai na resolução do formato da DA; prévia reduzida (--escala) não é entregável: renderize a versão final.
  …
REPROVADO: 2 erro(s), 3 aviso(s).
Relatório: /…/Projeto Um/qa/relatorio.json · relatorio.md
```

Em Python (a mesma coisa que a CLI; é o que a suíte `testes/test_conferencia.py` exercita):

```python
import da_ext_conferencia as conferencia
rel = conferencia.conferir()                                   # projeto do diretório atual; grava qa/relatorio.json e .md
rel = conferencia.conferir("/caminho/Projeto", cortes=["K01"], plataformas=["reels"], previa=False, saida=None, gravar=True)
rel["ok"], rel["resumo"], rel["alvos"], rel["itens"]           # o relatório é um dict no contrato (json.dumps(rel) é o arquivo)
rel.json, rel.md, rel.raiz, rel.previa, rel.restrito           # arquivos gravados (None com gravar=False) e contexto, fora do JSON
rel.entregaveis                                                # [{'arquivo': Path, 'rel': 'cortes/K01.mp4', 'tipo': 'curto', 'plataformas': ['reels']}]
conferencia.listar_entregaveis("/caminho/Projeto")             # o que SERIA conferido, sem conferir nada
conferencia.caminhos_do_relatorio("/caminho/Projeto", saida=None, previa=False)   # (…/qa/relatorio.json, …/qa/relatorio.md)
print(conferencia.texto_resumo(rel))                           # o resumo da CLI; conferencia.texto_md(rel) = o conteúdo do .md
```

Sem DA levanta `da.SemDA`; alvo inexistente, fora do projeto ou plataforma desconhecida levantam `da.DAErro` com `codigo == 64` antes de qualquer conferência.

**Para quem publica (video-publicacao) — o portão.** Um relatório libera um arquivo quando: (1) `ok` é `true` e nenhum item tem severidade `erro`; (2) `da_sha256` é o `d.sha256` atual; (3) `verificado_em` (com fuso) não é mais velho que o arquivo a publicar; (4) **o arquivo a publicar está em `alvos`, com o mesmo `sha256`** — `da conferencia --corte K01` grava um relatório `ok` que não diz nada sobre `render/final.mp4`, e um projeto sem entregável também sai `ok`. `qa/previa.json` nunca é portão. Thumbnail e `.srt` alterados depois de `verificado_em` pedem nova conferência (a thumbnail é peça carimbada: entra em `carimbo`).

**O que a conferência não vê** (limites reais, não promessas): o conteúdo do quadro — ela não abre imagem nem vídeo, só mede arquivo, áudio e carimbo; por isso zona segura é garantida pela construção do kit e pelos avisos do `validar`, não por medição da peça pronta, e uma cena própria que desenha fora da área livre passa. O loudness é o integrado do arquivo inteiro (um trecho estourado no meio de um vídeo longo no alvo passa). A técnica confere os campos normalizados de `da.plataforma` — duração, tamanho, orientação, resolução —; bitrate, GOP e espaço de cor de `plataformas.md` §3 não são conferidos (o `video.args_encode` os entrega certos). Os limites são os de `plataformas.json`: passou do prazo de revalidação, sai o aviso `tecnico.plataformas_vencidas`, mas os números continuam os antigos até alguém revalidar. Fatos: só o que o `fatos.py` reprova **offline** (ficha, roteiro, storyboard); abrir os links e revalidar os voláteis (`checar-links --trechos`, `vencidos`) continua sendo o passo de publicação da video-pesquisa-ia. Licenças: só a presença do crédito; risco, uso comercial e `usado_em` × storyboard são da video-broll e da video-publicacao.
