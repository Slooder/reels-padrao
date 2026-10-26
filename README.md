# Padrão de Reels gravados com o Claude Code

Processo completo para editar Reels/TikTok/Shorts **gravados** (uma pessoa falando para a câmera, 9:16) com o Claude Code:
decupagem natural, legenda limpa, inserts curtos com animação de entrada e saída, fechamento com frases no preto.
Nasceu de um vídeo editado do zero e aprovado parte por parte.

## O que tem aqui

| pasta | o quê |
|---|---|
| `padrao/` | **o padrão**: processo, decupagem, legenda, inserts, final, som e entrega, e a lista de correções que já foram feitas (leia o `README.md` de lá primeiro) |
| `.claude/skills/` | as skills usadas (transcrição, legendas, direção de arte, cortes verticais, b-roll etc.) |
| `projeto-modelo/scripts/` | os scripts Python do vídeo-modelo (decupagem, montagem com zoom no rosto, legenda, render, conferência da legenda) |
| `projeto-modelo/remotion/` | a composição Remotion (base + inserts + legenda + final) |
| `projeto-modelo/da/` | a direção de arte (fontes e tokens da legenda) |

Os vídeos e imagens do projeto original não estão aqui; os scripts e a composição servem de molde (troque caminhos, tempos e textos).

## Como usar

1. Instale: [Claude Code](https://claude.com/claude-code), Python 3.11+, Node 20+, ffmpeg no PATH. No projeto Remotion: `npm i remotion @remotion/cli`.
   Python: `pip install faster-whisper opencv-python numpy pillow`.
2. Copie `.claude/skills/` para a pasta onde vai editar (ou para `~/.claude/skills/`) e defina a variável `CRIABR_SKILLS` apontando para ela.
3. Crie uma pasta do vídeo com `bruto/` (as gravações), abra o Claude Code nela e peça:
   > "Edite este Reels seguindo o padrão em `padrao/README.md`, parte por parte, me mandando prévia de cada etapa."
4. O Claude segue `padrao/01-processo.md`: transcreve, decupa, monta a base, faz a legenda, os inserts e o final, com uma prévia aprovada por você a cada etapa.

## Aviso

As skills em `.claude/skills/` vêm do plano Pro do [crIAbr](https://www.criabr.com/) e foram adaptadas para Windows. Uso pessoal entre amigos.
