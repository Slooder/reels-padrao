#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""trava.py — trava global da operação de vídeo (uma tarefa pesada por vez).

Máquina de 8 GB: ffmpeg, Chromium/Playwright, whisper e compilação Swift nunca
rodam ao mesmo tempo. Todo comando pesado passa por aqui.

Linha de comando
    python3 trava.py [--espera-max SEG] [--inatividade SEG] [--prazo SEG] [--rotulo TEXTO] [--silencioso] -- <comando…>
    python3 trava.py --estado [--json]
    python3 trava.py --liberar [--se-ocioso SEG]

    Fila bloqueante por fcntl.flock num arquivo fixo (/tmp/video-ops-render.lock).
    Enquanto espera, avisa "aguardando trava…" no stderr a cada ~15 s, dizendo há
    quanto tempo o dono está sem progresso. O código de saída é o do comando.
    Códigos próprios: 75 = esperou mais que --espera-max; 124 = o comando foi morto
    pelo vigia (--inatividade ou --prazo); 127 = comando não encontrado;
    126 = comando sem permissão; 64 = uso incorreto; 128+N = morto pelo sinal N.

Garantias (nenhum caminho segura a trava para sempre)
    · O comando roda num grupo de processos próprio. SIGINT/SIGTERM/SIGHUP no dono
      matam o grupo inteiro e os descendentes (node, Chromium, ffmpeg) ANTES de a
      trava ser solta; quem ainda estiver vivo depois de 3 s leva SIGKILL.
    · Dono morto (até por SIGKILL) = trava livre para quem espera; quem assume
      encerra primeiro os grupos órfãos que o dono morto tinha registrado.
    · Vigia de inatividade: com --inatividade SEG (ou `inatividade=` em rodar/
      executar), comando sem progresso (CPU da árvore de processos, saída
      capturada, entrada consumida, arquivos vigiados) por SEG segundos é morto
      e a trava é liberada com código 124. --prazo SEG limita o tempo total.
    · `--liberar` é a saída manual: mata o dono (e a árvore dele) se ele estiver
      sem progresso há pelo menos --se-ocioso segundos (padrão 120).

Reentrância
    O filho recebe VIDEO_OPS_TRAVA=<pid do dono>. Um processo que já roda sob a
    trava (variável presente, dono vivo e registrado no arquivo da trava) executa
    direto, sem entrar na fila — por isso um script travado pode chamar outro
    script travado sem se enforcar.

Como módulo
    import trava
    r = trava.rodar(["ffmpeg", "-i", …], rotulo="corte 3", inatividade=120, capturar=True)
    r.codigo, r.stderr, r.motivo            # motivo: None | 'inatividade' | 'prazo'
    rc = trava.executar(["ffmpeg", "-i", …])  # só o código; saída herdada
    with trava.Trava(rotulo="legendas em PIL"):
        ...                                   # trabalho pesado dentro do próprio Python

Variáveis de ambiente
    VIDEO_OPS_TRAVA          pid do dono (definida pela própria trava; não mexa)
    VIDEO_OPS_TRAVA_ARQUIVO  troca o arquivo da trava — SOMENTE para testes
    VIDEO_OPS_INATIVIDADE    segundos do vigia de inatividade dos comandos do kit (motor, video.executar,
                             da.py grade); 0 desliga. Sem a variável cada comando usa o próprio padrão.
