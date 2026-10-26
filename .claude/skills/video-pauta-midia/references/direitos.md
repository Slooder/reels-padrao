# Direitos: o que pode entrar no vídeo, com que base e com que risco

**Isto não é parecer jurídico.** É o resumo de três fontes oficiais lidas em **12/10/2026** e a regra da casa que sai delas. A decisão de usar um material é sempre do usuário; a skill registra a decisão, a base legal e o risco em `broll/licencas.json`. Reveja as fontes a cada seis meses ou quando o YouTube avisar mudança de termos.

## 1. As três fontes

**Termos de Serviço do YouTube (versão Brasil, "em vigor a partir de 5 de janeiro de 2022")** — <https://www.youtube.com/static?template=terms&hl=pt-BR&gl=BR>, seção "Permissões e restrições", primeiro item. Os Termos proíbem acessar, reproduzir, fazer download, distribuir ou modificar qualquer Conteúdo do serviço, com duas exceções: quando o próprio Serviço autoriza de forma expressa, ou com permissão prévia por escrito do YouTube e, se for o caso, dos detentores dos direitos. A licença que quem envia um vídeo dá aos outros usuários vale para acessar o conteúdo por meio do Serviço, não para usá-lo fora dele.
O que isso quer dizer aqui: baixar com o yt-dlp não é um recurso oferecido pelo YouTube. Ter base para **usar** um trecho (licença aberta, citação) não transforma o **download** em algo previsto nos Termos. O risco é contratual, recai sobre a conta e o canal do usuário, e é ele quem decide. Por isso o `youtube.py` só mostra o plano e exige `--confirmar`.

**Ajuda do YouTube, "Tipos de licença no YouTube"** — <https://support.google.com/youtube/answer/2797468?hl=pt-BR>. Há duas licenças: a padrão do YouTube e a Creative Commons Atribuição (CC BY; o link da página leva à versão 4.0). Quem marca o vídeo com CC BY permite que outros criadores reutilizem a obra nos termos dessa licença. A marcação só cabe quando todo o conteúdo do vídeo é compatível (criado por quem envia, já licenciado em CC BY ou em domínio público) e não pode ser aplicada a vídeo com reivindicação do Content ID. Quem reutiliza precisa dar o crédito (atribuição) no vídeo e na descrição.
O que isso quer dizer aqui: a licença aparece nos metadados lidos pelo yt-dlp (campo `license`; hoje, no vídeo `aqz-KE-bpKQ` do canal Blender, o valor era "Creative Commons Attribution license (reuse allowed)"; vídeo de licença padrão vem sem o campo). A marcação é uma **declaração de quem enviou**: reenvio de TV, de filme ou de outro canal marcado como CC não vale nada. Confira se o canal é o titular.

**Lei 9.610/98 (direitos autorais), art. 46** — <https://www.planalto.gov.br/ccivil_03/leis/l9610.htm>. O inciso III diz que não é ofensa aos direitos autorais:

> "a citação em livros, jornais, revistas ou qualquer outro meio de comunicação, de passagens de qualquer obra, para fins de estudo, crítica ou polêmica"

desde que na medida justificada para o fim a atingir e com o nome do autor e a origem da obra. O inciso VIII admite pequenos trechos de obra preexistente dentro de uma obra nova quando a reprodução não é o objetivo principal da obra nova, não prejudica a exploração normal da obra reproduzida e não causa prejuízo injustificado ao autor.
O que isso quer dizer aqui: citação é **passagem**, **comentada** e **creditada**. Trecho usado só como cobertura bonita, sem que o vídeo fale dele, não é citação. A lei não fixa número de segundos; os tetos abaixo são regra da casa, não da lei.

## 2. Regra da casa, em ordem de preferência

1. **Material próprio** (gravado pela equipe, canal da casa): `--base-legal proprio --nota "por que é nosso"`. Risco baixo.
2. **Material autorizado** pelo titular: `--base-legal autorizacao --nota "quem autorizou, quando e onde está a prova"`. Risco baixo, se a prova existir.
3. **Licença aberta** (CC BY, CC BY-SA, CC0, domínio público): `licenca` é o padrão quando os metadados ou a página de origem trazem a licença. Crédito obrigatório na descrição. Licenças com "NC" ou "ND" são recusadas pela política do registro (o vídeo é monetizado e editado).
4. **Material protegido, só como citação**: `--base-legal citacao --nota "o que é citado e por quê"`. Trecho curto, comentado na fala, com crédito "Reprodução: …" na tela e a cor do original preservada. Risco médio; alto quando é música, quando passa de 30 s ou de 20% do vídeo de origem.

Nunca, em nenhuma base: o vídeo inteiro por padrão (o `youtube.py` não tem esse modo); trecho sem crédito; material sem registro.

## 3. O que os scripts aplicam

| regra | onde |
|---|---|
| `--t0` e `--t1` obrigatórios; teto de 30 s por trecho; `--teto` sobe até 60 s em citação e 600 s nas outras bases | `youtube.py baixar` |
| altura máxima 1080 (padrão 720) | `youtube.py baixar` |
| licença padrão do YouTube só entra com `--base-legal` declarada e `--nota` | `youtube.py baixar` |
| imagem sem licença informada só entra com `--base-legal` e `--nota`; autor obrigatório | `imagens.py baixar` |
| item da pauta precisa estar `aprovado` para baixar com `--pedido` | os dois |
| citação: crédito na tela "Reprodução: <canal> / YouTube" ou "Reprodução: <veículo>"; moldura e cor original | registro + `tratar.py` da video-broll |
| lista "Atenção antes de publicar" com tudo que não é licença aberta | `broll/creditos.md` |

## 4. Na dúvida

- Música comercial, clipe, transmissão esportiva, trailer e trecho de filme são os alvos mais comuns do Content ID: até trecho curto recebe reivindicação. Avise o usuário antes de aprovar.
- Rosto de pessoa comum, criança e conteúdo de terceiros em print (nome, foto de perfil) envolvem direito de imagem e privacidade, que este resumo não cobre.
- Sem certeza de quem é o titular, trate como protegido.
- Caso sensível (campanha eleitoral, marca, pessoa em situação vexatória): a recomendação é consultar um advogado antes de publicar.
