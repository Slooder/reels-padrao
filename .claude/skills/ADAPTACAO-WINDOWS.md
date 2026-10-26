# Adaptação das skills crIAbr para Windows (local)

As skills de vídeo da crIAbr foram feitas para macOS/Linux. Estas mudanças locais as fazem rodar direto no
Windows, sem WSL. **Ao baixar uma versão nova do site, reaplique** (os .zip originais estão em `criabr-downloads/`).

## Dependências instaladas
- `psutil` e `opencv-python` (`python -m pip install psutil opencv-python`).
- Já existiam: Python 3.14 (Pillow, numpy, faster-whisper), Node 24, ffmpeg 9, Chromium headless shell do Playwright.

## Variáveis (`.claude/settings.json`)
`CRIABR_SKILLS` (pasta das skills), `VIDEO_OPS_PYTHON`, `VIDEO_OPS_CHROME`, `PYTHONUTF8=1`.

## Arquivos novos
| arquivo | o que faz |
|---|---|
| `video-direcao-de-arte/kit/_win.py` | fila (`flock`) com `msvcrt`, lista de processos com `psutil` (no lugar do `ps`), `killpg` = mata a árvore, `pwrite` |
| `video-direcao-de-arte/kit/testes/test_win.py` | checagem da fila e do controle de processos no Windows |
| `video-cortes-verticais/scripts/rostos_win.py` + `face_detection_yunet_2023mar.onnx` | detecção de rosto com OpenCV YuNet no lugar do Vision do macOS (mesmo JSON) |
| `video-transcricao/` | skill de transcrição (faster-whisper) que a crIAbr cita mas não publica |

## Arquivos alterados
| arquivo | mudança |
|---|---|
| `kit/trava.py` | importa `_win` quando não há `fcntl`; fila em `%TEMP%`; `_vivo` e `_tabela` pelo `_win` |
| `kit/motor/comum.mjs` | acha `.exe` no PATH, Chromium em `%LOCALAPPDATA%\ms-playwright`, fila em `%TEMP%`; `KIT_FINAL` |
| `storyboard.py`, `registro.py`, `roteiro.py` | `import fcntl` com recuo para o `_win` |
| `cortes-verticais/scripts/enquadrar.py` | fora do macOS chama `rostos_win.py` |
| todos os `.md` e mensagens dos `.py` | `~/.claude/skills/` → `"$CRIABR_SKILLS"/`; `/opt/homebrew/bin/python3` → `python` |
| `kit/da.py`, `da_ext_conferencia.py`, `storyboard.py`, `comum.mjs` | constantes de caminho exibido (`KIT_FINAL` etc.) |

## Limites conhecidos
- A 1ª listagem de processos de cada execução leva ~3 s (psutil); as seguintes ~0,3 s.
- Sem sinais de Unix: cancelar um comando mata a árvore na hora (sem a carência de 3 s do SIGTERM).
- Os testes originais `test_trava.py` usam `pkill`/`sh` e não rodam no Windows; use `test_win.py`.
- `test_da.py`: 2 falhas só de exibição (o Windows mostra `da\build` com barra invertida).
- Transcrição na CPU por padrão (a GPU precisa das DLLs CUDA 12/cuBLAS; depois use `--gpu`).
