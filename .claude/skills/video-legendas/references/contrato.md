# Contrato: arquivos, campos e chamadas (para quem integra outra skill)

Tudo o que outra skill pode ler ou chamar. Campos podem ser **acrescentados** em versões futuras; os listados aqui não mudam de nome.

## 1. Onde cada arquivo é gravado

| arquivo | quando | observação |
|---|---|---|
| `legendas/<nome>.cues.json` | sempre (`cues.py gerar`, `legendar.py` em qualquer modo) | `<nome>` = `--nome`; senão o nome da saída sem extensão; senão o do vídeo — e, **com trecho** (`--inicio`/`--fim`), o do vídeo mais o intervalo: `final 62.4-91s` |
| `legendas/<nome>.srt`, `legendas/<nome>.vtt` | sempre, irmãos das cues | frases inteiras; relógio = o das cues |
| `<saida>` + `<saida>.da.json` | `legendar.py --saida` | vídeo legendado (H.264) ou faixa com alfa; carimbado |
| `<saida sem extensão>.srt` | quando a saída **não** fica em `legendas/` | cópia do `.srt` (ex.: `cortes/K01.srt`); `--sem-srt-ao-lado` desliga |
| `legendas/_previa_<nome>.png` | `--previa` | intermediário (prefixo `_`): sem carimbo, fora do lint e da conferência final (`da conferencia`) |
| `legendas/_png/<nome>/` | durante o render | PNG de cada estado; apagado no fim (`--manter-png` guarda) |
| `legendas/glossario.json` | escrito pelo usuário/Claude | lido se existir |

Como a `video-publicacao` acha o `.srt` de um vídeo: (1) `cortes/<corte>.srt`; (2) `.srt` com o mesmo nome do vídeo, ao lado dele ou em `legendas/`; (3) um `legendas/*.cues.json` cujo `origem` seja exatamente o vídeo. Por isso `cues.py gerar --video render/final.mp4 --nome final` → `legendas/final.srt`.

**O nome do vídeo inteiro é reservado.** A busca (2) é pelo nome, antes de olhar `origem`: um trecho gravado como `legendas/final.srt` seria enviado como legenda do vídeo longo. Por isso, com trecho:

- sem `--nome` nem `--saida`, o nome leva o intervalo (`legendas/final 20-30s.cues.json`, `.srt`, `.vtt`, `_previa_final 20-30s.png`);
- `--nome` (ou o nome da `--saida`) igual ao do vídeo ou ao do arquivo de palavras é **erro de uso (64)**, com a sugestão de nome;
- um `cues.json` existente que é a legenda de um vídeo inteiro (qualquer vídeo) não é trocado pelo de um trecho: erro 1; `--refazer-cues` / `--forcar` substituem de propósito.

## 2. `legendas/<nome>.cues.json`

```json
{"versao": 1,
 "origem": "cortes/K01.mp4",
 "formato": "vertical", "plataforma": "uniao", "estilo": "karaoke",
 "largura": 1080, "altura": 1920, "fps": "30000/1001", "duracao": 28.6,
 "janela": {"inicio": 62.4, "fim": 91.0},
 "fonte": {"video": "render/final.mp4", "inicio": 62.4, "fim": 91.0},
 "palavras_origem": "transcricao/final.palavras.json", "pontuacao": "limpa",
 "da_sha256": "…", "gerado_em": "2026-10-07T01:27:04-03:00", "editado": false,
 "regras": {"max_palavras": 5, "max_linhas": 2, "segura": 0.3, "dur_min": 0.5, "respiro": 0.0667, "respiro_oculta": 0.0667, "pausa_dura": 0.7, "limiar_confianca": 0.6},
 "glossario": {"trocas": 1, "numeros": 0, "censuradas": 0, "destaques": 2, "sem_ocorrencia": [], "arquivo": "legendas/glossario.json"},
 "notas": {"lidas": 412, "fora_da_janela": 330, "tempos_reparados": 4, "tokens_fundidos": 0, "fusoes_de_cue_curta": 1},
 "cues": [{"id": 1, "t0": 0.12, "t1": 1.48,
           "linhas": [["se", "teve"], ["uma", "coisa"]],
           "palavras": [{"a": 0.12, "b": 0.29, "w": "se", "linha": 0, "destaque": false, "p": 0.895, "txt": "se"}, …]}],
 "frases": [{"t0": 0.12, "t1": 3.61, "texto": "se teve uma coisa\nque ele falou ali que é real,"}],
 "avisos": [{"tipo": "confianca", "cue": 2, "t": 1.89, "palavra": "galera", "p": 0.437, "mensagem": "…"}]}
```

Campos do contrato da casa (as outras skills contam com eles): `versao`, `origem`, `formato`, `plataforma`, `estilo`, `cues[].t0`, `.t1`, `.linhas`, `.palavras[].a`, `.b`, `.w`, `.linha`, `.destaque`. O resto é desta skill.

