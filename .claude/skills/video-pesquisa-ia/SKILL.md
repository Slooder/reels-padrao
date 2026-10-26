---
name: video-pesquisa-ia
description: "Produz e mantém a ficha de fatos verificada de um vídeo sobre inteligência artificial: pesquisa/fatos.json com cada afirmação checável do roteiro (modelo, benchmark, preço, data, história, conceito, empresa) presa a fonte primária buscada NA WEB, com trecho literal conferido na página, data de acesso, confiança, redação segura (como_dizer) e data em que caduca — e prende roteiro, storyboard, crédito na tela e descrição a ela. Use ANTES de escrever ou gravar roteiro que cite modelos de IA, números, preços, datas ou “o melhor / o mais recente”, e sempre que o usuário disser “pesquisa esse tema”, “levanta os fatos pro vídeo”, “esse número está certo?”, “confere o roteiro”, “qual a fonte disso?”, “quanto custa o GPT/Claude/Gemini?”, “revalida antes de publicar” ou “me dá as fontes pra descrição” — mesmo sem dizer “ficha de fatos”. Nunca responda de memória sobre modelos, preços ou benchmarks de IA. Difere das irmãs: gerar-ganchos, gerar-roteiro e melhorar-roteiro ESCREVEM o texto (aqui só se diz o que é verdade, como dizer, e se reprova frase sem fato); video-animacao-explicativa e video-motion-graphics RENDERIZAM cenas e crédito (daqui sai o texto do crédito e a conferência dos fato_ids); video-broll cuida de licença de MATERIAL baixado, não de fatos; video-publicacao monta a descrição com o fontes.md daqui; video-direcao-de-arte decide a aparência do crédito (graficos.citacao_fonte)."
---

# Pesquisa e ficha de fatos para vídeos sobre IA

Regra nº 1: **nunca afirme de memória nada sobre modelos, preços, benchmarks ou empresas de IA**. A memória do modelo que executa esta skill termina meses antes de hoje, por construção, e o assunto muda todo mês. Ao montar esta skill em 2026-10-06, dos endereços de documentação que escrevi de memória pelo menos 11 tinham mudado de caminho ou de domínio (`references/fontes-primarias.md` §9), e as páginas oficiais de modelos e de preços abertas traziam nomes, versões e valores que não dá para afirmar de memória. O que você "sabe" serve para formular a busca; o que vai para o vídeo sai de uma página aberta hoje.

A ficha (`<projeto>/pesquisa/fatos.json`) é a fonte de verdade factual do vídeo, como a direção de arte é a visual. O roteiro cita fatos por marcador (`[F001]`); frase com dado checável e sem fato não é gravada. Um erro factual derruba a credibilidade do canal — o custo de checar é minutos, o de errar é o vídeo.

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }   # redefina em cada bloco: o shell não guarda funções entre chamadas
fatos --help            # 12 subcomandos, cada um com --help em PT-BR
```

Rode da raiz do projeto (o script sobe as pastas até achar `pesquisa/fatos.json`) ou passe `--projeto "<pasta>"`, antes ou depois do subcomando. Códigos de saída: **0** ok · **1** pendência ou reprovado · **2** não há ficha · **64** uso incorreto · **75** sem rede. Só biblioteca padrão (roda em Python ≥ 3.9); caminhos com espaço e acento funcionam (testado em `video-pesquisa-ia fecho/Vídeo 1 — como funciona um modelo/`).

Leia quando precisar: `references/fontes-primarias.md` (ONDE procurar, por laboratório e por tipo de fato — endereços conferidos em 2026-10-06; leia antes de qualquer busca) e `references/metodo.md` (como julgar o que a página diz: benchmark autodeclarado, contexto × saída, preço por token, anúncio × disponibilidade, pesos × código aberto, corte de conhecimento, divergência, fórmulas de redação, limites do conferidor — leia quando o fato não for trivial).

Esta skill não renderiza nada, por isso não tem "Passo 0 — Direção de arte": a pesquisa vem **antes** da DA no pipeline (pesquisa → roteiro → DA) e a ficha funciona num projeto sem `da/da.json`. O único contato com a DA é o crédito de fonte na tela (passo g).

## O método

### a) Decompor o tema ou o roteiro em afirmações verificáveis

Uma frase carrega várias afirmações ("o modelo X, lançado em março, lê 1 milhão de tokens e custa metade do Y" são quatro). Liste uma por linha, com **quem** (variante exata), **o quê** (grandeza e unidade), **quando** (data a que se refere) e a categoria: `modelo`, `benchmark`, `preco` (voláteis: exigem `caduca_em` e fonte primária), `historia`, `conceito`, `empresa`, `outro`. Um fato por afirmação, porque cada uma caduca num ritmo.

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }
fatos novo --tema "Como funciona um modelo de linguagem" --projeto .   # cria pesquisa/fatos.json na pasta atual; não sobrescreve
fatos conferir-roteiro roteiro/roteiro.md                               # código 1: a lista de pendências é a sua lista de pesquisa
```

