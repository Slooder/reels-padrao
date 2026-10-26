"""Suítes da skill video-broll. Rode de scripts/:  python3 -m unittest   (test_rede é pulado sem conexão)."""
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
for _p in (Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]):
    shutil.rmtree(_p / "__pycache__", ignore_errors=True)