- **Tempos** em segundos, no relógio de `origem`. Com trecho (`janela`), 0 é o início do trecho.
- **`origem`** = o vídeo **cujo relógio as cues seguem**, relativo à raiz do projeto:
  - sem trecho: o vídeo de entrada (`render/final.mp4`);
  - com trecho e vídeo legendado: o vídeo legendado (`cortes/K01.mp4`) — também quando a queima é feita com `--cues` (prévia → `cues.py editar` → queimar): o arquivo de cues é regravado com a `origem` nova;
  - com trecho e sem vídeo legendado (`cues.py gerar`, `--previa`, `--so-overlay`): `render/final.mp4#t=62.400,91.000` — o endereço do pedaço. Assim ninguém toma a legenda de um trecho pela do vídeo inteiro.
  - `fonte` guarda sempre o vídeo de entrada e o trecho.
- **`formato`**: nome de um formato de vídeo da DA (`vertical`, `horizontal`, `quadrado`…) quando as dimensões coincidem; senão `LxA` (`540x960`).
- **`plataforma`**: a zona usada, com a chave da DA — `uniao`, `instagram` (= reels), `tiktok`, `shorts`; `padrao` no horizontal.
- **`palavras[].w`** é o texto queimado (pontuação conforme `pontuacao`); **`txt`** é o texto da legenda oculta (com a pontuação da transcrição). `p` = confiança do whisper (1.0 depois de corrigida à mão). `orig` aparece quando o glossário trocou a palavra; **palavra censurada leva `"censurada": true` e nunca `orig`** — nem ela, nem as vizinhas que vieram da mesma troca (`"Kinga Tagiri" → "Kim Kataguiri"` + censura de `Kataguiri`: `Kim` fica sem `orig`). Texto vindo de `trocas` leva `p` 1.0 (foi escrito por gente, como no `editar`); número convertido guarda a menor confiança das palavras que o formaram. `fala_fim` aparece nas palavras que o glossário ou uma edição trocou: é o fim da fala do trecho original, em segundos — a cue fica na tela até a fala acabar mesmo quando o texto novo é curto (`150.000`, `***`).
- **`linhas`** = as palavras de cada linha, na ordem; `palavras[].linha` aponta para elas. No estilo `palavra` há sempre uma linha.
- **`editado: true`** + `edicoes[]` depois de `cues.py editar`: `legendar.py` sem `--cues` se recusa a sobrescrever.
- **`frases`** é o conteúdo do `.srt`/`.vtt`; **`avisos`** tem `tipo` em `confianca`, `duracao`, `leitura`, `largura`, `linhas`, `relampago`, `leitura_oculta`.
- **Tetos da DA**: nenhuma cue gerada tem mais palavras que `regras.max_palavras` nem mais linhas que `regras.max_linhas`. Arquivo editado à mão com linhas a mais é aceito, com aviso `linhas`, e na tela a quebra é refeita pelo kit dentro do teto.

## 3. `legendas/glossario.json`

```json
{"trocas": {"como saiu": "como deve ficar"}, "censura": ["termo"], "numeros_em_algarismo": true, "destaques": ["termo"], "mascara": "***"}
```

Todas as chaves são opcionais; chave desconhecida é erro (anotações livres começam por `_`). Ordem de aplicação: trocas → números → censura → destaques. `trocas` compara sem diferenciar maiúsculas e **com** acento; `censura` e `destaques` comparam sem maiúsculas e sem acento. Termos de várias palavras valem (não atravessam fim de frase). `mascara` não pode ter espaço nem começar/terminar em pontuação.

## 4. Linha de comando

```
legendar.py --video V --palavras P --saida S [--formato F] [--plataforma P] [--inicio s --fim s] [--so-overlay] [--codec …]
            [--previa [N]] [--cues ARQ] [--refazer-cues] [--nome N] [--glossario ARQ] [--pontuacao …] [--limiar-confianca P]
            [--enquadramento recorte|encaixe] [--foco X,Y] [--tratamento] [--escala F] [--crf N] [--amostras N] [--sem-contraste]
            [--sem-srt-ao-lado] [--manter-png] [--projeto PASTA] [--estrito] [--json]
cues.py [--projeto PASTA] gerar --palavras P [--video V] [--formato F] [--plataforma P] [--inicio s --fim s] [--nome N] [--glossario ARQ]
                                 [--pontuacao …] [--limiar-confianca P] [--escala F] [--forcar]
cues.py mostrar ARQ [--avisos]
cues.py editar ARQ --cue N [--texto TXT] [--palavra K --para TXT] [--t0 S] [--t1 S] [--juntar] [--dividir K] [--linhas A,B] [--destacar K] [--sem-destaque K] [--remover]
cues.py exportar ARQ
```

