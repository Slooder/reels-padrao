# Licenças de b-roll — o que cada uma permite, o que exige e o que a política faz

Resumo das licenças que a skill encontra, lido nas páginas oficiais em **2026-10-07**. A correspondência com o código foi reconferida em **2026-10-12**. Não é parecer jurídico: é a regra de operação da casa, conservadora de propósito. A política mora em `scripts/registro.py` (`LICENCAS`) e vale para tudo o que entra em `broll/licencas.json`, venha de `baixar.py` ou de outra skill.

Leia quando: um candidato for recusado e o usuário perguntar por quê; for registrar exceção (citação, autorização); for escrever os créditos da descrição; o vídeo for patrocinado ou monetizado.

```bash
python3 "$CRIABR_SKILLS"/video-broll/scripts/registro.py politica             # a tabela, como o código a aplica
python3 "$CRIABR_SKILLS"/video-broll/scripts/registro.py avaliar "CC BY-NC 4.0"   # código 1 = recusada
```

## Entram por padrão

| licença | crédito | comercial | adaptar (recortar, tratar a cor) | risco | página oficial |
|---|---|---|---|---|---|
| Licença do Pexels | opcional | sim | sim | baixo | https://www.pexels.com/license/ |
| Licença de conteúdo do Pixabay | opcional | sim | sim | baixo | https://pixabay.com/service/license-summary/ |
| CC0 1.0 | opcional | sim | sim | baixo | https://creativecommons.org/publicdomain/zero/1.0/ |
| Domínio público (marca PDM 1.0 ou declaração da fonte) | opcional | sim | sim | baixo | https://creativecommons.org/publicdomain/mark/1.0/ |
| Mídia da NASA | **obrigatório** (citar a NASA) | sim, sem sugerir endosso | sim | baixo | https://www.nasa.gov/nasa-brand-center/images-and-media/ |
| CC BY (qualquer versão) | **obrigatório** | sim | sim | baixo | https://creativecommons.org/licenses/by/4.0/ |
| CC BY-SA (qualquer versão) | **obrigatório** | sim | sim, e a adaptação herda a licença | **médio** | https://creativecommons.org/licenses/by-sa/4.0/ |

O que cada página diz, em resumo fiel:

- **Pexels** — tudo é gratuito para usar, o crédito "não é exigido" e pode modificar. Não pode: mostrar pessoa identificável de forma negativa ou ofensiva; vender cópia sem alteração; sugerir endosso de pessoas ou marcas que aparecem na imagem; redistribuir em outro banco de imagens; usar como parte de marca registrada.
- **Pixabay** — usar de graça, sem atribuição, e adaptar em obras novas. Não pode: vender ou distribuir o conteúdo isolado, sem esforço criativo; usar conteúdo com marca ou logotipo reconhecível para fins comerciais ligados a produtos e serviços; uso imoral, ilegal ou enganoso, em especial com pessoa reconhecível; usar como parte de marca.
- **CC0** — o autor renunciou aos direitos: copiar, modificar, distribuir e executar, inclusive comercialmente, sem pedir permissão. Marcas e patentes não são afetadas; direito de imagem e privacidade de quem aparece continuam valendo; não sugerir endosso.
- **NASA** — o conteúdo "em geral não está sujeito a direito autoral nos Estados Unidos" e pode ser usado de forma factual; "a NASA deve ser reconhecida como a fonte do material". Não pode sugerir que a NASA endossa produto ou serviço; a insígnia e os logotipos não estão em domínio público; pessoa identificável em uso comercial pede autorização dela; material de terceiros em sites da NASA exige contato com o titular.
- **CC BY 4.0** — compartilhar e adaptar para qualquer fim, inclusive comercial, desde que dê "o crédito apropriado, forneça um link para a licença e indique se foram feitas alterações". Outros direitos (imagem, privacidade, morais) podem limitar o uso.
- **CC BY-SA 4.0** — o mesmo, mais: "se remixar, transformar ou criar a partir do material, tem de distribuir as suas contribuições sob a mesma licença".

### Acervo que não confere a licença: risco médio

