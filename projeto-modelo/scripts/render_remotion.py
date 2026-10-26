"""render_remotion.py — renderiza a composição do JP no Remotion do Studio, do jeito do tools/render_hibrido.py:
bundle com pasta pública vazia + junção bundle/public → projetos/ (sem copiar os GB de projetos/), trechos no SSD.
uso: python render_remotion.py <Composicao> <saida.mp4> [--frames=A-B] [--reusar-bundle] [outras opções do remotion render]
prévia rápida: --scale=0.5 --crf=30 --x264-preset=veryfast (as opções repetidas valem sobre as de baixo)"""
import os
import shutil
import subprocess
import sys

RAIZ = r"D:\STUDIO\studio"
TMP = r"C:\STUDIO-RENDER-TMP\104"
comp, saida = [a for a in sys.argv[1:] if not a.startswith("--")][:2]
extra = [a for a in sys.argv[1:] if a.startswith("--") and a != "--reusar-bundle"]
bundle = os.path.join(TMP, "bundle")
pub = os.path.join(bundle, "public")
if not ("--reusar-bundle" in sys.argv and os.path.isdir(bundle)):
    shutil.rmtree(bundle, ignore_errors=True)        # rmtree remove só a junção, não segue para projetos/
    vazio = os.path.join(TMP, "vazio")
    os.makedirs(vazio, exist_ok=True)
    subprocess.run(["npx", "remotion", "bundle", "src/index.ts", "--out-dir", bundle, "--public-dir", vazio, "--log=error"],
                   cwd=RAIZ, shell=True, check=True)
    if os.path.isdir(pub):
        os.rmdir(pub)
# a junção bundle/public → projetos/ só existe durante o render: um robocopy /MOVE de outra sessão varreu C:\STUDIO-RENDER-TMP
# em 23/10 (03:17), seguiu as junções e levou projetos/ inteira para o D:. Sem junção parada, nada mais segue para lá.
if not os.path.isdir(os.path.join(pub, "104. JP")):
    subprocess.run(["cmd", "/c", "mklink", "/J", pub, os.path.join(RAIZ, "projetos")], capture_output=True, check=True)
assert os.path.isdir(os.path.join(pub, "104. JP")), "falhou a junção bundle/public → projetos"
padrao = {"--codec": "h264", "--crf": "16", "--x264-preset": "medium", "--concurrency": "5", "--gl": "angle", "--log": "error"}
padrao.update(a.split("=", 1) for a in extra if "=" in a)
try:
    subprocess.run(["npx", "remotion", "render", bundle, comp, saida, *(f"{k}={v}" for k, v in padrao.items())],
                   cwd=RAIZ, shell=True, check=True)
finally:
    subprocess.run(["cmd", "/c", "rmdir", pub], capture_output=True)    # rmdir numa junção apaga só o atalho
print("ok:", saida)