O `--projeto .` confirma que a pasta atual é a raiz (sem ele, numa pasta ainda sem `da/`, `roteiro/` nem `pesquisa/`, o `novo` recusa com código 64 para não criar ficha no lugar errado). Com a ficha vazia, toda frase com número (em dígitos **ou por extenso**), data, dinheiro, percentual, superlativo, tempo relativo ou nome de modelo com versão sai como pendência — títulos e linhas de tabela também. Afirmação conceitual sem número nem nome ("a IA só completa a próxima palavra") o script não vê: ache-as lendo.

### b) Buscar NA WEB a fonte primária de cada uma

1. Carregue as ferramentas se não estiverem disponíveis: ToolSearch com `select:WebSearch,WebFetch`.
2. Ache a página certa em `references/fontes-primarias.md` (§1 diz qual abrir para cada tipo de fato). Primária = quem tem autoridade sobre o dado: documentação oficial, model card, artigo científico, changelog, página de preços, comunicado. Imprensa, blog, enciclopédia e agregador são secundárias: servem para achar a primária.
3. Abra a página (WebFetch) e localize o dado. Anote: título, URL final, editor (nome curto de quem publica — é o que aparece no crédito), data de publicação ou de "última atualização" (`null` se a página não declara) e o **trecho literal**: pedaço contíguo da página, no idioma original, com no máximo 25 palavras, que contém o dado.
4. O WebFetch resume; ele não transcreve. O trecho só vale depois de conferido contra a página no passo c.
5. Não achou primária? O fato entra como `nao_confirmado` e fica fora do roteiro. Não promova secundária a primária e não complete com o que você lembra.

Primária não é sinônimo de independente: nota de benchmark publicada pelo fabricante é primária **e** autodeclarada — registre `"autodeclarado": true`.

### c) Registrar e provar que leu

Grave os fatos da rodada numa lista JSON (arquivo com nome iniciado por `_` é intermediário) e adicione de uma vez — a lista entra inteira ou não entra. O molde abaixo é **fictício de propósito**: colado sem preencher, o `adicionar` recusa (datas `AAAA-MM-DD`), porque exemplo com preço real vira "fato" copiado sem ninguém abrir a página.

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }
cat > "pesquisa/_novos.json" <<'EOF'
[{"afirmacao": "Em <mês> de <ano>, a tabela oficial do Laboratório Exemplo cobrava US$ <valor> por milhão de tokens de entrada no Modelo Exemplo X.",
  "valor": 0, "unidade": "US$ por 1M de tokens de entrada", "referente_a": "AAAA-MM-DD",
  "categoria": "preco", "status": "confirmado", "confianca": "alta", "caduca_em": "AAAA-MM-DD",
  "fontes": [{"titulo": "Pricing", "url": "https://example.com/pricing", "editor": "Laboratório Exemplo", "tipo": "primaria",
              "publicado_em": null, "acessado_em": "AAAA-MM-DD", "trecho": "<linha da tabela, copiada da página no idioma original>"}],
  "como_dizer": "Em <mês> de <ano>, 1 milhão de tokens de entrada no Modelo Exemplo X custava US$ <valor> na tabela oficial do Laboratório Exemplo.",
  "notas": "Nível pago, modo padrão; o preço de saída é outro fato.", "termos": ["Modelo Exemplo X"]}]