No Internet Archive e no Openverse a licença é a que **quem subiu o item declarou**; o acervo não confere. O candidato entra quando o texto é de licença permitida, mas nasce com risco **médio** e «confira a origem» (sinal âmbar na folha, `risco medio` no plano e no registro, linha em "Atenção antes de publicar" quando usado). A mesma obra pode aparecer na NASA com «crédito obrigatório» e, recarregada por um usuário, no Internet Archive como «domínio público»: vale a fonte original. O usuário rebaixa o risco depois de abrir a página de origem: `--risco baixo` ao montar o plano, ou `registro.py atualizar B002 risco=baixo`.

### Por que CC BY-SA é risco médio

O FAQ da Creative Commons diz que se um uso é adaptação "depende principalmente da lei de direito autoral aplicável" — e que sincronizar música com imagem em movimento é sempre adaptação. Para um trecho de vídeo dentro de outro vídeo não há resposta única. Se o seu uso contar como adaptação, o vídeo final teria de ser licenciado sob CC BY-SA. Consequência prática:

- canal próprio, vídeo explicativo: em geral aceitável, e o registro avisa;
- **peça patrocinada, vídeo de cliente, material que será licenciado a terceiros**: troque por CC BY, CC0, Pexels ou Pixabay (`buscar.py --licenca sem-atribuicao` mostra só o que dispensa crédito).

## Recusadas por padrão

| licença | por quê | página oficial |
|---|---|---|
| CC BY-NC, CC BY-NC-SA | NC proíbe uso "para fins comerciais" — o FAQ define como uso "principalmente destinado ou dirigido a vantagem comercial ou compensação monetária". Canal monetizado e peça patrocinada caem aí; a CC não arbitra casos | https://creativecommons.org/licenses/by-nc/4.0/ |
| CC BY-ND, CC BY-NC-ND | ND: "se remixar, transformar ou criar a partir do material, não pode distribuir o material modificado". Recortar, tratar a cor e montar com outro material é modificar | https://creativecommons.org/licenses/by-nd/4.0/ |
| Todos os direitos reservados (inclui a licença padrão do YouTube) | não há permissão de reuso | — |
| Desconhecida, ausente ou fora da lista (GFDL, "Attribution" e "Copyrighted free use" do Commons, Sampling+) | sem licença identificada não há permissão; as do fim da lista têm condições que a skill não sabe cumprir | — |

Recusa não é opinião sobre a obra: é a skill dizendo que não sabe garantir o uso. O candidato recusado aparece com `buscar.py --licenca todas` (sinal vermelho na folha) e `baixar.py` não o baixa.

A leitura do texto da licença é **fechada**: marca de restrição vence em qualquer grafia — colada (`CCBYNC`, `CC-BY-NCSA`, `cc-by-ncnd`), pontuada (`cc by n.c.`), com espaço no meio (`CC BY-N C`) ou com traço tipográfico (`CC BY–NC 4.0`). Reconhecido «CC BY», termo que sobra sem ser versão, jurisdição ou palavra do nome da licença faz o texto valer como **desconhecido**; «public domain in the US only; copyrighted elsewhere» é desconhecida, não domínio público; texto e URL que divergem valem pela mais restritiva. Na dúvida: `registro.py avaliar "<o texto como veio>"`.

## Exceção: só com base legal e nota

O registro aceita material fora da política quando `base_legal` é `citacao` ou `autorizacao` **e** `notas` explica. `proprio` não é exceção: é a declaração de que o material é da casa, e tem regra própria (última linha).

| `base_legal` | quando | o que a nota tem de dizer | padrões que o registro aplica |
|---|---|---|---|
| `citacao` | trecho curto de obra de terceiro usado para comentar, criticar ou explicar | o que é citado e para quê | crédito obrigatório, sem uso comercial, risco médio |
| `autorizacao` | o titular autorizou por escrito | quem autorizou, quando, onde está a prova | crédito obrigatório, risco baixo |
| `proprio` | material gravado ou gerado pela equipe | obrigatória quando ele veio de fora do disco (fonte que não é `local`, ou há `pagina_url`): por que o que está publicado ali é da casa (canal próprio, arquivo da equipe) | sem crédito, risco baixo. **Recusado** junto de licença de terceiro que a política não aceita (NC, ND, «todos os direitos reservados», licença padrão do YouTube): se é mesmo da casa, registre sem essa licença |