"""
from __future__ import annotations

try:
    import fcntl
    _win = None
except ImportError:                     # Windows: adaptação local (ver _win.py)
    import _win
    fcntl = _win
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

# D9 — a skill instalada não acumula __pycache__. A linha abaixo vale para tudo o que for importado DEPOIS; o .pyc do
# primeiro módulo do kit que o programa importou já foi gravado antes de qualquer linha dele rodar, por isso a pasta é
# apagada aqui (trava.py é a base de da.py, texto.py e video.py: todo import do kit passa por este ponto).
sys.dont_write_bytecode = True


def _sem_pycache() -> None:
    import shutil
    shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__"), ignore_errors=True)


_sem_pycache()

ARQUIVO_PADRAO = os.path.join(__import__("tempfile").gettempdir(), "video-ops-render.lock") if _win else "/tmp/video-ops-render.lock"
VAR_DONO = "VIDEO_OPS_TRAVA"
VAR_ARQUIVO = "VIDEO_OPS_TRAVA_ARQUIVO"
VAR_INATIVIDADE = "VIDEO_OPS_INATIVIDADE"
AVISO_A_CADA = 15.0          # segundos entre avisos "aguardando trava…"
PASSO_ESPERA = 0.25          # intervalo entre tentativas de flock
PASSO_VIGIA = 0.25           # intervalo do laço que acompanha o comando
BATIMENTO_A_CADA = 2.0       # o dono regrava o registro (batimento + ociosidade) neste intervalo
CARENCIA = 3.0               # segundos entre o SIGTERM e o SIGKILL
CPU_MINIMA = 0.03            # fração de um núcleo abaixo da qual a árvore conta como parada
SE_OCIOSO_PADRAO = 120.0     # --liberar só mata dono parado há pelo menos isto
MODO_ARQUIVO = 0o600         # o registro (pid, rótulo, grupos) é lido por quem espera e usado para encerrar órfãos
TAM_REGISTRO = 2048          # o registro é regravado com tamanho fixo num único pwrite (leitura nunca vê pela metade)
LIMITE_CAPTURA = 8 * 1024 * 1024
SAIDA_TEMPO_ESGOTADO = 75    # EX_TEMPFAIL
SAIDA_USO = 64               # EX_USAGE
SAIDA_VIGIA = 124            # morto pelo vigia (inatividade ou prazo), como o `timeout` do coreutils
HERDAR = "herdar"            # valor de `entrada`: o comando lê o stdin de quem chamou

__all__ = ["Trava", "TempoEsgotado", "Interrompido", "Resultado", "rodar", "executar", "estado", "liberar_ocioso",
           "descrever_vigia", "inatividade_padrao", "arquivo_da_trava", "sob_trava", "HERDAR", "SAIDA_VIGIA",
           "SAIDA_TEMPO_ESGOTADO"]


class TempoEsgotado(TimeoutError):
    """A espera pela trava passou de espera_max."""


class Interrompido(SystemExit):
    """SIGTERM ou SIGHUP chegou enquanto este processo segurava a trava.

    É um SystemExit com código 128+sinal: os `finally`/`with` rodam (a trava é solta e os filhos
    já foram mortos) e, se ninguém capturar, o processo sai com o código certo e sem traceback."""

    def __init__(self, sinal: int):
        super().__init__(128 + int(sinal))
        self.sinal = int(sinal)


class Resultado:
    """O que `rodar` devolve. `codigo` é o código de saída (128+N se morto pelo sinal N; 124 se morto pelo vigia)."""

    def __init__(self, comando, codigo: int, stdout, stderr, motivo: str | None, duracao: float, ocioso: float = 0.0):
        self.comando = list(comando)
        self.codigo = int(codigo)
        self.stdout = stdout
        self.stderr = stderr
        self.motivo = motivo            # None | 'inatividade' | 'prazo'
        self.duracao = duracao
        self.ocioso = ocioso            # segundos sem progresso no momento em que o vigia agiu

    @property
    def returncode(self) -> int:        # mesma leitura de um subprocess.CompletedProcess
        return self.codigo

    def __repr__(self) -> str:
        return f"Resultado(codigo={self.codigo}, motivo={self.motivo!r}, duracao={self.duracao:.2f})"


def arquivo_da_trava() -> str:
    return os.environ.get(VAR_ARQUIVO) or ARQUIVO_PADRAO


def inatividade_padrao(padrao: float | None) -> float | None:
    """Limite de inatividade dos comandos do kit: a variável VIDEO_OPS_INATIVIDADE (segundos; 0 desliga) ou `padrao`."""
    bruto = os.environ.get(VAR_INATIVIDADE, "").strip()
    if bruto:
        try:
            v = float(bruto)
            return v if v > 0 else None
        except ValueError:
            pass
    return padrao


# ───────────────────────────────────────────────────────────── processos ──
def _vivo(pid: int) -> bool:
    if _win:
        return _win.vivo(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, OverflowError):
        return False
    return True


def _cpu_seg(texto: str) -> float:
    """Coluna `time` do ps ("0:00.03", "123:45.67", "01:02:03", "1-02:03:04") → segundos."""
    dias = 0
    if "-" in texto:
        d, texto = texto.split("-", 1)
        dias = int(d or 0)
    seg = 0.0
    for parte in texto.split(":"):
        seg = seg * 60 + float(parte or 0)
    return dias * 86400 + seg


def _tabela() -> dict[int, dict]:
    """Todos os processos: {pid: {'ppid', 'pgid', 'cpu' (s), 'inicio' (texto do lstart), 'comando'}}. {} se o ps falhar."""
    if _win:
        return _win.tabela()
    try:
        r = subprocess.run(["/bin/ps", "-axo", "pid=,ppid=,pgid=,time=,lstart=,comm="], capture_output=True, text=True,
                           env={"LC_ALL": "C", "PATH": "/bin:/usr/bin"}, timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return {}
    tabela: dict[int, dict] = {}
    for linha in r.stdout.splitlines():
        p = linha.split(None, 9)
        if len(p) < 9:
            continue
        try:
            tabela[int(p[0])] = {"ppid": int(p[1]), "pgid": int(p[2]), "cpu": _cpu_seg(p[3]), "inicio": " ".join(p[4:9]),
                                 "comando": p[9].strip() if len(p) > 9 else ""}
        except ValueError:
            continue
    return tabela


def _arvore(raizes, tabela: dict[int, dict], grupos=()) -> set[int]:
    """pids de `raizes`, de todos os descendentes e dos membros dos `grupos` (pgid) — só os que existem na tabela."""
    filhos: dict[int, list[int]] = {}
    for pid, info in tabela.items():
        filhos.setdefault(info["ppid"], []).append(pid)
    grupos = {int(g) for g in grupos}
    fila = [int(r) for r in raizes] + [pid for pid, info in tabela.items() if info["pgid"] in grupos]
    achados: set[int] = set()
    while fila:
        pid = fila.pop()
        if pid in achados or pid <= 1:
            continue
        achados.add(pid)
        fila += filhos.get(pid, [])
    return {p for p in achados if p in tabela}


def _cpu_da_arvore(raizes, grupos=()) -> tuple[float, frozenset] | None:
    """(segundos de CPU somados, conjunto de pids) da árvore; None se o ps não respondeu."""
    tabela = _tabela()
    if not tabela:
        return None
    pids = _arvore(raizes, tabela, grupos)
    return sum(tabela[p]["cpu"] for p in pids), frozenset(pids)


def _ancestral(pid: int) -> bool:
    """True se `pid` é ancestral deste processo (pai, avô, …)."""
    tabela = _tabela()
    atual = os.getpid()
    for _ in range(64):
        info = tabela.get(atual)
        if info is None:
            return False
        atual = info["ppid"]
        if atual == pid:
            return True
        if atual <= 1:
            return False
    return False


def _epoch_do_inicio(texto: str) -> float | None:
    try:
        return time.mktime(time.strptime(texto, "%a %b %d %H:%M:%S %Y"))
    except (ValueError, OverflowError):
        return None


def _sinalizar(pids, sinal: int, grupos=()) -> None:
    for g in grupos:
        try:
            os.killpg(int(g), sinal)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    for p in pids:
        if p == os.getpid() or p <= 1:
            continue
        try:
            os.kill(int(p), sinal)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _matar_arvore(raizes, grupos=(), esperar=None, carencia: float = CARENCIA, primeiro: int = signal.SIGTERM,
                  extras=()) -> int:
    """SIGTERM na árvore (raízes + descendentes + grupos + `extras`), espera `carencia` e manda SIGKILL em quem sobrou.
    `esperar`: Popen do filho direto (para recolher o código). `extras`: pids já conhecidos da árvore (um neto que
    virou órfão não é mais achado pelo parentesco). Devolve quantos processos foram sinalizados."""
    tabela = _tabela()
    alvo = _arvore(raizes, tabela, grupos) | {int(r) for r in raizes if _vivo(int(r))} | {int(p) for p in extras if _vivo(int(p))}
    alvo.discard(os.getpid())
    _sinalizar(alvo, primeiro, grupos)
    limite = time.monotonic() + max(0.0, carencia)
    while time.monotonic() < limite:
        saiu = True
        if esperar is not None:
            try:
                esperar.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                saiu = False
        if saiu:
            if not any(_vivo(p) for p in alvo if esperar is None or p != esperar.pid):
                break
            time.sleep(0.1)
    # segunda varredura: netos que nasceram depois e quem ignorou o SIGTERM
    tabela = _tabela()
    resto = {p for p in alvo if _vivo(p)} | _arvore(raizes, tabela, grupos)
    resto.discard(os.getpid())
    if resto:
        _sinalizar(resto, signal.SIGKILL, grupos)
    if esperar is not None:
        try:
            esperar.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    return len(alvo | resto)


# ───────────────────────────────────────────────────────────── registro ──
def _ler_registro(caminho: str) -> dict:
    """Quem está com a trava, segundo o próprio arquivo ({} se livre ou ilegível)."""
    for tentativa in range(3):
        try:
            with open(caminho, "r", encoding="utf-8", errors="replace") as f:
                bruto = f.read(TAM_REGISTRO * 2).strip().strip("\x00")
            if not bruto:
                return {}
            dado = json.loads(bruto)
            return dado if isinstance(dado, dict) else {}
        except OSError:
            return {}
        except ValueError:
            time.sleep(0.02)          # leitura no meio de uma regravação: tenta de novo
    return {}


def sob_trava(caminho: str | None = None) -> int | None:
    """pid do dono se ESTE processo já roda sob a trava; senão None.

    Exige três coisas: a variável VIDEO_OPS_TRAVA, o dono vivo e o mesmo pid
    registrado no arquivo da trava. A terceira evita falso positivo quando um
    processo em segundo plano herdou a variável de um dono que já liberou.
    """
    valor = os.environ.get(VAR_DONO, "").strip()
    if not valor.isdigit():
        return None
    pid = int(valor)
    if pid <= 1 or not _vivo(pid):
        return None
    if _ler_registro(caminho or arquivo_da_trava()).get("pid") != pid:
        return None
    return pid


def _ociosidade(reg: dict) -> float | None:
    """Segundos sem progresso segundo o batimento do dono (None se o dono não bate ou o batimento está velho)."""
    bat, ocioso = reg.get("batimento"), reg.get("ocioso_s")
    if not isinstance(bat, (int, float)) or not isinstance(ocioso, (int, float)):
        return None
    if time.time() - bat > BATIMENTO_A_CADA * 5:
        return None
    return max(0.0, float(ocioso))


def estado(caminho: str | None = None) -> dict:
    """{'livre': bool, 'dono': {...} | None, 'ocioso_s': float | None} sem entrar na fila.

    `ocioso_s` vem do batimento que `rodar`/`executar` gravam; dono que só usa `with Trava()` não bate
    (None): meça por fora com liberar_ocioso() ou `trava.py --estado`, que amostra a CPU do dono."""
    caminho = caminho or arquivo_da_trava()
    try:
        fd = os.open(caminho, os.O_RDWR | os.O_CREAT, MODO_ARQUIVO)
    except OSError as e:
        return {"livre": False, "dono": None, "ocioso_s": None, "erro": str(e)}
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            reg = _ler_registro(caminho)
            return {"livre": False, "dono": reg or None, "ocioso_s": _ociosidade(reg)}
        fcntl.flock(fd, fcntl.LOCK_UN)
        return {"livre": True, "dono": None, "ocioso_s": None}
    finally:
        os.close(fd)


def _descrever_dono(reg: dict, ocioso: float | None = None) -> str:
    if not reg:
        return "dono desconhecido"
    partes = [f"pid {reg.get('pid', '?')}"]
    if reg.get("rotulo"):
        partes.append(str(reg["rotulo"]))
    desde = reg.get("desde_epoch")
    if isinstance(desde, (int, float)):
        partes.append(f"há {max(0, int(time.time() - desde))} s")
    if ocioso is None:
        ocioso = _ociosidade(reg)
    if ocioso is not None and ocioso >= 10:
        partes.append(f"SEM PROGRESSO há {int(ocioso)} s")
    return ", ".join(partes)


_INTERPRETADORES = ("python", "node", "sh", "bash", "zsh", "env", "ruby", "perl", "swift", "deno", "bun")
_EXT_DE_SCRIPT = (".py", ".mjs", ".js", ".cjs", ".sh", ".rb", ".pl", ".swift", ".ts")


def _rotulo_padrao(comando) -> str:
    """Rótulo público de um comando sem --rotulo: SÓ o nome do executável (e, se ele for um interpretador,
    o nome do script). Nunca os argumentos: o rótulo fica gravado no arquivo da trava e é impresso no stderr
    de todo processo que espera na fila — URL com chave, caminho de cliente ou texto de roteiro não podem ir parar lá."""
    partes = [str(c) for c in comando]
    if not partes:
        return ""
    nome = os.path.basename(partes[0]) or partes[0]
    if nome.lower().startswith(_INTERPRETADORES):
        for arg in partes[1:]:
            if arg.startswith("-"):
                if arg in ("-c", "-e", "-m", "--eval", "--"):
                    break                                    # o que vem depois é código ou argumento: fica fora
                continue
            if arg.lower().endswith(_EXT_DE_SCRIPT):
                nome += " " + os.path.basename(arg)
            break
    return nome[:60]


def _encerrar_orfaos(reg: dict, mtime: float | None) -> int:
    """O dono registrado morreu sem liberar: encerra os grupos de processos que ele deixou.

    Só mata o que comprovadamente é dele: o líder do grupo ainda é o mesmo processo (mesmo instante de
    início) ou, se o líder já morreu, membros do grupo que nasceram antes da última escrita do registro."""
    grupos = [g for g in (reg.get("grupos") or []) if isinstance(g, dict) and isinstance(g.get("pgid"), int)]
    if not grupos:
        return 0
    tabela = _tabela()
    alvos: set[int] = set()
    pgids: list[int] = []
    for g in grupos:
        pgid = g["pgid"]
        membros = [pid for pid, info in tabela.items() if info["pgid"] == pgid]
        if not membros or pgid <= 1 or pgid == os.getpgrp():
            continue
        lider = tabela.get(pgid)
        if lider is not None and g.get("inicio") and lider["inicio"] == g["inicio"]:
            alvos |= set(membros)
            pgids.append(pgid)
            continue
        if lider is None and mtime is not None:
            for pid in membros:
                nasceu = _epoch_do_inicio(tabela[pid]["inicio"])
                if nasceu is not None and nasceu <= mtime + 5:
                    alvos.add(pid)
    alvos.discard(os.getpid())
    if not alvos:
        return 0
    return _matar_arvore(sorted(alvos), grupos=pgids)


_DONA: "Trava | None" = None      # a Trava que segura o descritor NESTE processo (as reentrantes delegam a ela)


class Trava:
    """Trava global exclusiva e reentrante. Use com `with`.

    espera_max: segundos máximos na fila (None = espera para sempre).
    rotulo:     texto curto mostrado a quem ficar esperando.
    silencioso: não escreve avisos no stderr.
    arquivo:    arquivo da trava (padrão: /tmp/video-ops-render.lock).
    sinais:     True (padrão) = enquanto segura a trava, SIGTERM/SIGHUP viram a exceção Interrompido
                (só na thread principal e só se o programa não tiver tratador próprio): um
                `subprocess.run` em andamento mata o filho e a trava é solta em ordem.

    Para rodar um comando pesado prefira `rodar()`/`executar()`: além da trava, cuidam do grupo de
    processos, do repasse de sinais e do vigia de inatividade.
    """

    def __init__(self, espera_max: float | None = None, rotulo: str | None = None,
                 silencioso: bool = False, arquivo: str | None = None, sinais: bool = True):
        self.espera_max = espera_max
        self.rotulo = rotulo
        self.silencioso = silencioso
        self.arquivo = arquivo or arquivo_da_trava()
        self.sinais = sinais
        self._fd: int | None = None
        self._env_antes: str | None = None
        self._registro: dict = {}
        self._sinais_antes: dict = {}
        self._env_reentrada: tuple | None = None
        self._escrita = threading.Lock()
        self.reentrante = False
        self.esperou = 0.0
        self.orfaos_encerrados = 0

    # -- registro (só a dona escreve) ---------------------------------------
    def _gravar(self) -> None:
        if self._fd is None:
            return
        with self._escrita:
            reg = dict(self._registro)
            bruto = json.dumps(reg, ensure_ascii=False).encode("utf-8")
            if len(bruto) > TAM_REGISTRO - 1:                      # rótulo longo demais: encurta em vez de quebrar o JSON
                reg["rotulo"] = str(reg.get("rotulo", ""))[:80]
                reg["grupos"] = (reg.get("grupos") or [])[-8:]
                bruto = json.dumps(reg, ensure_ascii=False).encode("utf-8")[:TAM_REGISTRO - 1]
            try:
                os.pwrite(self._fd, bruto.ljust(TAM_REGISTRO - 1) + b"\n", 0)
            except OSError:
                pass

    def registrar_grupo(self, pgid: int, comando: str = "") -> None:
        """Anota um grupo de processos filho no registro: se o dono morrer, quem assumir a trava o encerra."""
        dona = self if self._fd is not None else _DONA
        if dona is None or dona._fd is None:
            return
        inicio = (_tabela().get(int(pgid)) or {}).get("inicio", "")
        grupos = [g for g in dona._registro.get("grupos", []) if g.get("pgid") != int(pgid)]
        grupos.append({"pgid": int(pgid), "inicio": inicio, "comando": os.path.basename(str(comando))[:40]})
        dona._registro["grupos"] = grupos[-16:]
        dona._gravar()

    def esquecer_grupo(self, pgid: int) -> None:
        dona = self if self._fd is not None else _DONA
        if dona is None or dona._fd is None:
            return
        dona._registro["grupos"] = [g for g in dona._registro.get("grupos", []) if g.get("pgid") != int(pgid)]
        dona._gravar()

    def bater(self, ocioso_s: float = 0.0) -> None:
        """Batimento do dono: quem espera (e `--estado`) lê daqui há quanto tempo não há progresso."""
        dona = self if self._fd is not None else _DONA
        if dona is None or dona._fd is None:
            return
        dona._registro["batimento"] = round(time.time(), 3)
        dona._registro["ocioso_s"] = round(max(0.0, ocioso_s), 1)
        dona._gravar()

    # -- ciclo de vida -----------------------------------------------------
    def adquirir(self) -> "Trava":
        global _DONA
        if self._fd is not None or self.reentrante:
            return self
        if sob_trava(self.arquivo) is not None:
            self.reentrante = True          # já estamos dentro: executa direto
            return self
        try:
            fd = os.open(self.arquivo, os.O_RDWR | os.O_CREAT, MODO_ARQUIVO)
        except PermissionError:
            raise PermissionError(f"não consegui abrir o arquivo da trava {self.arquivo}: ele pertence a outro usuário. "
                                  f"A trava é por usuário (modo 600); se a máquina é compartilhada, aponte {VAR_ARQUIVO} "
                                  f"para um arquivo seu.") from None
        try:
            os.fchmod(fd, MODO_ARQUIVO)     # arquivo antigo criado com 666 volta a ser só do dono
        except OSError:
            pass
        inicio = time.monotonic()
        proximo_aviso = inicio              # primeiro aviso assim que bloquear
        proxima_linhagem = inicio
        amostra = None                      # (instante, cpu, pids) do dono, para quem não bate
        parado_desde = None
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    pass
                agora = time.monotonic()
                if agora >= proxima_linhagem:
                    # O dono é nosso ancestral e a variável VIDEO_OPS_TRAVA se perdeu no caminho (env limpo, sudo,
                    # `env=` sem ela): esperar seria um impasse eterno — ele espera por nós. É reentrância.
                    dono = _ler_registro(self.arquivo).get("pid")
                    if isinstance(dono, int) and dono > 1 and _vivo(dono) and _ancestral(dono):
                        os.close(fd)
                        self.reentrante = True
                        self._env_reentrada = (os.environ.get(VAR_DONO),)
                        os.environ[VAR_DONO] = str(dono)
                        return self
                    proxima_linhagem = agora + 5.0
                if self.espera_max is not None and agora - inicio >= self.espera_max:
                    raise TempoEsgotado(
                        f"trava ocupada há mais de {self.espera_max:g} s "
                        f"({_descrever_dono(_ler_registro(self.arquivo))}); desisti de esperar")
                if agora >= proximo_aviso and not self.silencioso:
                    reg = _ler_registro(self.arquivo)
                    ocioso = _ociosidade(reg)
                    if ocioso is None and isinstance(reg.get("pid"), int):      # dono sem batimento: mede a CPU dele
                        medida = _cpu_da_arvore([reg["pid"]], [g.get("pgid") for g in reg.get("grupos") or [] if isinstance(g, dict)])
                        if medida is not None and amostra is not None and medida[1] == amostra[2] \
                                and medida[0] - amostra[1] < CPU_MINIMA * (agora - amostra[0]):
                            parado_desde = parado_desde if parado_desde is not None else amostra[0]
                            ocioso = agora - parado_desde
                        else:
                            parado_desde = None
                        amostra = (agora, medida[0], medida[1]) if medida is not None else None
                    dica = ""
                    if ocioso is not None and ocioso >= 60:
                        dica = f' — se for travamento: python3 "{os.path.abspath(__file__)}" --liberar'
                    print(f"[trava] aguardando trava… ({int(agora - inicio)} s na fila; em uso por "
                          f"{_descrever_dono(reg, ocioso)}){dica}", file=sys.stderr, flush=True)
                    proximo_aviso = agora + AVISO_A_CADA
                time.sleep(PASSO_ESPERA)
        except BaseException:
            os.close(fd)
            raise
        self.esperou = time.monotonic() - inicio
        # registro que sobrou de um dono que morreu sem liberar (o flock é solto pelo sistema): assume e limpa os órfãos
        velho = _ler_registro(self.arquivo)
        if velho.get("pid") and velho.get("pid") != os.getpid():
            try:
                mtime = os.fstat(fd).st_mtime
            except OSError:
                mtime = None
            self.orfaos_encerrados = _encerrar_orfaos(velho, mtime)
            if not self.silencioso:
                print(f"[trava] o dono anterior (pid {velho.get('pid')}"
                      + (f", {velho['rotulo']}" if velho.get("rotulo") else "") + ") morreu sem liberar; trava assumida"
                      + (f" e {self.orfaos_encerrados} processo(s) órfão(s) encerrado(s)" if self.orfaos_encerrados else ""),
                      file=sys.stderr, flush=True)
        self._fd = fd
        self._registro = {"pid": os.getpid(), "rotulo": self.rotulo or "",
                          "desde": datetime.now().astimezone().isoformat(timespec="seconds"),
                          "desde_epoch": round(time.time(), 3), "grupos": []}
        try:
            os.ftruncate(fd, 0)
        except OSError:
            pass
        self._gravar()
        try:
            os.fsync(fd)
        except OSError:
            pass
        self._env_antes = os.environ.get(VAR_DONO)
        os.environ[VAR_DONO] = str(os.getpid())
        _DONA = self
        if self.sinais and threading.current_thread() is threading.main_thread():
            for s in (signal.SIGTERM, signal.SIGHUP):
                try:
                    if signal.getsignal(s) is signal.SIG_DFL:
                        self._sinais_antes[s] = signal.signal(s, _levantar_interrompido)
                except (ValueError, OSError):
                    pass
        return self

    def liberar(self) -> None:
        global _DONA
        if self.reentrante:
            self.reentrante = False
            if self._env_reentrada is not None:
                (antes,), self._env_reentrada = self._env_reentrada, None
                if antes is None:
                    os.environ.pop(VAR_DONO, None)
                else:
                    os.environ[VAR_DONO] = antes
            return
        if self._fd is None:
            return
        for s, anterior in self._sinais_antes.items():
            try:
                if signal.getsignal(s) is _levantar_interrompido:
                    signal.signal(s, anterior)
            except (ValueError, OSError):
                pass
        self._sinais_antes = {}
        fd, self._fd = self._fd, None
        if _DONA is self:
            _DONA = None
        if self._env_antes is None:
            os.environ.pop(VAR_DONO, None)
        else:
            os.environ[VAR_DONO] = self._env_antes
        try:
            os.ftruncate(fd, 0)
        except OSError:
            pass
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> "Trava":
        return self.adquirir()

    def __exit__(self, *exc) -> bool:
        self.liberar()
        return False


def _levantar_interrompido(sinal, _quadro):
    raise Interrompido(sinal)


# ────────────────────────────────────────────────────────────────── rodar ──
class _Coletor(threading.Thread):
    """Drena um pipe de saída do filho (sem isso um stderr cheio trava o filho) guardando só o final."""

    def __init__(self, fluxo, limite: int = LIMITE_CAPTURA):
        super().__init__(daemon=True)
        self.fluxo, self.limite = fluxo, limite
        self.pedacos: list[bytes] = []
        self.guardado = 0
        self.total = 0

    def run(self):
        try:
            while True:
                dado = self.fluxo.read1(65536) if hasattr(self.fluxo, "read1") else self.fluxo.read(65536)
                if not dado:
                    break
                self.total += len(dado)
                self.pedacos.append(dado)
                self.guardado += len(dado)
                while self.guardado > self.limite and len(self.pedacos) > 1:
                    self.guardado -= len(self.pedacos.pop(0))
        except (OSError, ValueError):
            pass
        finally:
            try:
                self.fluxo.close()
            except OSError:
                pass

    def conteudo(self) -> bytes:
        return b"".join(self.pedacos)


class _Alimentador(threading.Thread):
    """Escreve `entrada` (bytes ou iterável de bytes) no stdin do filho e FECHA o stdin no fim, aconteça o que acontecer."""

    def __init__(self, fluxo, entrada):
        super().__init__(daemon=True)
        self.fluxo, self.entrada = fluxo, entrada
        self.total = 0
        self.erro: BaseException | None = None      # erro de quem PRODUZ a entrada (não o EPIPE do filho)
        self.quebrou = False                         # o filho fechou o stdin antes do fim (EPIPE)
        self.parar = False

    def run(self):
        try:
            pedacos = [self.entrada] if isinstance(self.entrada, (bytes, bytearray, memoryview)) else self.entrada
            for pedaco in pedacos:
                if self.parar:
                    break
                if not pedaco:
                    continue
                try:
                    self.fluxo.write(pedaco)
                    self.fluxo.flush()
                except (BrokenPipeError, ConnectionResetError, ValueError, OSError):
                    self.quebrou = True
                    break
                self.total += len(pedaco)
        except BaseException as e:                   # o gerador de quadros falhou
            self.erro = e
        finally:
            try:
                self.fluxo.close()
            except (BrokenPipeError, OSError, ValueError):
                pass


def rodar(comando: list[str], *, rotulo: str | None = None, espera_max: float | None = None, silencioso: bool = False,
          inatividade: float | None = None, prazo: float | None = None, entrada=None, capturar: bool = False,
          texto: bool = True, cwd=None, env=None, vigiar=(), **popen) -> Resultado:
    """Roda `comando` sob a trava global, num grupo de processos próprio, e devolve um Resultado.

    entrada:     None = stdin em /dev/null (padrão: o filho NUNCA fica esperando um stdin que ninguém fecha);
                 trava.HERDAR = herda o stdin de quem chamou; bytes ou iterável de bytes = escritos por uma
                 thread, com o stdin fechado ao fim (se o gerador levantar, o filho é morto e a exceção sobe).
    capturar:    True = stdout/stderr vão para Resultado.stdout/.stderr (drenados em threads; guarda os
                 últimos 8 MB de cada). False = herdados.
    inatividade: segundos sem progresso até o vigia matar o comando (None/0 = sem vigia). Progresso = CPU da
                 árvore de processos, bytes de saída capturada, bytes de entrada consumidos, ou mudança de
                 tamanho/mtime em algum caminho de `vigiar`. Resultado.motivo = 'inatividade', código 124.
    prazo:       segundos máximos de execução (None = sem limite). Resultado.motivo = 'prazo', código 124.
    Sinais:      SIGINT/SIGTERM/SIGHUP neste processo (thread principal) matam a árvore do filho antes de a
                 trava ser solta; depois sobem KeyboardInterrupt (SIGINT) ou trava.Interrompido (os outros).
    Levanta TempoEsgotado se a fila passar de espera_max e os erros normais do Popen (FileNotFoundError…)."""
    comando = [str(c) for c in comando]
    herdar_entrada = isinstance(entrada, str) and entrada == HERDAR
    if isinstance(entrada, str) and not herdar_entrada:
        raise TypeError("rodar: `entrada` precisa ser bytes, um iterável de bytes, trava.HERDAR ou None (texto: use .encode())")
    inatividade = float(inatividade) if inatividade else None
    prazo = float(prazo) if prazo else None
    vigiar = [str(v) for v in vigiar]
    t_inicio = time.monotonic()
    with Trava(espera_max=espera_max, rotulo=rotulo or _rotulo_padrao(comando), silencioso=silencioso) as tr:
        na_principal = threading.current_thread() is threading.main_thread()
        grupo_proprio = _DONA is not None                     # reentrante de OUTRO processo: fica no grupo que o dono já vigia
        kw = dict(popen)
        for chave in ("text", "encoding", "errors", "universal_newlines"):     # os pipes daqui são sempre binários
            kw.pop(chave, None)
        if entrada is None:
            kw.setdefault("stdin", subprocess.DEVNULL)
        elif not herdar_entrada:
            kw["stdin"] = subprocess.PIPE
        if capturar:
            kw["stdout"], kw["stderr"] = subprocess.PIPE, subprocess.PIPE
        if grupo_proprio:
            kw["start_new_session"] = True
        if env is not None and os.environ.get(VAR_DONO):
            env = {**env, VAR_DONO: os.environ[VAR_DONO]}      # um `env` montado antes de a trava existir não a conhece
        proc = subprocess.Popen(comando, cwd=str(cwd) if cwd else None, env=env, **kw)
        grupos = [proc.pid] if grupo_proprio else []
        if grupo_proprio:
            tr.registrar_grupo(proc.pid, comando[0])
        recebidos: list[int] = []
        anteriores = {}
        conhecidos: set[int] = set()                          # pids já vistos na árvore do filho

        def ao_sinal(sinal, _quadro):
            if not recebidos:
                conhecidos.update(_arvore([proc.pid], _tabela(), grupos))   # antes de o parentesco se desfazer
            recebidos.append(sinal)
            _sinalizar(conhecidos | {proc.pid}, sinal, grupos)  # repassa já; o laço abaixo escala para SIGKILL

        if na_principal:
            for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                try:
                    if signal.getsignal(s) is signal.SIG_IGN:
                        continue                              # sinal ignorado de propósito (nohup, job em segundo plano): respeita
                    anteriores[s] = signal.signal(s, ao_sinal)
                except (ValueError, OSError):
                    pass
        coletores = {}
        alimentador = None
        motivo = None
        ocioso = 0.0
        try:
            if capturar:
                coletores = {"stdout": _Coletor(proc.stdout), "stderr": _Coletor(proc.stderr)}
                for c in coletores.values():
                    c.start()
            if kw.get("stdin") is subprocess.PIPE and entrada is not None and not herdar_entrada:
                alimentador = _Alimentador(proc.stdin, entrada)
                alimentador.start()

            def marcas():
                m = [sum(c.total for c in coletores.values()), alimentador.total if alimentador else 0]
                for v in vigiar:
                    try:
                        st = os.stat(v)
                        m += [st.st_size, st.st_mtime_ns]
                    except OSError:
                        m += [None, None]
                return m

            # Ociosidade = tempo entre o último progresso visto e o último EXAME de CPU: só cresce quando uma amostra
            # confirma que nada andou (entre duas amostras não se sabe, e na dúvida não se acusa ninguém).
            ultimo_progresso = ultimo_exame = t_inicio_filho = time.monotonic()
            marcas_antes = marcas()
            medida = _cpu_da_arvore([proc.pid], grupos)
            cpu_antes = (t_inicio_filho, medida[0], medida[1]) if medida is not None else None
            intervalo_cpu = min(3.0, max(1.0, inatividade / 6)) if inatividade else 3.0
            proxima_cpu = t_inicio_filho + intervalo_cpu
            proximo_batimento = t_inicio_filho + BATIMENTO_A_CADA
            while True:
                try:
                    proc.wait(timeout=PASSO_VIGIA)
                    break
                except subprocess.TimeoutExpired:
                    pass
                agora = time.monotonic()
                if recebidos:
                    break
                if alimentador is not None and alimentador.erro is not None:
                    _matar_arvore([proc.pid], grupos, esperar=proc, extras=conhecidos)
                    break
                m = marcas()
                if m != marcas_antes:
                    marcas_antes, ultimo_progresso = m, agora
                if agora >= proxima_cpu:
                    medida = _cpu_da_arvore([proc.pid], grupos)
                    ultimo_exame = agora
                    if medida is None:
                        ultimo_progresso = agora              # sem medida não se mata ninguém por inatividade
                    elif cpu_antes is None or medida[1] != cpu_antes[2] \
                            or medida[0] - cpu_antes[1] >= CPU_MINIMA * (agora - cpu_antes[0]):
                        ultimo_progresso = agora
                    cpu_antes = (agora, medida[0], medida[1]) if medida is not None else None
                    if medida is not None:
                        conhecidos.update(medida[1])
                    proxima_cpu = agora + intervalo_cpu
                ocioso = max(0.0, ultimo_exame - ultimo_progresso)
                if agora >= proximo_batimento:
                    tr.bater(ocioso)
                    proximo_batimento = agora + BATIMENTO_A_CADA
                if inatividade and ocioso >= inatividade:
                    motivo = "inatividade"
                elif prazo and agora - t_inicio_filho >= prazo:
                    motivo = "prazo"
                if motivo:
                    _matar_arvore([proc.pid], grupos, esperar=proc, extras=conhecidos)
                    break
            if recebidos:                                     # sinal no dono: a árvore inteira morre antes de a trava ser solta
                _matar_arvore([proc.pid], grupos, esperar=proc, primeiro=recebidos[0], extras=conhecidos)
        except BaseException:
            _matar_arvore([proc.pid], grupos, esperar=proc, carencia=1.0, extras=conhecidos)
            raise
        finally:
            if alimentador is not None:
                alimentador.parar = True
            for s, anterior in anteriores.items():
                try:
                    signal.signal(s, anterior)
                except (ValueError, OSError):
                    pass
            if grupo_proprio:
                if proc.poll() is not None:
                    # o filho direto saiu: netos que ficaram no grupo dele (um ffmpeg lançado por um script) não sobram
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass
                tr.esquecer_grupo(proc.pid)
        for c in coletores.values():
            c.join(timeout=5)
        if alimentador is not None:
            alimentador.join(timeout=5)
        rc = proc.returncode if proc.returncode is not None else -signal.SIGKILL
        codigo = SAIDA_VIGIA if motivo else (128 - rc if rc < 0 else rc)

        def saida(nome):
            if nome not in coletores:
                return None
            bruto = coletores[nome].conteudo()
            return bruto.decode("utf-8", errors="replace") if texto else bruto

        resultado = Resultado(comando, codigo, saida("stdout"), saida("stderr"), motivo, time.monotonic() - t_inicio, ocioso)
    # daqui para baixo a trava já foi solta
    if recebidos:
        if recebidos[0] == signal.SIGINT:
            raise KeyboardInterrupt
        raise Interrompido(recebidos[0])
    if alimentador is not None and alimentador.erro is not None:
        raise alimentador.erro
    return resultado


def executar(comando: list[str], espera_max: float | None = None, rotulo: str | None = None,
             silencioso: bool = False, inatividade: float | None = None, prazo: float | None = None, **popen) -> int:
    """Roda `comando` sob a trava e devolve o código de saída (128+sinal se morto por sinal; 124 se morto pelo
    vigia de `inatividade`/`prazo`). Entrada e saídas são as de quem chamou; SIGINT/SIGTERM/SIGHUP matam o grupo."""
    r = rodar(comando, rotulo=rotulo, espera_max=espera_max, silencioso=silencioso, inatividade=inatividade,
              prazo=prazo, entrada=popen.pop("entrada", HERDAR), **popen)
    if r.motivo and not silencioso:
        print(f"[trava] {descrever_vigia(r, rotulo or os.path.basename(str(comando[0])))}", file=sys.stderr, flush=True)
    return r.codigo


def descrever_vigia(r: Resultado, rotulo: str = "") -> str:
    """Frase pronta para o erro quando o vigia matou o comando (r.motivo ≠ None)."""
    quem = f"{rotulo}: " if rotulo else ""
    if r.motivo == "inatividade":
        return (f"{quem}sem progresso há {r.ocioso:.0f} s — o processo (e os filhos) foi morto e a trava liberada. "
                "Rode de novo; se repetir, o comando está esperando algo que não vem (entrada por pipe, rede, disco cheio).")
    if r.motivo == "prazo":
        return f"{quem}passou do prazo de execução depois de {r.duracao:.0f} s — o processo foi morto e a trava liberada."
    return f"{quem}código {r.codigo}"


def liberar_ocioso(se_ocioso: float = SE_OCIOSO_PADRAO, caminho: str | None = None, medir: float | None = None) -> dict:
    """Saída manual para dono travado: se a trava está ocupada e o dono está sem progresso há pelo menos
    `se_ocioso` segundos, mata o dono e a árvore dele. Devolve {'liberou', 'motivo', 'dono', 'ocioso_s', 'mortos'}.

    Ociosidade: a do batimento do dono (rodar/executar) ou, se ele não bate, a posse da trava há mais de
    `se_ocioso` + nenhuma CPU na árvore dele durante `medir` segundos (padrão: até 10 s)."""
    caminho = caminho or arquivo_da_trava()
    e = estado(caminho)
    if e["livre"]:
        return {"liberou": False, "motivo": "a trava já está livre", "dono": None, "ocioso_s": None, "mortos": 0}
    reg = e["dono"] or {}
    pid = reg.get("pid")
    if not isinstance(pid, int) or pid <= 1:
        return {"liberou": False, "motivo": "a trava está ocupada mas o registro do dono está ilegível; descubra o processo com "
                                            f"`lsof {caminho}` e encerre-o à mão", "dono": reg or None, "ocioso_s": None, "mortos": 0}
    if pid == os.getpid() or sob_trava(caminho) is not None:
        return {"liberou": False, "motivo": "este processo roda sob a própria trava; libere de fora", "dono": reg, "ocioso_s": None, "mortos": 0}
    grupos = [g.get("pgid") for g in reg.get("grupos") or [] if isinstance(g, dict) and isinstance(g.get("pgid"), int)]
    ocioso = e["ocioso_s"]
    if ocioso is None:
        posse = time.time() - reg["desde_epoch"] if isinstance(reg.get("desde_epoch"), (int, float)) else 0.0
        janela = max(1.0, min(10.0, se_ocioso)) if medir is None else max(0.2, medir)
        a = _cpu_da_arvore([pid], grupos)
        time.sleep(janela)
        b = _cpu_da_arvore([pid], grupos)
        parado = a is not None and b is not None and a[1] == b[1] and b[0] - a[0] < CPU_MINIMA * janela
        ocioso = posse if parado else 0.0
    if ocioso < se_ocioso:
        return {"liberou": False, "motivo": f"o dono teve progresso nos últimos {se_ocioso:g} s (ocioso há {ocioso:.0f} s); nada foi morto",
                "dono": reg, "ocioso_s": ocioso, "mortos": 0}
    mortos = _matar_arvore([pid], grupos)
    limite = time.monotonic() + 5
    while time.monotonic() < limite and not estado(caminho)["livre"]:
        time.sleep(0.1)
    return {"liberou": estado(caminho)["livre"], "motivo": f"dono sem progresso há {ocioso:.0f} s", "dono": reg,
            "ocioso_s": ocioso, "mortos": mortos}


AJUDA = """uso: trava.py [--espera-max SEG] [--inatividade SEG] [--prazo SEG] [--rotulo TEXTO] [--silencioso] -- <comando…>
     trava.py --estado [--json]
     trava.py --liberar [--se-ocioso SEG]

