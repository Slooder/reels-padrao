"""_win.py — o que o kit usa de Unix, refeito para Windows. ADAPTAÇÃO LOCAL: não vem da crIAbr
(ver ADAPTACAO-WINDOWS.md na raiz das skills); ao atualizar o kit pelo site, reaplique.

· flock: msvcrt.locking num byte muito além do fim do arquivo. No Windows a trava de região bloqueia leitura e
  escrita de outros processos naquela região; travando longe do começo, quem espera continua lendo o registro
  (pid, rótulo, grupos) que o dono grava no início do mesmo arquivo — como no flock do Unix.
· processos: psutil no lugar do /bin/ps. Não há grupo de processos no Windows: o "grupo" de um pid é a árvore dele.
· os.kill(pid, 0) NÃO serve para testar se um processo existe (no Windows 0 = CTRL_C_EVENT): use vivo().
Importar este módulo completa os/signal com o que falta no Windows (pwrite, killpg, getpgrp, SIGHUP, SIGKILL).
"""
import msvcrt
import os
import signal
import time

import psutil

LOCK_SH, LOCK_EX, LOCK_NB, LOCK_UN = 1, 2, 4, 8
_BYTE_DA_TRAVA = 0x7FFFFFF0


def flock(fd, op: int) -> None:
    fd = fd.fileno() if hasattr(fd, "fileno") else int(fd)
    antes = os.lseek(fd, 0, os.SEEK_CUR)
    os.lseek(fd, _BYTE_DA_TRAVA, os.SEEK_SET)
    try:
        if op & LOCK_UN:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        elif op & LOCK_NB:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)       # ocupada: OSError, como o flock com LOCK_NB
        else:
            while True:                                    # LK_LOCK desiste após 10 s; o flock bloqueante espera sempre
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
    finally:
        os.lseek(fd, antes, os.SEEK_SET)


def vivo(pid: int) -> bool:
    return pid > 0 and psutil.pid_exists(pid)


def tabela() -> dict[int, dict]:
    """Mesmo formato do _tabela() do trava.py: {pid: {ppid, pgid, cpu, inicio, comando}}; pgid = o próprio pid."""
    brutos = {}
    for p in psutil.process_iter(["pid", "ppid", "cpu_times", "create_time", "name"]):
        brutos[p.info["pid"]] = p.info
    t = {}
    for pid, i in brutos.items():
        ppid, criado = i["ppid"] or 0, i["create_time"] or 0.0
        pai = brutos.get(ppid)
        if pai is not None and (pai["create_time"] or 0.0) > criado:
            ppid = 0                                       # o pid do pai foi reaproveitado por outro processo: não é o pai
        ct = i["cpu_times"]
        t[pid] = {"ppid": ppid, "pgid": pid, "cpu": (ct.user + ct.system) if ct else 0.0,
                  "inicio": time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(criado)), "comando": i["name"] or ""}
    return t


def killpg(pgid: int, _sinal=None) -> None:
    """Mata a árvore do pid `pgid` (filhos antes, raiz por último). Sem a raiz: ProcessLookupError, como no Unix."""
    try:
        raiz = psutil.Process(int(pgid))
        arvore = raiz.children(recursive=True) + [raiz]
    except psutil.Error:
        raise ProcessLookupError(pgid) from None
    for p in arvore:
        try:
            p.kill()
        except psutil.Error:
            pass


def pwrite(fd: int, dados: bytes, posicao: int) -> int:
    antes = os.lseek(fd, 0, os.SEEK_CUR)
    os.lseek(fd, posicao, os.SEEK_SET)
    try:
        return os.write(fd, dados)
    finally:
        os.lseek(fd, antes, os.SEEK_SET)


for _nome, _valor in (("pwrite", pwrite), ("killpg", killpg), ("getpgrp", os.getpid)):
    if not hasattr(os, _nome):
        setattr(os, _nome, _valor)
# só nomes: signal.signal() com eles levanta ValueError, que o trava.py já trata como "sinal indisponível"
for _nome, _valor in (("SIGHUP", 1), ("SIGKILL", 9)):
    if not hasattr(signal, _nome):
        setattr(signal, _nome, _valor)
