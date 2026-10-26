#!/usr/bin/env python3
"""comum.py — o que buscar.py, baixar.py e tratar.py dividem: localizar o kit de direção de arte, achar o projeto,
ler chaves sem nunca imprimi-las e falar HTTP com educação (identificação, intervalo entre pedidos, nova tentativa,
lista de hosts permitidos por provedor). Não é para ser chamado direto."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import ipaddress
import json
import os
import re
import shutil
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
shutil.rmtree(Path(__file__).resolve().parent / "__pycache__", ignore_errors=True)     # a skill instalada não acumula .pyc

AQUI = Path(__file__).resolve().parent
VERSAO = "1.2.0"
SAIDA_OK, SAIDA_ERRO, SAIDA_SEM_DA, SAIDA_USO, SAIDA_SEM_REDE = 0, 1, 2, 64, 75


class Erro(Exception):
    """Erro com mensagem acionável: o que houve + `dica` (o que fazer) + código de saída."""

    def __init__(self, mensagem: str, dica: str | None = None, codigo: int = SAIDA_ERRO):
        super().__init__(mensagem)
        self.mensagem, self.dica, self.codigo = mensagem, dica, codigo

    def __str__(self) -> str:
        return self.mensagem if not self.dica else f"{self.mensagem}\n{self.dica}"


def diz(*partes, erro: bool = False) -> None:
    print(*partes, file=sys.stderr if erro else sys.stdout, flush=True)


# ─────────────────────────────────────────────────────────────── kit e projeto ──
def kit() -> Path:
    """Pasta do kit de direção de arte, achada pela posição desta skill (nunca por caminho embutido)."""
    k = AQUI.parents[1] / "video-direcao-de-arte" / "kit"
    if not (k / "da.py").is_file():
        k = Path("~/.claude/skills/video-direcao-de-arte/kit").expanduser()
    if not (k / "da.py").is_file():
        raise Erro("não achei o kit de direção de arte (video-direcao-de-arte/kit/da.py) ao lado desta skill.",
                   "Instale a skill video-direcao-de-arte em \"$CRIABR_SKILLS\"/ — sem ela nada é renderizado.")
    return k


def importar_kit():
    """(da, texto, video, trava) do kit. Importa só quando alguém precisa: registro.py e os testes de licença não dependem dele."""
    k = str(kit())
    if k not in sys.path:
        sys.path.insert(0, k)
    try:
        import da
        import texto
        import trava
        import video
    except ImportError as e:                                      # o python3 do sistema não tem Pillow nem numpy
        if (getattr(e, "name", "") or "").split(".")[0] not in ("PIL", "numpy"):
            raise
        raise Erro(f"este Python ({sys.executable}) não tem {'o Pillow' if e.name.startswith('PIL') else 'o numpy'}, de que o kit de direção de arte precisa.",
                   "Rode com o Python do Homebrew, que tem os dois: /opt/homebrew/bin/python3 "
                   f"\"{AQUI / Path(sys.argv[0]).name}\" …  (qualquer Python 3.10+ com Pillow e numpy serve).")
    return da, texto, video, trava


def carregar_da(projeto=None):
    """Passo 0: a DA do projeto (ou Erro com código 2 e o caminho para criá-la). Devolve (d, módulo da)."""
    da, _texto, _video, _trava = importar_kit()
    try:
        d = da.carregar(projeto) if projeto else da.carregar()
    except da.SemDA as e:
        raise Erro(str(e.mensagem), "Este projeto não tem direção de arte. Pare aqui e crie uma com a skill video-direcao-de-arte "
                   f"({da.DA_CLI} init \"<pasta>\" --nome \"…\" --base <preset>); sem DA não se busca, baixa nem trata b-roll.", SAIDA_SEM_DA)
    except da.DAErro as e:
        raise Erro(str(e), codigo=getattr(e, "codigo", SAIDA_ERRO) or SAIDA_ERRO)
    return d, da


def video_ops_home() -> Path:
    v = os.environ.get("VIDEO_OPS_HOME")
    return Path(v).expanduser() if v else Path.home() / ".config" / "video-ops"


# ───────────────────────────────────────────────────────────────────── chaves ──
_SEGREDOS: set[str] = set()


def _ler_env(arq: Path) -> dict:
    valores = {}
    try:
        linhas = arq.read_text(encoding="utf-8").splitlines()
    except OSError:
        return valores
    for linha in linhas:
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, valor = linha.removeprefix("export ").split("=", 1)
        valores[nome.strip()] = valor.strip().strip("'\"")
    return valores


def chave(nome: str) -> str | None:
    """Chave de API pelo nome (variável de ambiente; senão $VIDEO_OPS_HOME/chaves.env). O valor nunca é impresso:
    tudo o que sai por `mascarar` troca a chave por ***."""
    valor = os.environ.get(nome) or _ler_env(video_ops_home() / "chaves.env").get(nome)
    valor = (valor or "").strip()
    if valor:
        _SEGREDOS.add(valor)
    return valor or None


def config(nome: str) -> str | None:
    """Configuração não secreta (ex.: VIDEO_OPS_CONTATO): ambiente ou chaves.env."""
    return ((os.environ.get(nome) or _ler_env(video_ops_home() / "chaves.env").get(nome) or "").strip()) or None


def sem_segredos(texto) -> str:
    """Troca por *** cada chave lida nesta execução, em qualquer grafia de URL (crua, %XX, com + no lugar do espaço).
    Não mexe em mais nada: um `token=` que não é segredo do usuário (endereço assinado de um CDN) fica como está."""
    s = str(texto)
    for segredo in _SEGREDOS:
        if not segredo:
            continue
        formas = {segredo, urllib.parse.quote(segredo, safe=""), urllib.parse.quote_plus(segredo), urllib.parse.quote(segredo)}
        for forma in sorted(formas, key=len, reverse=True):
            s = s.replace(forma, "***") if forma == segredo else re.sub(re.escape(forma), "***", s, flags=re.I)
    return s


def mascarar(texto) -> str:
    """Tira chaves de qualquer texto que vá para a tela ou para log: as chaves conhecidas (`sem_segredos`) e, por
    garantia, o valor de todo parâmetro com nome de credencial (key=, token=…) — numa mensagem de erro ninguém precisa dele."""
    return re.sub(r"(?i)([?&](?:key|api_key|apikey|token|access_token)=)[^&\s\"'<>]+", r"\1***", sem_segredos(texto))


def mascarar_dados(dados):
    """`sem_segredos` em toda string de uma estrutura (dict, lista) — é por aqui que passa tudo o que vai para o disco ou
    para --json: cache de respostas, resultado da busca, plano de download. Um provedor que devolva a chave dentro de um
    campo (a URL do pedido ecoada na resposta, por exemplo) não a faz chegar a arquivo nenhum."""
    if isinstance(dados, str):
        return sem_segredos(dados)
    if isinstance(dados, dict):
        return {(sem_segredos(k) if isinstance(k, str) else k): mascarar_dados(v) for k, v in dados.items()}
    if isinstance(dados, (list, tuple)):
        return [mascarar_dados(v) for v in dados]
    return dados


def sem_controle(texto) -> str:
    """Uma linha de texto para o terminal: caractere de controle ou de formatação (quebra de linha, ESC, inversor de
    direção) vira espaço. Título, autor e nome de arquivo vêm de terceiros: sem isto, um nome com \\n forja uma linha do
    plano e uma sequência ANSI repinta o terminal."""
    import unicodedata
    return " ".join("".join(" " if unicodedata.category(ch)[0] == "C" else ch for ch in str(texto if texto is not None else "")).split())


# ─────────────────────────────────────────────────────────────────────── HTTP ──
def agente() -> str:
    """User-Agent descritivo: a Wikimedia exige nome/versão e contato; o Internet Archive pede nome, versão e, para
    agente de IA, o modelo. O contato é do usuário (VIDEO_OPS_CONTATO: e-mail ou URL dele) — nunca inventado aqui."""
    contato = re.sub(r"[^\x20-\x7e]", "", config("VIDEO_OPS_CONTATO") or "") or "contato nao configurado: defina VIDEO_OPS_CONTATO"
    modelo = re.sub(r"[^A-Za-z0-9._:-]", "", os.environ.get("VIDEO_OPS_AGENTE") or "")
    return f"video-broll/{VERSAO} (bot de pesquisa de b-roll, uso pessoal; {contato}) Python-urllib/{sys.version_info.major}.{sys.version_info.minor}" + (f" ({modelo})" if modelo else "")


def identificacao() -> dict:
    """O que o User-Agent desta execução leva: {'contato': bool, 'agente': bool}. Sem contato a Wikimedia não é consultada
    (a política dela exige); sem o modelo do agente o Internet Archive é consultado com aviso."""
    return {"contato": bool(config("VIDEO_OPS_CONTATO")), "agente": bool(re.sub(r"[^A-Za-z0-9._:-]", "", os.environ.get("VIDEO_OPS_AGENTE") or ""))}


def _local_permitido() -> bool:
    return os.environ.get("VIDEO_BROLL_PERMITIR_LOCAL") == "1"          # só para a suíte de testes (servidor em 127.0.0.1)


def host_permitido(url: str, hosts) -> bool:
    """hosts = sufixos aceitos ("nasa.gov" aceita images-assets.nasa.gov); None = qualquer host PÚBLICO em https."""
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower()
    if not host:
        return False
    local = host in ("127.0.0.1", "localhost", "::1")
    if local:
        return _local_permitido()
    if p.scheme != "https":
        return False
    if hosts is None:
        try:
            for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
                ip = ipaddress.ip_address(info[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return False
        except (OSError, ValueError):
            return False
        return True
    return any(host == h or host.endswith("." + h) for h in hosts)


def url_limpa(url: str) -> str:
    """https, caminho codificado (a NASA devolve http:// e espaços no caminho) e sem parâmetros de rastreio (utm_*)."""
    p = urllib.parse.urlsplit(str(url).strip())
    esquema = "https" if p.scheme == "http" and (p.hostname or "") not in ("127.0.0.1", "localhost") else p.scheme
    caminho = urllib.parse.quote(urllib.parse.unquote(p.path), safe="/~()!*',;:@+$=&")
    consulta = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")])
    return urllib.parse.urlunsplit((esquema, p.netloc, caminho, consulta, ""))


class _SemRedirecionarParaFora(urllib.request.HTTPRedirectHandler):
    """Segue redirecionamento só para host permitido (o Internet Archive redireciona para iaNNNNNN.us.archive.org)."""

    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_permitido(newurl, self.hosts):
            raise urllib.error.HTTPError(req.full_url, code, f"redirecionamento para host fora da lista: {urllib.parse.urlsplit(newurl).hostname}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Http:
    """Cliente mínimo e educado. Um por execução; guarda o instante do último pedido a cada host."""

    def __init__(self, prazo: float = 30.0, tentativas: int = 3):
        self.prazo, self.tentativas = prazo, tentativas
        self._ultimo: dict[str, float] = {}
        self.pedidos = 0
        self.limites: dict[str, dict] = {}            # host → cabeçalhos de cota vistos por último

    def _esperar(self, host: str, intervalo: float) -> None:
        falta = self._ultimo.get(host, 0) + intervalo - time.monotonic()
        if falta > 0:
            time.sleep(falta)
        self._ultimo[host] = time.monotonic()

    def abrir(self, url: str, hosts, cabecalhos: dict | None = None, intervalo: float = 1.0, metodo: str = "GET"):
        """Abre a URL (objeto de resposta). Erros viram `Erro` com a URL mascarada; 429/503 respeitam Retry-After."""
        if not host_permitido(url, hosts):
            raise Erro(f"endereço recusado: {mascarar(url)[:160]} (só https e só os hosts do provedor).",
                       "Se o provedor mudou de domínio, confira a documentação oficial e atualize `hosts` em provedores.py.")
        host = urllib.parse.urlsplit(url).hostname or ""
        abridor = urllib.request.build_opener(_SemRedirecionarParaFora(hosts))
        cab = {"User-Agent": agente(), "Accept-Encoding": "gzip", **(cabecalhos or {})}
        ultimo = None
        for tentativa in range(1, self.tentativas + 1):
            self._esperar(host, intervalo)
            self.pedidos += 1
            try:
                r = abridor.open(urllib.request.Request(url, headers=cab, method=metodo), timeout=self.prazo)
                cota = {k.lower(): v for k, v in r.headers.items() if "ratelimit" in k.lower()}
                if cota:
                    self.limites[host] = cota
                return r
            except urllib.error.HTTPError as e:
                if e.code in (429, 503) and tentativa < self.tentativas:
                    e.close()
                    try:
                        pausa = float(e.headers.get("Retry-After") or 0)
                    except ValueError:
                        pausa = 0.0
                    pausa = pausa or 2.0 * tentativa
                    if pausa > 30:
                        raise Erro(f"{host} pediu para esperar {int(pausa)} s (HTTP {e.code}: limite de pedidos).",
                                   "Tente de novo depois desse tempo; o cache de broll/_busca/ evita repetir consultas.")
                    time.sleep(pausa)
                    ultimo = e
                    continue
                corpo = ""
                try:
                    corpo = e.read(300).decode("utf-8", "replace")
                except OSError:
                    pass
                e.close()
                if "<" in corpo[:40]:                              # página HTML de erro: não ajuda ninguém
                    corpo = ""
                corpo = " ".join(corpo.split())
                raise Erro(f"{host} respondeu HTTP {e.code} em {mascarar(url)[:140]}: {mascarar(corpo).strip()[:200] or e.reason}",
                           {401: "Chave de API ausente ou recusada: confira a variável de ambiente ou chaves.env (references/fontes.md).",
                            403: "Acesso negado: confira a chave e, na Wikimedia, o contato em VIDEO_OPS_CONTATO (ela bloqueia cliente sem identificação).",
                            404: "O item saiu do ar ou o endereço mudou: refaça a busca com --sem-cache.",
                            429: "Limite de pedidos do provedor: espere e use o cache."}.get(e.code))
            except (urllib.error.URLError, TimeoutError, ConnectionError, socket.timeout) as e:
                ultimo = e
                if tentativa < self.tentativas:
                    time.sleep(1.5 * tentativa)
        raise Erro(f"sem resposta de {host} depois de {self.tentativas} tentativa(s): {mascarar(getattr(ultimo, 'reason', ultimo))}",
                   "Confira a conexão. Buscas já feitas continuam em broll/_busca/ (o cache vale 24 h).", SAIDA_SEM_REDE)

    @staticmethod
    def _corpo(r, teto: int) -> bytes:
        dados = r.read(teto + 1)
        if len(dados) > teto:
            raise Erro(f"resposta maior que {teto // 1024} KB em {mascarar(r.geturl())[:120]}: não parece uma resposta de API.")
        return gzip.decompress(dados) if r.headers.get("Content-Encoding") == "gzip" else dados

    def json(self, url: str, hosts, cabecalhos: dict | None = None, intervalo: float = 1.0, teto: int = 8 << 20):
        with self.abrir(url, hosts, {"Accept": "application/json", **(cabecalhos or {})}, intervalo) as r:
            bruto = self._corpo(r, teto)
        try:
            return json.loads(bruto.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise Erro(f"{urllib.parse.urlsplit(url).hostname} devolveu algo que não é JSON: {mascarar(bruto[:120].decode('utf-8', 'replace'))!r}",
                       "A API pode ter mudado: confira o endpoint em references/fontes.md contra a documentação oficial.")

    def bytes(self, url: str, hosts, intervalo: float = 0.3, teto: int = 2 << 20) -> bytes:
        """Arquivo pequeno (miniatura) inteiro na memória, com teto."""
        with self.abrir(url, hosts, {"Accept": "image/*,*/*;q=0.8"}, intervalo) as r:
            return self._corpo(r, teto)

    def tamanho(self, url: str, hosts, intervalo: float = 0.5) -> dict:
        """Tamanho e tipo sem baixar: HEAD e, se o servidor não informar, GET de 1 byte (Range). → {bytes, tipo, retoma, url_final}"""
        info = {"bytes": None, "tipo": None, "retoma": False, "url_final": url}
        try:
            with self.abrir(url, hosts, {"Accept-Encoding": "identity"}, intervalo, metodo="HEAD") as r:
                info.update(bytes=int(r.headers["Content-Length"]) if r.headers.get("Content-Length") else None,
                            tipo=(r.headers.get("Content-Type") or "").split(";")[0].strip() or None,
                            retoma=(r.headers.get("Accept-Ranges") or "").lower() == "bytes", url_final=r.geturl())
        except Erro:
            pass
        if info["bytes"] is None:
            with self.abrir(url, hosts, {"Accept-Encoding": "identity", "Range": "bytes=0-0"}, intervalo) as r:
                faixa = r.headers.get("Content-Range") or ""
                m = re.search(r"/(\d+)$", faixa)
                info.update(bytes=int(m.group(1)) if m else (int(r.headers["Content-Length"]) if r.status == 200 and r.headers.get("Content-Length") else None),
                            tipo=(r.headers.get("Content-Type") or "").split(";")[0].strip() or None, retoma=bool(m), url_final=r.geturl())
        return info

    def resolver(self, url: str, hosts, intervalo: float = 0.5) -> str:
        """Endereço FINAL de um GET depois dos redirecionamentos, cada salto conferido contra `hosts` (pede 1 byte, não o
        arquivo). É o que se entrega a quem vai ler a URL por fora deste cliente (o ffmpeg do --trecho)."""
        with self.abrir(url, hosts, {"Accept-Encoding": "identity", "Accept": "*/*", "Range": "bytes=0-0"}, intervalo) as r:
            final = r.geturl()
        if not host_permitido(final, hosts):
            raise Erro(f"o endereço final do arquivo saiu dos hosts do provedor: {mascarar(final)[:140]}",
                       "O provedor redirecionou para fora do que a documentação dele prevê; não foi seguido.")
        return final

    def baixar(self, url: str, destino: Path, hosts, teto: int, esperado: int | None = None, progresso=None) -> dict:
        """Baixa para `destino` (arquivo provisório), retomando de onde parou se ele já existe e o servidor aceita Range.
        Para se passar de `teto` bytes ou do tamanho `esperado` (o do plano). Devolve {bytes, sha256, retomado_de}. O arquivo
        fica em `destino`; quem chama renomeia. Só o download INCOMPLETO deixa o provisório no disco (para retomar): tamanho
        diferente do anunciado ou teto estourado apagam o que chegou — repetir o comando não resolveria."""
        destino.parent.mkdir(parents=True, exist_ok=True)
        ja = destino.stat().st_size if destino.is_file() else 0
        if esperado and ja > esperado:
            destino.unlink()
            ja = 0
        cab = {"Accept-Encoding": "identity", "Accept": "*/*"}
        if ja:
            cab["Range"] = f"bytes={ja}-"

        def definitivo(mensagem: str, dica: str) -> Erro:           # erro que repetir o comando não resolve: o provisório é apagado
            e = Erro(mensagem, dica)
            e.apagar_parcial = True
            return e

        def outro_arquivo(chegou: int) -> Erro:
            return definitivo(f"o servidor entregou um arquivo de tamanho diferente do planejado ({tamanho_legivel(chegou)} em vez de "
                              f"{tamanho_legivel(esperado)}): não é o arquivo que o plano mostrou. Nada foi guardado.",
                              "Refaça o plano (baixar.py sem --confirmar), mostre-o de novo ao usuário e só então confirme.")
        try:
            if not (esperado and ja == esperado):
                with self.abrir(url, hosts, cab, 0.5) as r:
                    if ja and r.status != 206:                       # o servidor ignorou o Range: recomeça
                        ja = 0
                    total = ja + int(r.headers["Content-Length"]) if r.headers.get("Content-Length") else esperado
                    if total and total > teto:
                        raise definitivo(f"o arquivo tem {total / 1e6:.1f} MB, acima do teto de {teto / 1e6:.0f} MB.",
                                         "Escolha uma versão menor (--altura), baixe só um trecho (--trecho A-B) ou suba o teto (--teto-mb).")
                    if esperado and total and total != esperado:
                        raise outro_arquivo(total)
                    with open(destino, "ab" if ja else "wb") as f:
                        feito = ja
                        while True:
                            bloco = r.read(1 << 18)
                            if not bloco:
                                break
                            feito += len(bloco)
                            if feito > teto:
                                raise definitivo(f"o download passou do teto de {teto / 1e6:.0f} MB e foi interrompido (o servidor não informou o tamanho). Nada foi guardado.",
                                                 "Suba o teto com --teto-mb se o arquivo for mesmo esse.")
                            if esperado and feito > esperado:
                                raise outro_arquivo(feito)
                            f.write(bloco)
                            if progresso:
                                progresso(feito, total)
        except Erro as e:
            if getattr(e, "apagar_parcial", False):                  # o que chegou não serve para retomar
                destino.unlink(missing_ok=True)
            raise
        except (OSError, http.client.HTTPException) as e:            # a conexão caiu no meio do corpo: o provisório fica para a retomada
            raise Erro(f"a conexão caiu durante o download ({type(e).__name__}).", "Rode o mesmo comando de novo: ele retoma de onde parou.", SAIDA_SEM_REDE)
        tamanho = destino.stat().st_size
        if esperado and tamanho > esperado:
            destino.unlink(missing_ok=True)
            raise outro_arquivo(tamanho)
        if esperado and tamanho != esperado:
            raise Erro(f"download incompleto: {tamanho} de {esperado} bytes.", "Rode o mesmo comando de novo: ele retoma de onde parou.", SAIDA_SEM_REDE)
        h = hashlib.sha256()
        with open(destino, "rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        return {"bytes": tamanho, "sha256": h.hexdigest(), "retomado_de": ja}


# ──────────────────────────────────────────────────────────── pequenas utilidades ──
def slug(texto: str, maximo: int = 48) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii").lower()
    return (re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "busca")[:maximo].strip("-")


def tamanho_legivel(n) -> str:
    if n is None:
        return "tamanho ?"
    return f"{n / 1e6:.1f} MB".replace(".", ",") if n >= 1e5 else f"{n / 1e3:.0f} KB"


def duracao_legivel(s) -> str:
    if s is None:
        return "?"
    s = float(s)
    if s >= 3600:
        return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{int(s % 60):02d}"
    return f"{int(s // 60)}:{int(s % 60):02d}" if s >= 60 else f"{s:.1f} s".replace(".", ",")


def segundos(valor) -> float | None:
    """"0:03:20", "12:25", "750.65", "12.5 s" → segundos; o que não entender vira None."""
    if valor is None:
        return None
    t = str(valor).strip().lower().removesuffix("s").strip()
    try:
        if ":" in t:
            total = 0.0
            for parte in t.split(":"):
                total = total * 60 + float(parte)
            return total
        return float(t)
    except ValueError:
        return None


_ARGPARSE_PT = (("the following arguments are required", "faltou informar"), ("unrecognized arguments", "opção desconhecida"),
                ("invalid choice", "valor inválido"), ("choose from", "opções"), ("expected one argument", "faltou o valor"),
                ("expected at least one argument", "faltou pelo menos um valor"), ("invalid float value", "número inválido"),
                ("invalid int value", "número inteiro inválido"), ("argument ", "argumento "), ("not allowed with", "não pode vir junto com"),
                ("one of the arguments", "um destes argumentos"), ("is required", "é obrigatório"))


class Parser(argparse.ArgumentParser):
    """argparse com erro de uso em português, código 64 e sem traceback."""

    def error(self, message):
        for en, pt in _ARGPARSE_PT:
            message = message.replace(en, pt)
        print(f"erro de uso: {message}\nVeja: {self.prog} --help", file=sys.stderr)
        sys.exit(SAIDA_USO)

    def format_help(self):
        return super().format_help().replace("usage:", "uso:").replace("positional arguments:", "argumentos:").replace("options:", "opções:") \
            .replace("show this help message and exit", "mostra esta ajuda e sai")


def rodar(principal) -> int:
    """Executa a função principal de um script traduzindo exceções em mensagem de uma linha + código de saída."""
    try:
        return int(principal() or 0)
    except Erro as e:
        print(f"erro: {mascarar(e)}", file=sys.stderr)
        return e.codigo
    except KeyboardInterrupt:
        print("interrompido.", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except Exception as e:                                        # erro do kit (DAErro) ou do registro: mensagem, não traceback
        if os.environ.get("DA_DEBUG") == "1":
            raise
        codigo = getattr(e, "codigo", None)
        if codigo is None:
            print(f"erro interno: {type(e).__name__}: {mascarar(e)} (DA_DEBUG=1 mostra o traceback)", file=sys.stderr)
            return SAIDA_ERRO
        print(f"erro: {mascarar(e)}", file=sys.stderr)
        return int(codigo or SAIDA_ERRO)
