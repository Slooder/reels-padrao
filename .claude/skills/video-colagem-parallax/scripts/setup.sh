#!/usr/bin/env bash
# Cria (ou completa) um projeto de colagem + parallax pronto pra renderizar.
# uso: bash <skill>/scripts/setup.sh <pasta-do-projeto>
set -euo pipefail
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${1:?uso: setup.sh <pasta-do-projeto>}"

for c in node npm ffmpeg python3; do command -v "$c" >/dev/null || { echo "falta: $c (instale antes; no Mac: brew install node ffmpeg python)"; exit 1; }; done

if [ ! -f "$DEST/render.mjs" ]; then
  mkdir -p "$DEST" && cp -R "$SKILL/assets/projeto/." "$DEST/"
  echo "projeto criado em $DEST"
fi
cd "$DEST"

[ -d node_modules/gsap ] && [ -d node_modules/playwright ] || npm install --no-audit --no-fund --loglevel=error
npx --yes playwright install chromium >/dev/null

if [ ! -x audio/.venv/bin/python ]; then
  python3 -m venv audio/.venv
  audio/.venv/bin/pip install -q --disable-pip-version-check numpy scipy pillow
fi

mkdir -p tools previews out
cp "$SKILL/scripts/recortar.py" "$SKILL/scripts/commons.py" tools/
if [ "$(uname)" = "Darwin" ]; then
  if [ ! -x tools/cutout ]; then
    command -v swiftc >/dev/null && swiftc -O "$SKILL/scripts/cutout.swift" -o tools/cutout \
      || echo "aviso: sem swiftc (xcode-select --install) — recorte automático indisponível"
  fi
else
  echo "aviso: recorte automático usa o Vision do macOS; em outro sistema recorte com rembg ou à mão (PNG com alfa)"
fi
echo "pronto: cd \"$DEST\" && node render.mjs exemplo --preview=12"
