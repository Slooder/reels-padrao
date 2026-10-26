#!/usr/bin/env bash
# Cria (ou completa) um projeto "palavra em recortes" pronto pra renderizar.
# uso: bash <skill>/scripts/setup.sh <pasta-do-projeto>
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:?uso: setup.sh <pasta-do-projeto>}"
for c in ffmpeg python3; do command -v "$c" >/dev/null || { echo "falta: $c (no Mac: brew install ffmpeg python)"; exit 1; }; done
NODE="$(bash "$SKILL/scripts/node.sh")"; export PATH="$(dirname "$NODE"):$PATH"
if [ ! -f "$DEST/render.mjs" ]; then mkdir -p "$DEST" && cp -R "$SKILL/assets/projeto/." "$DEST/"; echo "projeto criado em $DEST"; fi
cd "$DEST"; mkdir -p tools previews out audio
[ -d node_modules/gsap ] && [ -d node_modules/playwright ] || npm install --no-audit --no-fund --loglevel=error
npx --yes playwright install chromium >/dev/null 2>&1 || true
if [ ! -x audio/.venv/bin/python ]; then python3 -m venv audio/.venv && audio/.venv/bin/pip install -q --disable-pip-version-check numpy scipy pillow; fi
cp "$SKILL/scripts/node.sh" "$SKILL/scripts/papeis.py" "$SKILL/scripts/analisar.py" tools/
[ -f lib/papeis/creme.jpg ] || audio/.venv/bin/python tools/papeis.py
echo "pronto: cd \"$DEST\" && N=\$(bash tools/node.sh) && \$N render.mjs exemplo --preview=12"