EOF
fatos adicionar "@pesquisa/_novos.json"     # atribui F001, F002…; recusa fato inválido e duplicata; nada é gravado se um item reprovar
fatos validar                               # erros reprovam (código 1); avisos orientam
fatos checar-links --trechos                # abre cada URL, procura o trecho e GRAVA o resultado em cada fonte; código 1 se faltar prova
```

- **`checar-links --trechos` é a prova de que o fato foi lido, não lembrado.** Cada fonte ganha `conferencia`: `encontrado`, `ausente` (a página abriu e o trecho não está lá — o dado mudou, o trecho não era literal, ou a página é montada por JavaScript) ou `nao_verificado` (o robô não leu: bloqueio, PDF, sem resposta). Enquanto um fato confirmado tiver fonte ausente, não verificada ou nunca conferida, ele não ganha crédito (`credito` recusa), `validar --estrito` e `conferir-roteiro --estrito` reprovam, e o `resumo` o marca com `!`. Trocar a URL ou o trecho apaga a conferência.
- **O robô não lê a página?** Abra-a você (WebFetch ou navegador), ache o trecho e declare: `fatos atualizar F003 --conferido-manual "onde e como li: tabela Models, linha do modelo, coluna Context window"`. A nota (mínimo de 20 caracteres) fica na ficha e no `fatos.md` com a data — é assinatura, não atalho. Ela só cai diante de evidência nova (o robô passa a ler a página e não acha o trecho).
- **O que `validar` reprova**: campo do contrato ausente ou de tipo errado; `confirmado` sem 1 fonte primária ou 2 secundárias de editores e domínios distintos (a mesma página não conta duas vezes); `preco`, `benchmark` ou `modelo` confirmado sem fonte primária, ou sem `caduca_em`; `confianca: alta` sem fonte primária; URL que não é `https`; trecho vazio ou com mais de 25 palavras; data inválida ou futura; `acessado_em` ausente; `divergente` com menos de 2 fontes. Avisa (e `--estrito` reprova): trecho ausente ou não conferido, fato vencido, validade acima de 180 dias em categoria volátil, `como_dizer` sem data ou sem atribuição, superlativo sem data, enciclopédia marcada como primária, fato sustentado só por fórum ou blog.
- **`caduca_em`**: sugestão da casa de 30 dias para preço e 60 para modelo e benchmark (`--caduca-padrao` aplica); se a fonte anuncia uma mudança, vale a data mais próxima. História e conceito usam `null`. **`--acessado-hoje`** preenche `acessado_em` nas fontes sem o campo — só use se abriu a página hoje; a data não substitui a conferência do trecho.
- **Duplicata**: mesma afirmação, ou a mesma medida do mesmo modelo tirada da mesma página. Modelos diferentes com o mesmo preço na mesma tabela são fatos diferentes e entram normalmente (o nome do modelo, na `afirmacao` e em `termos`, é o que os distingue).
- **Gravação**: só o `fatos.py` escreve na ficha, dentro de uma trava (`pesquisa/_fatos.lock`), e guarda a versão anterior em `pesquisa/_fatos.anterior.json`. Comandos disparados em paralelo esperam a vez (até 20 s); ainda assim, prefira uma lista num `adicionar` só.
- Mudou algo? `fatos atualizar F003 "@pesquisa/_mudanca.json"` (JSON só com os campos que mudam) ou os atalhos `--status`, `--confianca`, `--caduca-em`, `--como-dizer`, `--notas`, `--nova-fonte @fonte.json`. `fatos remover F003 --sim` tira o fato (sem `--sim` só simula); o id nunca é reaproveitado, porque roteiro e storyboard apontam para ele.

### d) Tratar divergência entre fontes

1. Confira se falam da mesma coisa: unidade, variante do modelo, modalidade, nuvem, data. Quase toda divergência morre aqui.
2. Primária vence secundária; entre primárias, a tabela de referência vence o post de anúncio e a mais recente vence a antiga.
3. Persistiu: registre `"status": "divergente"` com as duas fontes e `notas` dizendo quem diz o quê.
4. `divergente` é estado de trabalho, não de entrega — `conferir-roteiro` reprova fato citado que não esteja `confirmado`, e a fonte dele fica fora do `fontes.md`. Ou você reescreve a afirmação de modo que as duas fontes a sustentem (atribuição: "a documentação lista X; o anúncio falava em Y"; ou faixa) e ela passa a `confirmado`, ou o dado sai do roteiro. Detalhe em `metodo.md` §13.

### e) Redigir `como_dizer`

É a frase que o roteirista copia — e a lista do que o roteiro **pode** dizer: `conferir-roteiro` aceita o `valor`, os números e datas do `como_dizer` e as formas de `termos`. Número que está só na `afirmacao` (o aumento anunciado, a outra coluna da tabela) ou só no trecho da fonte não valida frase nenhuma. Regras, cada uma com seu motivo:

- **Datada** ("em outubro de 2026, …"): o vídeo fica no ar depois que o dado muda; a data mantém a frase verdadeira.
- **Atribuída quando autodeclarada** ("segundo a própria empresa, …"): quem assiste precisa saber de quem é a conta.
- **Com a unidade inteira** ("por milhão de tokens de entrada, no nível pago"): "custa x" sem unidade é falso para metade dos casos.
- **Sem tempo relativo** ("hoje", "atualmente", "o mais recente") e **sem superlativo sem critério e data**.
- **Arredondada com honestidade** ("cerca de"): os números do `como_dizer` são os que o roteiro pode usar.

Fórmulas prontas em `metodo.md` §14.

### f) Conferir o roteiro

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }
fatos conferir-roteiro roteiro/roteiro.md                       # 0 = nenhuma pendência (pode haver avisos: leia-os)
fatos conferir-roteiro roteiro/roteiro.md --estrito             # avisos também reprovam: é ESTE que libera a gravação
fatos conferir-roteiro roteiro/roteiro.md --json --saida pesquisa/_conferencia.json   # relatório em JSON, para guardar ou conferir por script
```