```bash
python3 "$CRIABR_SKILLS"/video-broll/scripts/baixar.py --busca "…" --escolher 4 --base-legal citacao --nota "6 s para comentar a fala do pesquisador" --risco alto   # monta o PLANO com a exceção à vista; o download é baixar.py --plano CÓDIGO --confirmar
python3 "$CRIABR_SKILLS"/video-broll/scripts/registro.py adicionar --de-arquivo "bruto/drone.mp4" --base-legal proprio --autor "Canal"
```

A exceção é **decisão do usuário**, nunca sua: explique o risco, registre a nota com as palavras dele. `broll/creditos.md` lista toda exceção — e todo `proprio` que veio de fora do disco — na seção "Atenção antes de publicar", e a skill video-publicacao avisa quando um item sem uso comercial entra numa peça.

Sobre a citação no Brasil: a Lei 9.610/1998, art. 46, diz que não constitui ofensa aos direitos autorais "a citação em livros, jornais, revistas ou qualquer outro meio de comunicação, de passagens de qualquer obra, para fins de estudo, crítica ou polêmica, na medida justificada para o fim a atingir, indicando-se o nome do autor e a origem da obra" (inciso III) e "a reprodução, em quaisquer obras, de pequenos trechos de obras preexistentes […] sempre que a reprodução em si não seja o objetivo principal da obra nova e que não prejudique a exploração normal da obra reproduzida" (inciso VIII) — texto em https://www.planalto.gov.br/ccivil_03/leis/l9610.htm, lido em 2026-10-07. Daí as regras da casa para citação: trecho curto, com comentário, **nome do autor e origem na tela**, e a cor do original intacta (`tratar.py` faz isso sozinho). As plataformas aplicam as regras delas (Content ID, remoção) independentemente da lei: citação é sempre risco médio ou alto.

## Como o crédito é escrito

A Creative Commons pede: autor, aviso de licença com link, link para a obra quando razoável e indicação de que houve alteração; o título é recomendado. A forma é livre, "de qualquer maneira razoável" para o meio — num vídeo, a descrição serve. O registro monta o texto (`atribuicao`) e a skill video-publicacao exige que ele apareça **literalmente** na descrição quando `exige_atribuicao` é verdadeiro.

| caso | texto gerado (`atribuicao`) | crédito curto para a tela (`credito_tela`) |
|---|---|---|
| CC BY / BY-SA | `«Título», de Autor — CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0), via Wikimedia Commons: <página> (adaptado: recorte e cor)` | `Autor · CC BY-SA 3.0` |
| NASA | `«Título» — NASA: <página>` | `NASA` |
| Pexels / Pixabay | `Vídeo de Autor no Pexels: <página>` (cortesia) | `Autor / Pexels` |
| CC0 / domínio público | `«Título», de Autor — CC0 1.0, via Internet Archive: <página>` (cortesia) | `Autor` |
| citação | `Trecho de «Título», de Autor, usado como citação: <página>` | `Autor · YouTube` |
| autorização | `«Título», de Autor, usado com autorização: <página>` | `Autor` |

Para mudar um texto: `registro.py atualizar B003 atribuicao="…"`. Mudou autor, título, licença ou página? O texto é refeito sozinho.

`broll/creditos.md` é regravado a cada mudança no registro: a seção "Para a descrição" traz só o que exige crédito e está marcado em `usado_em`; "Cortesia", o que não exige; "Atenção antes de publicar", exceções, material declarado próprio que veio de fora, risco médio/alto e itens sem uso comercial. O arquivo lista só o que está marcado em `usado_em`; o registro inteiro vai na tabela do fim.

## O que a licença não cobre

Vale para todas, inclusive CC0 e domínio público:

- **Pessoas identificáveis**: direito de imagem e privacidade são de quem aparece, não do fotógrafo. Evite rosto reconhecível em contexto negativo, médico, político ou publicitário.
- **Marcas, logotipos, obras de arte e telas de software** dentro do quadro continuam protegidos.
- **Licença errada na fonte**: Wikimedia e Internet Archive não garantem o que o usuário declarou; o Openverse diz que não verifica. Material com cara de TV, cinema, clipe ou agência de notícias marcado como "CC0" é quase sempre engano de quem subiu — não use.
- **Endosso**: nada de sugerir que a NASA, uma pessoa ou uma marca apoia o vídeo.
