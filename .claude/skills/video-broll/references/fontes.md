# Fontes de b-roll — API, limites e regras de uso de cada provedor

Tudo aqui foi lido na documentação oficial ou medido contra a API em **2026-10-07**. A correspondência com o código foi reconferida em **2026-10-12** (o que mudou: Wikimedia pulada sem contato, risco médio para acervo que não confere licença, filtro de NC/ND no Internet Archive). O que não deu para verificar está marcado como **não verificado**. Revalide a cada três meses ou quando um provedor responder de forma estranha: abra o link, compare com a tabela e corrija `scripts/provedores.py` junto com este arquivo.

Leia quando: um provedor falhar, o usuário pedir uma fonte nova, for configurar chave, ou antes de aumentar o volume de buscas.

## Resumo

| provedor | chave | vídeo | imagem | limite de pedidos | o script espera | crédito na licença |
|---|---|---|---|---|---|---|
| Pexels | `PEXELS_API_KEY` | sim | sim | 200/hora e 20.000/mês | 1 s entre pedidos | opcional (a API pede link para o Pexels onde os resultados aparecem) |
| Pixabay | `PIXABAY_API_KEY` | sim | sim (até 1280 px) | 100 a cada 60 s; cache de 24 h obrigatório | 1 s | opcional (mostrar a origem ao exibir resultados) |
| NASA Image and Video Library | não | sim | sim | não documentado | 1 s | a NASA pede ser citada como fonte |
| Wikimedia Commons | não (contato obrigatório: sem `VIDEO_OPS_CONTATO` é pulada) | sim | sim | sem limite rígido de leitura; pedidos em série | 1 s | conforme a licença de cada arquivo |
| Internet Archive | não (identificação obrigatória) | sim | sim | respeitar 429 e `Retry-After` | 1 s | conforme a licença declarada no item |
| Openverse | não | **não** | sim | anônimo: 20/min e 200/dia | 3,2 s | conforme a licença de cada imagem |

Todo pedido leva `User-Agent: video-broll/<versão> (bot de pesquisa de b-roll, uso pessoal; <contato>) Python-urllib/<versão> (<modelo>)`:

- `<contato>` vem de `VIDEO_OPS_CONTATO` (variável de ambiente ou linha em `$VIDEO_OPS_HOME/chaves.env`): um e-mail ou URL **do usuário, escolhido por ele**. A Wikimedia exige contato e bloqueia sem aviso quem não se identifica: **sem `VIDEO_OPS_CONTATO` o script não a consulta** (pula, explica por quê e segue com os demais). Aos outros provedores, sem contato, o cabeçalho vai com «contato nao configurado: defina VIDEO_OPS_CONTATO». Na suíte, o contato fictício dos testes simulados nunca sai da máquina (um teste garante) e o teste de rede da Wikimedia só roda com contato real no ambiente. Nunca preencha com o e-mail do usuário por conta própria: pergunte.
- `<modelo>` vem de `VIDEO_OPS_AGENTE` (ex.: `VIDEO_OPS_AGENTE=claude-opus-5-5`). O Internet Archive pede que agentes de IA informem o modelo no User-Agent.

O cache fica em `broll/_busca/_cache/` e vale 24 h (exigência do Pixabay; cortesia com os demais). A chave nunca entra no cache, em mensagem de erro nem em log: `comum.mascarar` troca por `***`.

## Pexels

- Documentação: https://www.pexels.com/api/documentation/ · licença: https://www.pexels.com/license/
- Endpoints: `GET https://api.pexels.com/v1/search` (fotos) e `GET https://api.pexels.com/v1/videos/search` (vídeos). Autenticação pelo cabeçalho `Authorization: <chave>`.
- Parâmetros usados: `query`, `orientation` (`landscape` | `portrait` | `square`), `locale` (`pt-BR` na consulta em português), `per_page` (padrão 15, máximo 80).
- Resposta de vídeo: `id, width, height, url, image, duration, user{name, url}, video_files[{quality, file_type, width, height, fps, link}]`. Não há campo de tamanho: o `baixar.py` descobre por `HEAD`. Foto: `width, height, url, photographer, photographer_url, alt, src{original, large2x, large, medium, …}`.
- Limites: 200 pedidos por hora e 20.000 por mês por padrão. Os cabeçalhos `X-Ratelimit-Limit`, `X-Ratelimit-Remaining` e `X-Ratelimit-Reset` só vêm em respostas 2xx. Tentar contornar o limite encerra o acesso.
- Regras de uso da API: mostrar um link visível para o Pexels onde os resultados aparecem ("Photos provided by Pexels") e creditar o fotógrafo quando possível; não replicar a função central do Pexels (app de papéis de parede, por exemplo).
- **Não verificado com chave real** (não há chave nesta máquina): o interpretador foi testado com resposta simulada a partir dos campos documentados. Sem chave, em 2026-10-07 tanto `/v1/videos/search` quanto o caminho antigo `/videos/search` responderam `401 {"code": "Unauthorized", "message": "Missing API key"}`. O host dos arquivos (`videos.pexels.com`, `images.pexels.com`; links antigos em `player.vimeo.com`) também não foi conferido: se o primeiro download real for recusado por "host fora da lista", ajuste `Pexels.hosts`.