No roteiro, o marcador vai **no fim da frase a que se refere**, antes ou depois do ponto: `… custava US$ <valor> [F004].` Vários: `[F001, F002]`. Frase que tem número mas não é afirmação leva `[sem-fato]` ou `[opinião]` — o relatório lista as dispensadas para alguém conferir.

- **Pendências (código 1)**: dado checável sem marcador (mesmo quando um fato parece cobri-lo — o relatório sugere qual, você decide); nome de modelo com versão que nenhum fato confirmado registra; verbo de lançamento, preço, licença ou compra, ou tempo relativo ("semana passada"), junto de um nome; na frase marcada, número, data, moeda ou modelo que não bate **por tipo** com o fato citado (dinheiro com dinheiro, percentual com percentual, data com data, contagem com contagem), entrada × saída trocadas, grandeza trocada (tokens × palavras), "por mês" citando preço de API, superlativo que o fato não sustenta; marcador para id inexistente; fato usado com `status` ≠ `confirmado`, vencido ou com trecho ausente.
- **Avisos**: frase só com nome próprio; nome que não está no fato citado; número pequeno em frase dirigida ao espectador ("você sabia que só 5 países…"); "hoje"/"atualmente" em fato volátil; fato com trecho ainda não conferido; fato que vence em até 14 dias (`--dias N`).
- **Ignora de propósito** (e lista em "NÚMEROS IGNORADOS"): número pequeno em fala na primeira pessoa, chamada ("comenta 1", "manda para 2 amigos") e analogia declarada ("imagina…"); contagens editoriais ("3 motivos"), durações e minutagem ("em 60 segundos", "0–3s"); o bloco "Checklist"; cabeçalho de tabela.

