#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testes de robustez da trava (trava.py): nenhum caminho pode segurar a trava para sempre.

Rodar a partir do kit:  python3 -m unittest testes.test_trava -v
Tudo usa um arquivo de trava PRIVADO (VIDEO_OPS_TRAVA_ARQUIVO numa pasta temporária com espaço e acento):
a trava global da máquina nunca é tocada. Os processos são minúsculos (sleep, cat) e todo prazo é curto;
o tearDown mata o que tiver sobrado.
"""
from __future__ import annotations

import contextlib
import io
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))

import trava  # noqa: E402

PY = sys.executable
TRAVA = str(KIT / "trava.py")


def esperar(condicao, prazo=8.0, passo=0.05) -> bool:
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(passo)
    return bool(condicao())


class TesteTravaRobusta(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="trava teste é ")).resolve()
        self._env = {k: os.environ.get(k) for k in (trava.VAR_ARQUIVO, trava.VAR_DONO, trava.VAR_INATIVIDADE)}
        os.environ[trava.VAR_ARQUIVO] = str(self.tmp / "trava de teste.lock")     # nunca a trava real
        os.environ.pop(trava.VAR_DONO, None)
        os.environ.pop(trava.VAR_INATIVIDADE, None)
        self.marca = f"marca{os.getpid()}x{int(time.time() * 1000) % 100000}"      # aparece na linha de comando dos filhos
        self.processos: list[subprocess.Popen] = []

    def tearDown(self):
        for p in self.processos:
            if p.poll() is None:
                p.kill()
            with contextlib.suppress(Exception):
                p.wait(timeout=5)
            for fluxo in (p.stdout, p.stderr):
                if fluxo is not None:
                    with contextlib.suppress(Exception):
                        fluxo.close()
        subprocess.run(["pkill", "-KILL", "-f", self.marca], capture_output=True)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- ajudantes ----------------------------------------------------------
    def vivos(self) -> int:
        """Processos cuja linha de comando tem a marca deste teste (fora o próprio pgrep)."""
        r = subprocess.run(["pgrep", "-f", self.marca], capture_output=True, text=True)
        return len([l for l in r.stdout.split() if l.strip() and int(l) != os.getpid()])

    def dorminhoco(self, seg=60) -> list[str]:
        """Comando que dorme e carrega a marca na linha de comando."""
        return [PY, "-c", f"import time; time.sleep({seg})  # {self.marca}"]

    def lancar(self, *args, **kw) -> subprocess.Popen:
        p = subprocess.Popen([PY, TRAVA, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)
        self.processos.append(p)
        return p

    # -- rodar: entrada, saída e códigos ---------------------------------------
    def test_rodar_captura_saida_e_fecha_o_stdin_por_padrao(self):
        r = trava.rodar([PY, "-c", "import sys; print('saída'); print('erro', file=sys.stderr); sys.exit(3)"], capturar=True)
        self.assertEqual((r.codigo, r.returncode, r.motivo), (3, 3, None))
        self.assertEqual(r.stdout.strip(), "saída")
        self.assertEqual(r.stderr.strip(), "erro")
        # sem `entrada`, o filho lê /dev/null: um `cat` termina na hora em vez de esperar um stdin que ninguém fecha
        t0 = time.monotonic()
        r = trava.rodar(["cat"], capturar=True, inatividade=10)
        self.assertEqual((r.codigo, r.stdout), (0, ""))
        self.assertLess(time.monotonic() - t0, 3)
        self.assertTrue(trava.estado()["livre"])

    def test_rodar_entrada_em_bytes_e_por_iteravel(self):
        r = trava.rodar(["cat"], capturar=True, entrada="ação é\n".encode(), texto=False)
        self.assertEqual(r.stdout, "ação é\n".encode())
        pedacos = (f"quadro {i}\n".encode() for i in range(200))
        r = trava.rodar(["cat"], capturar=True, entrada=pedacos)
        self.assertEqual(r.stdout.count("\n"), 200)
        self.assertTrue(r.stdout.endswith("quadro 199\n"))

    def test_filho_que_sai_antes_de_ler_a_entrada_nao_trava(self):
        # 40 MB num pipe para um processo que sai sem ler: a escrita recebe EPIPE e tudo termina
        blocos = (b"x" * 1048576 for _ in range(40))
        t0 = time.monotonic()
        r = trava.rodar([PY, "-c", "import sys; sys.exit(9)"], capturar=True, entrada=blocos, inatividade=10)
        self.assertEqual(r.codigo, 9)
        self.assertLess(time.monotonic() - t0, 5)
        self.assertTrue(trava.estado()["livre"])

    def test_stderr_volumoso_nao_enche_o_pipe(self):
        codigo = "import sys\nfor i in range(3000): sys.stderr.write('e' * 1000 + '\\n')\nprint('fim')"
        r = trava.rodar([PY, "-c", codigo], capturar=True, inatividade=10)
        self.assertEqual((r.codigo, r.stdout.strip()), (0, "fim"))
        self.assertGreater(len(r.stderr), 2_000_000)

    def test_erro_de_quem_produz_a_entrada_mata_o_filho_e_sobe(self):
        def quadros():
            yield b"um\n"
            raise RuntimeError("o gerador de quadros falhou")

        with self.assertRaises(RuntimeError):
            trava.rodar(["cat"], capturar=True, entrada=quadros(), inatividade=10)
        self.assertTrue(trava.estado()["livre"])

    def test_env_explicito_ainda_leva_o_dono(self):
        # um `env=` montado ANTES de a trava existir não tem VIDEO_OPS_TRAVA: sem a correção o filho entrava na fila do próprio pai
        limpo = {k: v for k, v in os.environ.items() if k != trava.VAR_DONO}
        r = trava.rodar([PY, "-c", "import os; print(os.environ.get('VIDEO_OPS_TRAVA'))"], capturar=True, env=limpo)
        self.assertEqual(r.stdout.strip(), str(os.getpid()))

    # -- vigia de inatividade e prazo -----------------------------------------
    def test_inatividade_mata_e_libera_com_codigo_124(self):
        t0 = time.monotonic()
        r = trava.rodar(self.dorminhoco(60), inatividade=1.5, rotulo="dorme")
        dur = time.monotonic() - t0
        self.assertEqual((r.codigo, r.motivo), (trava.SAIDA_VIGIA, "inatividade"))
        self.assertLess(dur, 9)
        self.assertGreaterEqual(dur, 1.4)
        self.assertEqual(self.vivos(), 0)
        self.assertTrue(trava.estado()["livre"])
        self.assertIn("sem progresso", trava.descrever_vigia(r, "dorme"))

    def test_quem_trabalha_nao_e_morto_pelo_vigia(self):
        # 2,5 s de CPU contínua com limite de 1 s de inatividade: tem progresso, termina normalmente
        codigo = "import time\nt = time.monotonic()\nwhile time.monotonic() - t < 2.5: sum(range(20000))\nprint('ok')"
        r = trava.rodar([PY, "-c", codigo], capturar=True, inatividade=1.0)
        self.assertEqual((r.codigo, r.motivo, r.stdout.strip()), (0, None, "ok"))

    def test_arquivo_vigiado_crescendo_conta_como_progresso(self):
        alvo = self.tmp / "saída parcial.bin"
        codigo = ("import sys, time\n"
                  "for i in range(12):\n"
                  "    open(sys.argv[1], 'ab').write(b'x' * 10); time.sleep(0.25)\n")
        r = trava.rodar([PY, "-c", codigo, str(alvo)], inatividade=1.0, vigiar=[alvo])
        self.assertEqual((r.codigo, r.motivo), (0, None))
        self.assertEqual(alvo.stat().st_size, 120)

    def test_prazo_mata_mesmo_com_cpu(self):
        t0 = time.monotonic()
        r = trava.rodar([PY, "-c", f"while True: pass  # {self.marca}"], prazo=1.0)
        self.assertEqual((r.codigo, r.motivo), (trava.SAIDA_VIGIA, "prazo"))
        self.assertLess(time.monotonic() - t0, 8)
        self.assertEqual(self.vivos(), 0)

    def test_cli_inatividade(self):
        p = self.lancar("--inatividade", "1.2", "--rotulo", "cli dorme", "--", *self.dorminhoco(60))
        _, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, trava.SAIDA_VIGIA, err)
        self.assertIn("sem progresso", err)
        self.assertTrue(trava.estado()["livre"])

    # -- sinais: o grupo inteiro morre antes de a trava ser solta ----------------
    def test_sigterm_no_dono_mata_filhos_netos_e_quem_mudou_de_sessao(self):
        # filho: sh que lança dois dorminhocos e um terceiro em OUTRA sessão (como o Chromium do Playwright)
        outro = f"import os, time; os.setsid(); time.sleep(60)  # {self.marca}"
        sh = f'"{PY}" -c "import time; time.sleep(61)  # {self.marca}" & "{PY}" -c "{outro}" & wait'
        p = self.lancar("--rotulo", "árvore", "--", "sh", "-c", sh)
        self.assertTrue(esperar(lambda: self.vivos() >= 2), "os filhos não subiram")
        time.sleep(0.4)
        self.assertFalse(trava.estado()["livre"])
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=15)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertLess(time.monotonic() - t0, 8)
        self.assertTrue(esperar(lambda: self.vivos() == 0, 3), f"sobraram {self.vivos()} processo(s) depois do SIGTERM")
        self.assertTrue(trava.estado()["livre"])

    def test_with_trava_e_sigterm_viram_interrompido(self):
        # código de terceiros: `with Trava(): subprocess.run(...)`. O SIGTERM vira exceção, o run mata o filho, a trava é solta.
        codigo = (f"import sys, subprocess; sys.path.insert(0, {str(KIT)!r}); import trava\n"
                  "with trava.Trava(rotulo='terceiros'):\n"
                  f"    subprocess.run([sys.executable, '-c', 'import time; time.sleep(60)  # {self.marca}'])\n")
        p = subprocess.Popen([PY, "-c", codigo], stderr=subprocess.PIPE, text=True)
        self.processos.append(p)
        self.assertTrue(esperar(lambda: self.vivos() >= 1 and not trava.estado()["livre"]))
        time.sleep(0.3)
        p.send_signal(signal.SIGTERM)
        _, err = p.communicate(timeout=10)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM, err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(esperar(lambda: self.vivos() == 0, 3))
        self.assertTrue(trava.estado()["livre"])

    # -- dono morto: quem espera assume e limpa os órfãos -------------------------
    def test_dono_morto_por_sigkill_trava_assumida_e_orfaos_encerrados(self):
        sh = f'"{PY}" -c "import time; time.sleep(62)  # {self.marca}" & "{PY}" -c "import time; time.sleep(63)  # {self.marca}"'
        dono = self.lancar("--rotulo", "vai morrer", "--", "sh", "-c", sh)
        self.assertTrue(esperar(lambda: self.vivos() >= 2))
        time.sleep(0.4)
        dono.kill()                                               # SIGKILL: nenhum tratador roda
        dono.wait(timeout=5)
        self.assertGreaterEqual(self.vivos(), 2, "o teste precisa dos órfãos vivos para provar a limpeza")
        self.assertTrue(trava.estado()["livre"], "dono morto tem de deixar a trava livre para quem espera")
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            with trava.Trava(rotulo="herdeiro", espera_max=5) as t:
                self.assertGreaterEqual(t.orfaos_encerrados, 2)
                self.assertEqual(self.vivos(), 0, "quem assume a trava encerra os órfãos ANTES de trabalhar")
        self.assertIn("morreu sem liberar", erro.getvalue())

    def test_registro_de_dono_morto_nao_mata_processo_alheio(self):
        # registro velho apontando para um grupo que NÃO é dele (início diferente): ninguém é morto
        inocente = subprocess.Popen(self.dorminhoco(60), start_new_session=True)
        self.processos.append(inocente)
        time.sleep(0.3)
        reg = {"pid": 999999, "rotulo": "fantasma", "desde_epoch": time.time() - 3600,
               "grupos": [{"pgid": inocente.pid, "inicio": "Mon Jan  1 00:00:00 2001", "comando": "python"}]}
        Path(os.environ[trava.VAR_ARQUIVO]).write_text(__import__("json").dumps(reg), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            with trava.Trava(espera_max=5) as t:
                self.assertEqual(t.orfaos_encerrados, 0)
        self.assertIsNone(inocente.poll(), "um processo cujo início não bate com o registro não pode ser morto")

    # -- reentrância ---------------------------------------------------------------
    def test_reentrancia_por_linhagem_quando_a_variavel_se_perde(self):
        # o neto perde VIDEO_OPS_TRAVA (env -u): antes ficava na fila do próprio avô para sempre
        t0 = time.monotonic()
        p = self.lancar("--rotulo", "avô", "--", "env", "-u", trava.VAR_DONO, PY, TRAVA, "--rotulo", "neto", "--", "echo", "neto rodou")
        out, err = p.communicate(timeout=20)
        self.assertEqual(p.returncode, 0, err)
        self.assertIn("neto rodou", out)
        self.assertLess(time.monotonic() - t0, 10)

    # -- estado e liberação manual --------------------------------------------------
    def test_estado_mostra_ociosidade_e_liberar_ocioso_mata_o_dono_parado(self):
        dono = self.lancar("--rotulo", "parado", "--", *self.dorminhoco(120))
        self.assertTrue(esperar(lambda: not trava.estado()["livre"]))
        self.assertTrue(esperar(lambda: (trava.estado().get("ocioso_s") or 0) >= 1.0, 12), "o batimento não registrou a ociosidade")
        e = trava.estado()
        self.assertEqual(e["dono"]["rotulo"], "parado")
        self.assertIn("grupos", e["dono"])
        r = trava.liberar_ocioso(se_ocioso=3600)                 # ainda não está parado há tanto tempo: não mata
        self.assertFalse(r["liberou"])
        self.assertIsNone(dono.poll())
        r = trava.liberar_ocioso(se_ocioso=1.0)
        self.assertTrue(r["liberou"], r)
        self.assertGreaterEqual(r["mortos"], 2)
        dono.wait(timeout=8)
        self.assertEqual(self.vivos(), 0)
        self.assertTrue(trava.estado()["livre"])
        self.assertFalse(trava.liberar_ocioso(se_ocioso=0)["liberou"])      # já livre: nada a fazer

    def test_liberar_ocioso_poupa_dono_que_trabalha(self):
        codigo = f"while True: sum(range(10000))  # {self.marca}"
        dono = self.lancar("--rotulo", "ocupado", "--", PY, "-c", codigo)
        self.assertTrue(esperar(lambda: not trava.estado()["livre"]))
        time.sleep(2.5)                                           # dá tempo de um batimento com CPU
        r = trava.liberar_ocioso(se_ocioso=1.0)
        self.assertFalse(r["liberou"], r)
        self.assertIsNone(dono.poll())
        dono.send_signal(signal.SIGTERM)
        dono.wait(timeout=10)

    def test_cli_estado_e_liberar(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(trava.main(["--inatividade", "abc", "--", "true"]), trava.SAIDA_USO)
            self.assertEqual(trava.main(["--prazo", "-1", "--", "true"]), trava.SAIDA_USO)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(trava.main(["--estado", "--json"]), 0)
            self.assertEqual(trava.main(["--liberar"]), 0)                         # já livre
        self.assertIn('"livre": true', out.getvalue())
        self.assertIn("já está livre", out.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