## Pixabay

- Documentação: https://pixabay.com/api/docs/ · licença: https://pixabay.com/service/license-summary/
- Endpoints: `GET https://pixabay.com/api/` (imagens) e `GET https://pixabay.com/api/videos/` (vídeos). A chave vai no parâmetro `key` da URL — é a única forma documentada; por isso a URL nunca é impressa nem gravada.
- Parâmetros usados: `q` (até 100 caracteres), `lang` (`pt` | `en`), `image_type=photo`, `video_type=film`, `orientation` (`horizontal` | `vertical`, só imagens), `safesearch=true`, `per_page` (3 a 200).
- Resposta de vídeo: `id, pageURL, tags, duration, videos{large, medium, small, tiny}{url, width, height, size, thumbnail}, user, user_id`. Imagem: `pageURL, tags, previewURL, webformatURL (válida por 24 h), largeImageURL, imageWidth, imageHeight, user`. A API entrega imagem em até 1280 px; resolução cheia só pelo site.
- Limites e regras: 100 pedidos a cada 60 segundos (`X-RateLimit-Limit/Remaining/Reset`); os resultados **têm de** ficar em cache por 24 h; usar a URL do Pixabay de forma permanente dentro de um produto não é permitido (baixe para o seu disco, é o que a skill faz); mostrar de onde vêm as imagens e os vídeos ao exibir resultados; download sistemático em massa é proibido.
- **Não verificado com chave real.** Sem chave, as duas rotas responderam `400 [ERROR 400] Invalid or missing API key` em 2026-10-07.

## NASA Image and Video Library

- Documentação: https://images.nasa.gov/docs/images.nasa.gov_api_docs.pdf (Release v1.22.0, de 2023-01-06) · regras de uso de mídia: https://www.nasa.gov/nasa-brand-center/images-and-media/ (página atualizada em 2026-08-13)
- Raiz `https://images-api.nasa.gov`; sem chave. `GET /search?q=&media_type=image|video|audio&page_size=` (padrão 100), `GET /asset/{nasa_id}` (lista de arquivos), `GET /metadata/{nasa_id}`, `GET /captions/{nasa_id}`. Resposta em Collection+JSON: `collection.items[].data[0]{nasa_id, title, description, center, date_created, keywords, photographer, secondary_creator}` e `links[]` (prévias).
- Medido em 2026-10-07: o manifesto `/asset/` devolve endereços com `http://` e **espaços no caminho** (o script troca por `https` e codifica); as versões têm sufixo `~orig`, `~large`, `~medium`, `~small`, `~mobile`, `~preview`; a busca **não informa duração, resolução nem tamanho** do vídeo. A duração e a resolução do original vêm de `metadata.json` (`QuickTime:Duration`, `QuickTime:ImageWidth`…) e o tamanho de cada versão, de um `HEAD`. Num vídeo de 4 min: orig 318 MB, large 164 MB, medium 75 MB, small 48 MB, mobile 11 MB.
- Limite de pedidos: a documentação não traz nenhum. O script usa 1 pedido por segundo.
- Uso: o conteúdo da NASA "em geral não está sujeito a direito autoral nos Estados Unidos"; a NASA deve ser citada como fonte; não pode sugerir endosso; a insígnia e os logotipos **não** estão em domínio público; pessoa identificável (astronauta, funcionário) em uso comercial pede autorização dela; material de terceiros publicado em sites da NASA continua protegido — o script avisa quando a descrição ou os metadados citam crédito de quem não é da casa, e rebaixa o risco para médio.

## Wikimedia Commons

- API: `https://commons.wikimedia.org/w/api.php` (MediaWiki Action API) · `prop=imageinfo`: https://www.mediawiki.org/wiki/API:Imageinfo · etiqueta: https://www.mediawiki.org/wiki/API:Etiquette (editada em 2026-05-13) · identificação: https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy (atualizada em 2026-03-27) · reuso: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia
- Consulta usada: `action=query&generator=search&gsrnamespace=6&gsrsearch=<termos> filetype:video|bitmap&prop=imageinfo|videoinfo&iiprop=url|size|mime|mediatype|extmetadata&iiurlwidth=500|1920&viprop=derivatives&maxlag=5&formatversion=2`.
- A licença vem de `extmetadata`: `LicenseShortName`, `LicenseUrl`, `License`, `AttributionRequired`, `Artist` (em HTML), `Credit`, `Restrictions`. Vídeo traz `duration` e, em `videoinfo.derivatives`, as transcodificações (`240p.vp9.webm` … `1080p.vp9.webm`) com `bandwidth` — o tamanho delas é estimado até o `HEAD`.
- Medido em 2026-10-07: a busca é de texto integral — `server room filetype:video` trouxe eventos de uma hora que só citam as palavras. O script busca primeiro a **frase exata** e só completa com as palavras soltas, que entram com nota menor. As miniaturas saem em larguras padronizadas (pedido de 480 px devolveu `500px-…`) pelo host `thumb.wikimedia.org`; os arquivos, por `upload.wikimedia.org`, com parâmetros `utm_*` que o script remove.
- Limites: "não há limite rígido de velocidade para leitura"; faça os pedidos em série; use `maxlag`; erro `ratelimited` pede espera crescente. `User-Agent` no formato `<cliente>/<versão> (<contato>) <biblioteca>/<versão>` é obrigatório — genérico ou sem contato "pode ser bloqueado sem aviso".
- Reuso: a Wikimedia Foundation **não garante** o status de direito autoral nem a correção da licença informada; restrições que não são de direito autoral (marca, direito de imagem) continuam valendo; quem reutiliza responde por isso. Domínio público não exige crédito, mas ele é recomendado.