Repita até dar 0 pendências e, com `--estrito`, 0 avisos. Corrigir é: pesquisar e registrar o fato, reescrever a frase com o `como_dizer`, ou tirar a afirmação. Nunca "ajustar" o fato para caber na frase. Se a frase diz o mesmo dado de um jeito que o script não reconhece, ou cita um modelo de família nova, acrescente a forma em `termos` do fato.

É um portão por padrões de texto, não um revisor. Medido em 2026-10-06, frase a frase: no conjunto usado para ajustar as regras, 0 de 42 frases problemáticas passavam; em 30 frases novas medidas às cegas, 5 passaram no modo padrão (4 com aviso — uma dessas regras virou pendência depois da medição — e 1 sem nada) e essa última passou até com `--estrito` (afirmação sem número nem nome); de 20 frases inocentes novas, 1 virou pendência. Leia o relatório inteiro; `metodo.md` §15 lista o que ele não vê.

### g) Entregar créditos para a tela e fontes para a descrição

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }
fatos md --roteiro roteiro/roteiro.md      # pesquisa/fatos.md (ficha legível) + pesquisa/fontes.md (só as fontes dos fatos citados)
fatos credito F004                         # Fonte: Editor, mês/ano
fatos credito F004 --sem-prefixo           # Editor, mês/ano   ← valor de params.fonte das cenas
fatos credito F004 --caber vertical        # mede com a DA do projeto; código 1 se o crédito não couber na zona segura
fatos conferir-storyboard                  # roteiro/storyboard.json: fatos, números da tela e créditos
```

- **Crédito na tela**: padrão "Fonte: Editor, mês/ano" (mês da publicação; se a página não tem data, mês do acesso). Só sai de fato confirmado **com trecho conferido**. As cenas `citacao` e `barras` do motor da direção de arte recebem `params.fonte` e desenham o crédito com a peça compartilhada do kit, que **põe o prefixo** (token `graficos.citacao_fonte.prefixo`, padrão "Fonte: ") — passe a saída de `--sem-prefixo`. Cena própria de outra skill usa a mesma peça: `ctx.kit.credito("Editor, mês/ano", { plataforma })` (lido em `kit/motor/cenas/_credito.js` em 2026-10-06; confira em `kit-api.md`). Papel, tamanho, cor, posição e prefixo vêm do token `graficos.citacao_fonte` da DA; esta skill nunca escolhe cor nem fonte. Toda cena que mostra número leva crédito: no storyboard, `"fato_ids": ["F004"]` e `"params": {"fonte": "Editor, mês/ano"}`. As cenas embutidas `titulo`, `gc` e `moldura` não desenham crédito (kit 1.3.0): leve o número para `barras` ou `citacao` — o `conferir-storyboard` avisa. Testado: `barras` em 960×540, quadro 3,5 s, desenhou "Fonte: Anthropic, out/2026" no canto inferior direito.
- **`conferir-storyboard`** reprova: fato inexistente, não confirmado, vencido ou com trecho ausente; cena com número e sem `fato_ids`; e **número que vai para a tela** (no `trecho`, nos textos de `params` e em `params.dados[].valor`, com o tipo dado por `prefixo`/`unidade`) que não bate com o fato citado. Avisa crédito ausente, diferente ou que já traz "Fonte:" no parâmetro. Não lê imagem nem confere rótulos: olhe o quadro renderizado.
- **`--caber FORMATO`** usa o kit em `"$CRIABR_SKILLS"/video-direcao-de-arte/kit` e precisa de Pillow; sem DA no projeto devolve código 2 e diz para criar a DA — não inventa medida. Mede o texto como vai para a tela (prefixo da DA + crédito). No teste (preset lab-ia): "cabe: “Fonte: Anthropic, out/2026” mede 296.6 px de 660 px úteis no formato vertical". `--todas` cita todas as fontes do fato; `--data ano` encurta.
- **`fontes.md`** traz a lista pronta entre `<!-- DESCRICAO:INICIO -->` e `<!-- DESCRICAO:FIM -->` (uma linha por fonte única, numerada, com a URL), a contagem de caracteres contra o limite de descrição que o kit registra em `plataformas.json`, e uma versão de uma linha entre `<!-- CURTA:INICIO -->` e `<!-- CURTA:FIM -->` para Shorts, Reels e TikTok. Só entram fontes de fatos confirmados; divergentes e não confirmados ficam de fora. Não edite os `.md`: gere de novo.

### h) Revalidar os fatos voláteis antes de publicar

Entre a pesquisa e a publicação passam dias ou semanas. No dia de publicar (e de novo se o vídeo atrasar):

```bash
fatos() { python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py "$@"; }
fatos vencidos --hoje 2026-11-20            # simula a data de PUBLICAÇÃO: o que estará vencido quando o vídeo sair? (código 1 se houver)
fatos checar-links --trechos                # as páginas abrem e os trechos continuam lá? grava a conferência de hoje
fatos atualizar F004 --revalidado --caduca-em 2026-12-05    # só passa com o trecho conferido HOJE (automático ou --conferido-manual)
fatos checar-links --trechos && fatos validar --estrito && fatos conferir-roteiro roteiro/roteiro.md --estrito && fatos md --roteiro roteiro/roteiro.md
```

A última linha é o portão de publicação: qualquer elo que falhe interrompe a cadeia. Se há storyboard, rode também `fatos conferir-storyboard --estrito`. `--hoje` (ou `VIDEO_OPS_HOJE`) só simula **leitura**; comando que grava recusa a opção e usa a data real. `--revalidado` é uma declaração de que você abriu a página hoje, não um botão de adiar — por isso exige a conferência do dia. Se o valor mudou: atualize `valor`, `afirmacao`, `como_dizer` e o `trecho` da fonte; rode `conferir-roteiro` (ele acusa o número antigo no roteiro) e `conferir-storyboard`; as cenas com esse `fato_id` precisam ser renderizadas de novo; se o vídeo já foi gravado, a correção entra na tela ou na descrição — diga isso ao usuário, não esconda.

## O que NÃO afirmar

- **"O melhor modelo", "o mais inteligente", "o mais avançado", "líder"** sem critério e data. Diga o teste, o placar e o dia: "no teste Z de outubro de 2026, A marcou x".
- **"O mais recente", "acabou de lançar", "hoje", "atualmente"**: troque por data.
- **Número de parâmetros, custo de treino, tamanho dos dados** que o fabricante não divulga. O fato confirmável é "a empresa não divulga".
- **Nota de benchmark do fabricante como se fosse medida independente.**
- **"Open source"** para modelo com pesos disponíveis sob licença restritiva: diga "pesos abertos sob a licença X".
- **Janela de contexto como se fosse limite de saída**, e tokens como se fossem palavras.
- **Preço sem unidade, nível e data**; preço de assinatura como se fosse de API; preço de entrada como se fosse de saída.
- **"Pensa", "entende", "sabe", "quer"** como fato técnico. É figura de linguagem: use de propósito, não por descuido.
- **"Estudos mostram"** com um estudo só; pré-publicação como se fosse consenso.
- **Qualquer coisa que só você (o modelo) lembra** e nenhuma página aberta hoje sustenta.

## Contrato e arquivos

`pesquisa/fatos.json` segue o contrato da casa: `{"versao": 1, "tema", "atualizado_em", "fatos": [{"id", "afirmacao", "valor", "unidade", "referente_a", "categoria", "status", "confianca", "caduca_em", "fontes": [{"titulo", "url", "editor", "tipo", "publicado_em", "acessado_em", "trecho"}], "como_dizer", "notas"}]}`. Campos acrescentados por esta skill, todos opcionais: no fato, `termos` (nomes, apelidos e outras formas de dizer o dado, que entram no cruzamento com o roteiro), `autodeclarado` (bool), `verificado_em` (gravado por `--revalidado`); na fonte, `conferencia` (`{"estado", "em", "metodo", "marca", …}`, só escrita pelo `fatos.py`); na raiz, `ultimo_id`. Intermediários: `pesquisa/_fatos.anterior.json`, `pesquisa/_fatos.lock`, `pesquisa/_links.json` (última checagem de links), `pesquisa/_conferencia.json` (se pedido com `--saida`).

Outras skills importam o módulo por posição: `sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "video-pesquisa-ia" / "scripts")); import fatos` → `fatos.carregar(projeto=…)`, `fatos.validar_ficha(ficha)`, `fatos.conferir_roteiro(texto, ficha)`, `fatos.conferir_storyboard(sb, ficha)`, `fatos.credito(fatos.obter(ficha, "F001"))`, `fatos.conferencia_do_fato(f)["ok"]`, `fatos.vencimentos(ficha)`.

## Testes

```bash
cd "$CRIABR_SKILLS"/video-pesquisa-ia/scripts && python3 -B -m unittest                                           # 126 testes; os 5 de rede são pulados sem conexão
cd "$CRIABR_SKILLS"/video-pesquisa-ia/scripts && python3 -B -m unittest testes.test_fatos testes.test_regressao   # só os 121 sem rede (cerca de 1 min)
```

`-B` evita deixar `__pycache__` dentro da skill. Os testes criam tudo em pasta temporária com espaço e acento no nome, usam relógio fixo e sobem um servidor HTTP local para os estados de link e a conferência de trechos. `test_regressao.py` guarda os testes dos defeitos achados na revisão de 2026-10-06. Os 121 sem rede passam também no `/usr/bin/python3` 3.9.

## Armadilhas (observadas ao construir, revisar e corrigir em 2026-10-06)

- **O que o WebFetch mostra não é o que a página traz.** Pedi a frase do artigo do Transformer e recebi "…the model is auto-regressive, consuming…"; na página está "…auto-regressive [10], consuming…". Numa tabela oficial de preços, o WebFetch devolveu as colunas numa ordem e o HTML as tinha em outra (com uma descrição do modelo no meio); numa página de modelos, a nota de rodapé que eu queria citar nem existia no HTML — estava só na versão em markdown (`<endereço>.md`). Nos três casos `checar-links --trechos` devolveu `ausente`. Use como trecho um fragmento contíguo, sem marcas de citação, e ajuste-o até o robô achar; se a página não entrega o texto ao robô, `--conferido-manual`.
- **Número certo no lugar errado passava.** Antes da correção, num fato de exemplo de US$ 0,75, as frases "custava US$ 6", "US$ 10" e "US$ 31" eram aceitas, porque a ficha continha `2026-10-06` e o trecho dizia "December 31". Hoje a comparação é por tipo e só vale o que está em `valor`, `como_dizer` e `termos` — se o roteiro vai dizer um segundo número do mesmo fato, ele precisa estar no `como_dizer` (ou ser outro fato).
- **Fato inventado atravessava tudo com código 0.** Um preço falso com trecho inventado era `confirmado/alta`, passava em `validar --estrito` e ganhava crédito; o "trecho ausente" era só texto na tela. Hoje a conferência fica gravada na fonte e é ela que libera crédito e `--estrito`.
- **Seis `adicionar` ao mesmo tempo gravaram 4, 5 e 3 fatos de 6**, com seis códigos 0 e ids repetidos (três rodadas, antes da trava). Agentes disparam chamadas em paralelo por padrão: a trava resolve, a lista JSON evita.
- **Número por extenso era invisível**: "custava nove dólares [F004]" passava contra um fato de quatro dólares. Hoje é lido; continuam fora "um/uma" sozinhos ("um gigawatt") e quantidades vagas ("a maioria").
- **Regra ajustada a um conjunto de frases mente sobre si mesma.** No conjunto usado para ajustar, nada escapava; em frases novas, 5 de 30 escaparam no modo padrão. Só confie na taxa medida em frases que a regra nunca viu.
- **Endereço de memória também caduca.** `platform.openai.com/docs/models` virou `developers.openai.com/api/docs/models`; `lmarena.ai` virou `arena.ai`; `paperswithcode.com` cai em `huggingface.co/papers/trending`; `llama.com` cai em `dev.meta.ai`. Chegue pela busca ou por `fontes-primarias.md` e registre a URL final que o `checar-links` mostrar.
- **`bloqueado` não é `quebrado`, e cada ferramenta é barrada num lugar.** `ai.meta.com/blog/` deu 400 no `fatos.py` e abriu no WebFetch; `openai.com/business/pricing/` deu 403 numa rodada do `fatos.py` e 200 um minuto depois; EUR-Lex responde 202 vazio; o WebFetch recusa `web.archive.org`. Troque de ferramenta antes de dar o link por morto; para o fato, o caminho é `--conferido-manual`.
- **`ai.google.dev` entra em laço de redirecionamento quando o cliente se apresenta como navegador e não devolve cookies**: `curl -sL -A "Mozilla/5.0 … Chrome/126.0 …"` parou em 50 redirecionamentos (`curl: (47)`), passando por `accounts.google.com`; o mesmo `curl` sem `-A` recebeu 200 direto, e com `-A` mais `-b ""` (cookies ligados) recebeu 200. O `fatos.py` usa agente de navegador e guarda cookies em memória durante a requisição.
- **A mesma página do Google vem traduzida conforme o `Accept-Language`**, e o trecho em inglês deixa de ser encontrado. O `fatos.py` pede inglês primeiro; se você conferir à mão em português, compare com a versão em inglês (`?hl=en`).
- **Preço com data marcada para mudar.** Uma tabela oficial trazia, na mesma célula, o preço vigente "até" uma data e o novo "a partir de" outra. Registrar só o primeiro número cria um fato que vence sem aviso: ponha a mudança na `afirmacao` e `caduca_em` antes dela.
- **A data da versão lida não é a data do artigo.** Registrei `publicado_em` com a data da versão v7 e o crédito saiu "arXiv, ago/2023" para um artigo de 2017. `publicado_em` é a primeira versão; a versão lida vai no `titulo`.
- **O conferidor não enxerga conceito.** "Um modelo autorregressivo escreve um token por vez" passou sem marcador e sem aviso (não tem número nem nome), e o fato correspondente apareceu como "não usado". Na medição cega, "consome a energia de uma cidade pequena" também. Frases assim dependem da leitura do passo a.
- **`--hoje` num comando que grava deixava a ficha com data futura** (`atualizado_em` e `acessado_em` em 2026-11-20) e o `validar` seguinte reprovava. Hoje esses comandos recusam `--hoje` (código 64) e ignoram `VIDEO_OPS_HOJE` com uma nota.
- **`--quadro fim` não serve para conferir o crédito.** Renderizei a cena `barras` no último instante e o quadro saiu só com o fundo (a cena já tinha saído). Use um tempo do meio: `--quadro 3.5` numa cena de 6 s.
- **`--caber` no Python do sistema falha por falta de Pillow** (`/usr/bin/python3` 3.9 nesta máquina): a mensagem manda usar o Python que tem Pillow e numpy (`python`). Todo o resto do `fatos.py` roda nos dois.
- **Guardar o comando numa variável não funciona.** `F="python3 ~/.claude/…/fatos.py"; $F validar` dá "no such file or directory" no zsh (ele não separa a variável em palavras) e "can't open file '…/~/.claude/…'" no bash (`~` entre aspas não expande). Por isso os exemplos usam função.