`--escala` fora de 0.05–1 (inclusive 0) e `--previa 0` são erro de uso. Códigos de saída: **0** ok (mesmo com avisos) · **1** erro, ou `--estrito` com contraste ruim/cue abaixo do mínimo legível · **2** projeto sem direção de arte · **64** uso incorreto · **75**/**124** vindos da trava do kit (fila, ffmpeg sem progresso) · **127** kit de direção de arte não encontrado ao lado. Erros saem em uma ou duas linhas no stderr (`erro: …` + `→ o que fazer`), sem traceback.

A DA é procurada em: `--projeto` → pasta atual → pasta da saída → pasta do vídeo (subindo até achar `da/da.json`).

## 5. Função

```python
import legendar          # com <skills>/video-legendas/scripts no sys.path
r = legendar.legendar(video, palavras=None, saida=None, formato=None, plataforma=None, inicio=None, fim=None, **opcoes)
```

`opcoes`: `so_overlay`, `codec` (`"vp9alfa"`, `"prores4444"`, `"ambos"`), `previa` (`True` ou nº de quadros), `previa_saida`, `cues` (arquivo corrigido), `refazer_cues`, `nome`, `glossario`, `projeto`, `escala`, `enquadramento` (`"recorte"`, `"encaixe"`), `foco` (`(x, y)` em frações), `tratamento`, `pontuacao`, `limiar_confianca`, `amostras`, `sem_contraste`, `crf`, `srt_ao_lado`, `manter_png`. Opção desconhecida é `comum.Erro` (código 64).

Retorno:

| chave | conteúdo |
|---|---|
| `saida`, `saidas` | `Path` do vídeo (ou da primeira faixa) e a lista de todos; `None`/`[]` em `previa` |
| `carimbo` | `Path` do `<saida>.da.json` |
| `cues_json`, `srt`, `vtt` | `Path`s em `legendas/` |
| `srt_ao_lado` | `Path` da cópia junto da saída, ou `None` |
| `previa` | `Path` da folha de contato, ou `None` |
| `nome`, `formato`, `largura`, `altura`, `plataforma`, `estilo`, `animacao`, `duracao` | o que foi usado |
| `cues`, `palavras`, `estados` | contagens |
| `glossario` | `{trocas, numeros, censuradas, destaques, sem_ocorrencia: […], arquivo}` — o que o glossário fez neste trecho |
| `avisos` | lista de textos prontos para mostrar ao usuário (linhas começadas por `  →` são a sugestão do aviso anterior) |
| `conferencia["zona"]` | `{ok, estados, cues_fora, menor_tamanho_fracao, minimo_legivel, encolhidas: [{cue, tamanho_fracao, texto}], abaixo_do_minimo, pop_reduzido, faixa_reservada, fora_da_faixa, linhas_refeitas}` — `faixa_reservada: false` = a DA não reserva a faixa da legenda neste formato (o horizontal, por padrão): GC e crédito do kit ocupam o mesmo lugar, e sai aviso; `fora_da_faixa` = cues cujo bloco passa da faixa que a DA reserva; `linhas_refeitas` = cues que vieram com mais linhas que `legenda.max_linhas` |
| `conferencia["contraste"]` | `{ok, amostras, pior, ruins, atencao, limites, trechos: [{t0, t1, pior, fundo_video}], carregado: [t…], sugestoes: […], itens: [{t, cue, fundo_video, detalhe, fundo_efetivo: [p10, p50, p90], contraste: {cor, cor_destaque, cor_falada}, pior, nivel}]}` (ausente com `sem_contraste`) |
| `tempo_s` | parede, com a fila da trava |

Exceções: `comum.Erro` (`.mensagem`, `.dica`, `.codigo`), `da.SemDA` (sem direção de arte), `da.DAErro` (kit: ffmpeg falhou, zona inexistente, carimbo recusado…). Nada é gravado em `<saida>` quando há erro (o kit grava em `.parcial` e só troca no fim).

Outras funções úteis: `cues.gerar(palavras, projeto=…, video=…, formato=…, …)` → `{"doc", "arquivos", "nome", "largura", "altura", "da"}`; `cues.construir(palavras, d, L, A, formato, …)` → o documento em memória; `cues.editar(doc, d, cue, …)` → `(doc, descrição)`; `cues.gravar(doc, pasta, nome)`; `cues.validar(doc)` → lista de problemas; `legendar.conferir_contraste(d, amostras, L, A, estilo)`; `legendar.cadeia_da_base(d, info, L, A, enquadramento, foco, tratamento)`.

## 6. Carimbo da saída

`ferramenta: "video-legendas"`, `formato` = o mesmo do `cues.json` (nome de formato de vídeo da DA ou `LxA`; um 1280×720 nunca sai `thumbnail`), `auditoria: "n/a"`, `insumos` = [vídeo de entrada, arquivo de cues] e, em `parametros`: `cues_json`, `cues_sha256`, `palavras`, `fonte` (`video`, `inicio`, `fim`), `plataforma`, `estilo`, `animacao`, `n_cues`, `enquadramento`, `tratamento_da_da`, `editado`, `conferencia` (`zona_ok`, `menor_tamanho_fracao`, `contraste_pior`, `contraste_trechos_ruins`), mais os que `video.compor_cues` acrescenta (`base`, `cues` = nº de estados, `estados`, `inicio`, `duracao`, `tratamento_base`, `regiao`). A faixa com alfa leva também `so_overlay: true`, `codec`, `fps`, `quadros`.