Executa <comando> sob a trava global da operação de vídeo (uma tarefa pesada por vez).

opções:
  --espera-max SEG   desiste (código 75) se ficar mais que SEG segundos na fila
  --inatividade SEG  mata o comando (código 124) se ele ficar SEG segundos sem progresso (CPU, arquivos, saída)
  --prazo SEG        mata o comando (código 124) se ele passar de SEG segundos de execução
  --rotulo TEXTO     nome curto da tarefa, mostrado a quem ficar esperando
  --silencioso       não escreve "aguardando trava…" no stderr
  --estado           mostra se a trava está livre (código 0) ou ocupada (código 1), e há quanto tempo o dono está parado
  --json             com --estado: imprime o registro em JSON
  --liberar          mata o dono da trava SE ele estiver sem progresso há --se-ocioso segundos (código 0 se liberou ou já estava livre)
  --se-ocioso SEG    ociosidade mínima para --liberar agir (padrão: 120)
  -h, --help         mostra esta ajuda

O código de saída é o do comando (128+N se morto pelo sinal N). O comando roda em grupo de processos próprio:
Ctrl-C, SIGTERM ou SIGHUP no trava.py matam o comando e os filhos dele antes de a trava ser solta.
A trava é reentrante: um comando travado pode chamar trava.py de novo sem entrar na fila.
"""

_COM_VALOR = ("--espera-max", "--rotulo", "--inatividade", "--prazo", "--se-ocioso")
_SEM_VALOR = ("--silencioso", "--estado", "--json", "--liberar", "-h", "--help")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        corte = argv.index("--")
        opcoes, comando = argv[:corte], argv[corte + 1:]
    else:
        # sem "--": tudo depois da última opção reconhecida é o comando
        opcoes, comando, i = [], [], 0
        while i < len(argv):
            a = argv[i]
            if a in _COM_VALOR:
                opcoes += argv[i:i + 2]
                i += 2
            elif a in _SEM_VALOR or a.startswith(tuple(o + "=" for o in _COM_VALOR)):
                opcoes.append(a)
                i += 1
            else:
                comando = argv[i:]
                break
    valores = {"--espera-max": None, "--inatividade": None, "--prazo": None, "--se-ocioso": SE_OCIOSO_PADRAO}
    rotulo, silencioso, so_estado, em_json, so_liberar = None, False, False, False, False
    i = 0
    while i < len(opcoes):
        a = opcoes[i]
        nome = a.split("=", 1)[0]
        if a in ("-h", "--help"):
            print(AJUDA, end="")
            return 0
        if a == "--silencioso":
            silencioso = True
        elif a == "--estado":
            so_estado = True
        elif a == "--json":
            em_json = True
        elif a == "--liberar":
            so_liberar = True
        elif nome in _COM_VALOR:
            valor = a.split("=", 1)[1] if "=" in a else (opcoes[i + 1] if i + 1 < len(opcoes) else "")
            i += 0 if "=" in a else 1
            if nome == "--rotulo":
                rotulo = valor
            else:
                try:
                    valores[nome] = float(valor)
                    if valores[nome] < 0:
                        raise ValueError
                except ValueError:
                    print(f"trava.py: {nome} precisa de um número de segundos (veio {valor!r})", file=sys.stderr)
                    return SAIDA_USO
        else:
            print(f"trava.py: opção desconhecida {a!r}\n\n{AJUDA}", file=sys.stderr, end="")
            return SAIDA_USO
        i += 1
    if so_estado:
        e = estado()
        if not e["livre"] and e["ocioso_s"] is None and isinstance((e.get("dono") or {}).get("pid"), int):
            reg = e["dono"]                              # dono sem batimento: amostra a CPU dele por 1 s
            grupos = [g.get("pgid") for g in reg.get("grupos") or [] if isinstance(g, dict)]
            a = _cpu_da_arvore([reg["pid"]], grupos)
            time.sleep(1.0)
            b = _cpu_da_arvore([reg["pid"]], grupos)
            if a is not None and b is not None:
                e["cpu_em_1s"] = round(b[0] - a[0], 2)
        if em_json:
            print(json.dumps(e, ensure_ascii=False))
            return 0 if e["livre"] else 1
        if e["livre"]:
            print("trava livre")
            return 0
        extra = f"; CPU do dono no último segundo: {e['cpu_em_1s']:.2f} s" if "cpu_em_1s" in e else ""
        print(f"trava ocupada ({_descrever_dono(e.get('dono') or {}, e.get('ocioso_s'))}{extra})")
        return 1
    if so_liberar:
        r = liberar_ocioso(se_ocioso=valores["--se-ocioso"])
        dono = _descrever_dono(r["dono"] or {}) if r["dono"] else ""
        if r["liberou"]:
            print(f"[trava] liberada: {r['motivo']} ({dono}); {r['mortos']} processo(s) encerrado(s)")
            return 0
        print(f"[trava] {r['motivo']}" + (f" ({dono})" if dono else ""))
        return 0 if r["motivo"].startswith("a trava já está livre") else 1
    if not comando:
        print("trava.py: faltou o comando.\n\n" + AJUDA, file=sys.stderr, end="")
        return SAIDA_USO
    try:
        return executar(comando, espera_max=valores["--espera-max"], rotulo=rotulo, silencioso=silencioso,
                        inatividade=valores["--inatividade"], prazo=valores["--prazo"])
    except TempoEsgotado as e:
        print(f"[trava] {e}", file=sys.stderr)
        return SAIDA_TEMPO_ESGOTADO
    except FileNotFoundError:
        print(f"[trava] comando não encontrado: {comando[0]}", file=sys.stderr)
        return 127
    except PermissionError:
        print(f"[trava] sem permissão para executar: {comando[0]}", file=sys.stderr)
        return 126
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
