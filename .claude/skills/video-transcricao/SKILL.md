---
name: video-transcricao
description: Transcreve vídeo ou áudio palavra a palavra (faster-whisper local, GPU se houver) e grava transcricao/<nome>.palavras.json no formato [{"a","b","w","p"}] que as skills video-legendas e video-cortes-verticais exigem como insumo. Use quando o usuário pedir "transcreve esse vídeo", quando for legendar ou cortar e ainda não existir transcricao/<nome>.palavras.json, ou quando a legenda estiver fora de sincronia e for preciso refazer a transcrição.
---

# Transcrição palavra a palavra

Skill local (não veio da crIAbr): cobre a `video-transcricao` que as outras skills citam.

Rode a partir da pasta do projeto de vídeo, transcrevendo **o arquivo que será legendado ou cortado** (os tempos têm de ser do mesmo arquivo):

```bash
python "$CRIABR_SKILLS/video-transcricao/scripts/transcrever.py" render/final.mp4 --nome final
```

- Saída: `transcricao/final.palavras.json` (`a`/`b` em segundos, `w` texto, `p` confiança 0–1).
- Padrão: modelo `large-v3-turbo`, português, CPU. `--idioma en`, `--modelo Systran/faster-whisper-small` (mais rápido) e `--gpu` (só depois de instalar as DLLs CUDA 12 / cuBLAS) mudam isso.
- Palavras com `p < 0,60` são as que a video-legendas vai pedir para revisar: ouça o trecho antes de aceitar.
- Se a legenda acender errado no começo de frases, refaça a transcrição cortando o silêncio inicial do arquivo.
