# -*- coding: utf-8 -*-
"""Apoio comum das suítes: projetos de teste em pasta temporária com espaço e acento, e atalhos para o CLI e o motor.

Não é módulo de teste. Tudo o que é criado mora numa pasta temporária apagada no fim; VIDEO_OPS_HOME aponta para
dentro dela (a biblioteca de presets e as configurações reais do usuário não são tocadas)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SCRIPTS = AQUI.parent
SKILL = SCRIPTS.parent
CENAS = SKILL / "cenas"
KIT = SKILL.parent / "video-direcao-de-arte" / "kit"
sys.dont_write_bytecode = True
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(KIT))

# As cenas da biblioteca, por família. NOMES é a PASTA (toda cena em cenas/ entra em todos os testes, mesmo sem estar
# nas listas); as listas existem para os testes que conhecem o layout de uma família e para acusar cena sem família.
NOMES_MODELO = ["tokenizacao", "embeddings", "atencao", "proximo_token", "rede_neural", "treino", "janela_contexto", "difusao"]
NOMES_SISTEMA = ["rag", "agente", "fluxo", "comparativo", "linha_do_tempo", "terminal", "chat", "numero", "versus", "conceito", "lista"]
NOMES = sorted(a.stem for a in CENAS.glob("*.js") if not a.name.startswith("_"))
PYTHON = sys.executable


class Area:
    """Pasta temporária "vídeo de teste ção/" com projetos criados por `da init`."""

    def __init__(self):
        self.raiz = Path(tempfile.mkdtemp(prefix="animação explicativa "))
        os.environ["VIDEO_OPS_HOME"] = str(self.raiz / "home")
        self.projetos = {}

    def projeto(self, preset: str = "lab-ia") -> Path:
        if preset not in self.projetos:
            pasta = self.raiz / f"vídeo {preset} ção"
            r = subprocess.run([*(["sh"] if os.name == "nt" else []), str(KIT / "bin" / "da"), "init", str(pasta), "--nome", f"Teste {preset}", "--base", preset], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"da init falhou: {r.stderr}")
            self.projetos[preset] = pasta
        return self.projetos[preset]

    def limpar(self):
        shutil.rmtree(self.raiz, ignore_errors=True)


def sb(projeto, *args, entrada=None):
    """Roda o CLI storyboard.py dentro do projeto. → CompletedProcess (texto)."""
    return subprocess.run([PYTHON, "-B", str(SCRIPTS / "storyboard.py"), *[str(a) for a in args]], cwd=str(projeto) if projeto else None,
                          capture_output=True, text=True, input=entrada, timeout=600)


def ler_storyboard(projeto) -> dict:
    return json.loads((Path(projeto) / "roteiro" / "storyboard.json").read_text(encoding="utf-8"))


def palavras_de(texto: str, t0: float = 1.0, passo: float = 0.4) -> list:
    """Transcrição sintética no formato da casa: uma palavra a cada `passo` segundos."""
    return [{"a": round(t0 + i * passo, 2), "b": round(t0 + i * passo + passo * 0.8, 2), "w": w, "p": 0.99} for i, w in enumerate(texto.split())]