## Internet Archive

- Busca: https://archive.org/help/aboutsearch.htm — `GET https://archive.org/advancedsearch.php?q=<consulta Lucene>&fl[]=identifier&…&rows=&output=json`; resultados paginados só até o 10.000º. Metadados: https://archive.org/developers/md-read.html — `GET https://archive.org/metadata/{identificador}` → `files[]{name, source, format, size, length, width, height}`. Arquivo: `https://archive.org/download/{identificador}/{arquivo}` (redireciona para um servidor `*.archive.org`; conferido por `HEAD` em 2026-10-07).
- Automação: https://archive.org/developers/bots.html — todo pedido automático leva `User-Agent` com nome da ferramenta, versão e, em agente de IA, o modelo; espera entre pedidos; respeitar `429` e `Retry-After`; cache; nova tentativa com espera crescente.
- Consulta usada: `(title:(<palavras com AND>) OR subject:"<frase>" OR description:"<frase>") AND mediatype:movies|image AND (licenseurl:*creativecommons.org* OR licenseurl:*publicdomain*) AND NOT licenseurl:*-nc* AND NOT licenseurl:*-nd*`. Medido: a consulta em texto livre ordenada por downloads devolveu filmes inteiros sem relação com o tema; por campo, o resultado é pertinente e pequeno.
- A licença é o campo `licenseurl`, **declarado por quem subiu o item**. O acervo tem muito material com licença errada (séries de TV marcadas como CC0 apareceram nos testes): por isso todo candidato daqui nasce com **risco médio** e o sinal âmbar «confira a origem» na folha, no plano e no registro, mesmo quando o texto diz domínio público. O risco só baixa por decisão do usuário, depois de abrir a página do item (`baixar.py … --risco baixo` ao montar o plano, ou `registro.py atualizar ID risco=baixo`). Os Termos de Uso (https://archive.org/about/terms) não abriram sem JavaScript em 2026-10-07 — **não verificado**.
- Os itens costumam ser filmes inteiros (12 min a 4 h; 40 a 350 MB): use `baixar.py --trecho A-B`.

## Openverse

- API: https://api.openverse.org/v1/ (esquema em https://api.openverse.org/v1/schema/, versão `909aa41…` lida em 2026-10-07) · termos: https://docs.openverse.org/terms_of_service.html (em vigor desde 2022-05-05)
- Só **imagens e áudio**; não há vídeo. `GET /v1/images/?q=&license_type=commercial,modification&aspect_ratio=wide|tall|square&page_size=&mature=false`. Resposta: `results[]{id, title, foreign_landing_url, url, creator, creator_url, license, license_version, license_url, source, width, height, filesize, filetype, thumbnail}`.
- Limites medidos nos cabeçalhos em 2026-10-07 (uso anônimo): `x-ratelimit-limit-anon_burst: 20/min` e `x-ratelimit-limit-anon_sustained: 200/day`; passou disso, `429`. O tamanho padrão da página é 20 e o esquema diz que tamanho e profundidade de paginação são limitados para anônimos, sem dar o número: o script nunca pede mais de 20. Os termos proíbem raspagem e contornar limites com várias máquinas.
- O Openverse "não verifica o status de licenciamento" e diz que cabe a você conferir de forma independente: o `url` do arquivo aponta para o site de origem (Flickr, museus), e é lá que a licença tem de ser confirmada antes do uso. Por isso todo candidato sai com esse aviso, com risco médio e com o sinal âmbar «confira a origem», como no Internet Archive.
- Medido: a miniatura (`/v1/images/{id}/thumb/`) responde `406` a `Accept: image/*`; o script pede `image/*,*/*;q=0.8`. Como o arquivo mora em outro site, o download aceita qualquer host público em `https` (rede privada e `localhost` são recusados).

## Acrescentar um provedor

1. Abra a documentação oficial hoje e anote endpoint, autenticação, limite, regra de atribuição e campos da resposta.
2. Em `scripts/provedores.py`, crie uma classe `Provedor` com `nome`, `rotulo`, `tipos`, `hosts`, `hosts_arquivo`, `intervalo`, `buscar()` (devolve candidatos por `candidato(...)`, que já aplica a política de licenças) e, se preciso, `detalhar()`.
3. Registre em `PROVEDORES` e `ORDEM`, guarde um trecho de resposta real em `scripts/testes/_dados/` e escreva o teste em `test_provedores.py`.
4. Acrescente a seção aqui, com a data.
