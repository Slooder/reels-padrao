#!/usr/bin/env bash
# Imprime o caminho de um Node >= 20 (o Playwright exige). Procura no PATH, no nvm e no Homebrew.
# uso: N=$(bash scripts/node.sh) && $N render.mjs ...
ok(){ [ -x "$1" ] && v=$("$1" -v 2>/dev/null | sed 's/^v//;s/\..*//') && [ -n "$v" ] && [ "$v" -ge 20 ]; }
for c in "$(command -v node 2>/dev/null)" /opt/homebrew/bin/node /usr/local/bin/node $(ls -d "$HOME"/.nvm/versions/node/v2[0-9]*/bin/node 2>/dev/null | sort -rV); do
  if ok "$c"; then echo "$c"; exit 0; fi
done
echo "nenhum Node >= 20 encontrado (instale: brew install node, ou nvm install 22)" >&2; exit 1
