# Licenças das fontes do kit

Todas as fontes em `kit/fontes/` são distribuídas sob a **SIL Open Font License 1.1** (OFL), que permite usar, copiar e
redistribuir os arquivos — inclusive embutidos num projeto ou num preset — desde que o aviso de direitos autorais e o
texto da licença acompanhem cada cópia. Por isso esta pasta viaja junto: `da init` copia para `<projeto>/da/fontes/LICENCAS/`
a licença de cada fonte que copia, e `da salvar-preset` faz o mesmo na biblioteca pessoal.

Conferido em 2026-10-06, arquivo por arquivo, na tabela `name` de cada fonte: o aviso de direitos (nameID 0), a
declaração de licença (nameID 13, "This Font Software is licensed under the SIL Open Font License, Version 1.1") e a URL
da licença (nameID 14). O cabeçalho de cada `OFL-<Família>.txt` é o aviso lido do próprio arquivo de fonte; o corpo é o
texto padrão da OFL 1.1 (sha256 `f05e84c3000faf09…`, o mesmo em 10 arquivos `OFL.txt` de outras famílias OFL
encontrados nesta máquina).

| arquivo | família (nameID 1) | versão (nameID 5) | direitos autorais (nameID 0) | licença |
|---|---|---|---|---|
| `ArchivoSemiExpanded-Black.ttf` | Archivo SemiExpanded Black | Version 2.001 | Copyright 2020 The Archivo Project Authors (https://github.com/Omnibus-Type/Archivo) | `OFL-ArchivoSemiExpanded.txt` |
| `BebasNeue-Regular.ttf` | Bebas Neue | Version 2.000 | Copyright 2019 The Bebas Neue Project Authors (https://github.com/dharmatype/Bebas-Neue) | `OFL-BebasNeue.txt` |
| `FiraCode-Variable.ttf` | Fira Code Light | Version 5.002 | Copyright 2014-2020 The Fira Code Project Authors (https://github.com/tonsky/FiraCode) | `OFL-FiraCode.txt` |
| `IBMPlexMono-Bold.ttf` | IBM Plex Mono | Version 2.3 | Copyright 2017 IBM Corp. All rights reserved. | `OFL-IBMPlexMono.txt` |
| `IBMPlexMono-Medium.ttf` | IBM Plex Mono Medium | Version 2.3 | Copyright 2017 IBM Corp. All rights reserved. | `OFL-IBMPlexMono.txt` |
| `IBMPlexMono-Regular.ttf` | IBM Plex Mono | Version 2.3 | Copyright 2017 IBM Corp. All rights reserved. | `OFL-IBMPlexMono.txt` |
| `IBMPlexMono-SemiBold.ttf` | IBM Plex Mono SemiBold | Version 2.3 | Copyright 2017 IBM Corp. All rights reserved. | `OFL-IBMPlexMono.txt` |
| `Montserrat-Variable.ttf` | Montserrat Thin | Version 9.000 | Copyright 2011 The Montserrat Project Authors (https://github.com/JulietaUla/Montserrat) | `OFL-Montserrat.txt` |
| `Roboto-Variable.ttf` | Roboto | Version 3.009; 2024 | Copyright 2011 The Roboto Project Authors (https://github.com/googlefonts/roboto-classic) | `OFL-Roboto.txt` |
| `Urbanist-Black.ttf` | Urbanist Black | Version 1.303 | Copyright 2021 The Urbanist Project Authors (https://github.com/coreyhu/Urbanist) | `OFL-Urbanist.txt` |
| `Urbanist-ExtraBold.ttf` | Urbanist ExtraBold | Version 1.303 | Copyright 2021 The Urbanist Project Authors (https://github.com/coreyhu/Urbanist) | `OFL-Urbanist.txt` |
| `Urbanist-Medium.ttf` | Urbanist Medium | Version 1.303 | Copyright 2021 The Urbanist Project Authors (https://github.com/coreyhu/Urbanist) | `OFL-Urbanist.txt` |
| `Urbanist-SemiBold.ttf` | Urbanist SemiBold | Version 1.303 | Copyright 2021 The Urbanist Project Authors (https://github.com/coreyhu/Urbanist) | `OFL-Urbanist.txt` |

Regras para quem acrescenta fonte:

- Fonte nova no kit ou num projeto: ponha a licença dela em `fontes/LICENCAS/OFL-<Prefixo>.txt`, onde `<Prefixo>` é o
  nome do arquivo de fonte até o primeiro hífen (`Urbanist-Black.ttf` → `OFL-Urbanist.txt`). É por esse nome que o
  `init` e o `salvar-preset` acham a licença que acompanha cada fonte.
- A OFL não permite vender a fonte sozinha nem usar o nome reservado em versão modificada; renomear o **arquivo** (como
  `Montserrat-Variable.ttf`) não é modificar a fonte.
- Fonte comercial (Didot, AmsiPro e qualquer outra sem licença de redistribuição) nunca entra aqui nem em `da/fontes/`:
  só é referenciada pelo caminho absoluto do sistema.
