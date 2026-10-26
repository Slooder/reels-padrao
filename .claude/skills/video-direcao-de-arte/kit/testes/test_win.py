"""Checagem da adaptação Windows (_win.py + trava.py). Local, não vem da crIAbr.
Rodar da pasta kit:  python -m unittest testes.test_win"""
import os
import subprocess
import sys
import tempfile
import time
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KIT)
import psutil  # noqa: E402
import trava  # noqa: E402

PY = sys.executable


@unittest.skipUnless(os.name == "nt", "só Windows")
class TesteWin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        trava._tabela()             # a 1ª listagem do psutil leva ~3 s; as seguintes ~0,3 s

    def setUp(self):
        self.arq = os.path.join(tempfile.mkdtemp(), "trava.lock")
        os.environ[trava.VAR_ARQUIVO] = self.arq
        os.environ.pop(trava.VAR_DONO, None)

    def segurar(self, segundos):
        """Outro processo segura a trava por `segundos` com rótulo 'outro'."""
        codigo = (f"import sys,time; sys.path.insert(0, {KIT!r}); import trava\n"
                  f"with trava.Trava(rotulo='outro', arquivo={self.arq!r}): print('ok', flush=True); time.sleep({segundos})")
        p = subprocess.Popen([PY, "-c", codigo], stdout=subprocess.PIPE, text=True)
        self.assertEqual(p.stdout.readline().strip(), "ok")
        return p

    def test_exclusao_e_registro_legivel(self):
        p = self.segurar(3)
        st = trava.estado(self.arq)
        self.assertFalse(st["livre"])
        self.assertEqual(st["dono"]["rotulo"], "outro")          # registro lido apesar da trava
        with self.assertRaises(trava.TempoEsgotado):
            trava.Trava(espera_max=0.5, silencioso=True, arquivo=self.arq).adquirir()
        p.wait()
        self.assertTrue(trava.estado(self.arq)["livre"])

    def test_dono_morto_libera(self):
        p = self.segurar(60)
        p.kill()
        p.wait()
        with trava.Trava(espera_max=5, silencioso=True, arquivo=self.arq):
            self.assertFalse(trava.estado(self.arq)["livre"])

    def test_prazo_mata_a_arvore(self):
        neto = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); time.sleep(60)"
        antes = time.monotonic()
        r = trava.rodar([PY, "-c", neto], prazo=2, silencioso=True)
        self.assertEqual(r.codigo, trava.SAIDA_VIGIA)
        self.assertLess(time.monotonic() - antes, 15)
        time.sleep(0.5)
        vivos = [p for p in psutil.process_iter(["cmdline"]) if "time.sleep(60)" in " ".join(p.info["cmdline"] or [])]
        self.assertEqual(vivos, [])

    def test_rodar_captura_e_codigo(self):
        r = trava.rodar([PY, "-c", "print('oi'); raise SystemExit(3)"], capturar=True, silencioso=True)
        self.assertEqual((r.codigo, r.stdout.strip()), (3, "oi"))

    def test_vivo_nao_mata(self):
        p = subprocess.Popen([PY, "-c", "import time; time.sleep(5)"])
        self.assertTrue(trava._vivo(p.pid))
        time.sleep(0.3)
        self.assertIsNone(p.poll())                               # os.kill(pid, 0) mataria/interromperia no Windows
        p.kill()
        p.wait()


if __name__ == "__main__":
    unittest.main()
