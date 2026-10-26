#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ponta_a_ponta.py — a skill inteira sobre vídeo de verdade: 3 presets × 3 estilos × (vertical + horizontal).

    python3 ponta_a_ponta.py --video fala.mp4 --palavras fala.palavras.json --saida "/pasta de teste" [--prova PASTA] \\
            [--inicio 4.1 --fim 7.1] [--presets lab-ia,neon-shorts,editorial-claro] [--longo v.mp4 --longo-palavras p.json]

Para cada preset e cada estilo cria um projeto (da init + legenda.estilo/animacao trocados no da.json do PROJETO DE
TESTE), queima 3 s em 540×960 (recorte pelo kit) e em 960×540, confere mídia, zona segura, carimbo e .srt, e monta as
folhas de contato em <saida>/prova/ (ou em --prova). Com --longo mede o desempenho no vídeo inteiro (a saída é apagada depois).
Não entra na suíte unittest: precisa de vídeo real e leva cerca de um minuto. Defina VIDEO_OPS_HOME para a área de teste.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import comum  # noqa: E402
import legendar  # noqa: E402

ESTILOS = ("karaoke", "palavra", "bloco")
# animação de cada combinação: cobre pop no lugar (karaokê com caixa e com contorno), pop inteiro, fade e nenhuma
ANIMACAO = {("lab-ia", "karaoke"): "pop", ("lab-ia", "palavra"): "fade", ("lab-ia", "bloco"): "pop",
            ("neon-shorts", "karaoke"): "pop", ("neon-shorts", "palavra"): "pop", ("neon-shorts", "bloco"): "fade",
            ("editorial-claro", "karaoke"): "fade", ("editorial-claro", "palavra"): "nenhuma", ("editorial-claro", "bloco"): "fade"}
FORMATOS = {"vertical": "540x960", "horizontal": "960x540"}


def criar_projeto(raiz: Path, preset: str, estilo: str, animacao: str | None) -> Path:
    da, _, _, _ = comum.kit()
    pasta = raiz / f"{preset} {estilo}"
    da.iniciar(pasta, nome=f"Teste {preset} {estilo}", base=preset, forcar=(pasta / "da" / "da.json").is_file())
    arq = pasta / "da" / "da.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    dados["legenda"]["estilo"] = estilo
    if animacao:
        dados["legenda"]["animacao"] = animacao
    arq.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return pasta


def montar_cli():
    ap = comum.Analisador(
        prog="ponta_a_ponta.py",
        description="A skill inteira sobre vídeo de verdade: para cada preset e cada estilo (karaoke, palavra, bloco) cria um projeto de\n"
                    "teste, queima um trecho em 540×960 (recorte pelo kit) e em 960×540, confere mídia, zona segura, carimbo e .srt e\n"
                    "monta as folhas de contato. Não entra na suíte unittest: precisa de vídeo real e leva cerca de um minuto.",
        epilog="Defina VIDEO_OPS_HOME para dentro da área de teste. Códigos de saída: 0 tudo certo · 1 alguma combinação falhou · 64 uso incorreto.")
    ap.add_argument("--video", required=True, metavar="ARQ", help="vídeo com fala (ex.: uma pessoa falando, 1080p)")
    ap.add_argument("--palavras", required=True, metavar="ARQ", help='transcrição palavra a palavra do vídeo: [{"a", "b", "w", "p"}]')
    ap.add_argument("--saida", required=True, metavar="PASTA", help="pasta de teste, criada se não existir (pode ter espaço no nome)")
    ap.add_argument("--prova", metavar="PASTA", help="onde gravar as folhas de contato e o relatorio.json (padrão: <saida>/prova)")
    ap.add_argument("--inicio", type=float, default=4.1, metavar="S", help="início do trecho, em segundos (padrão 4.1)")
    ap.add_argument("--fim", type=float, default=7.1, metavar="S", help="fim do trecho (padrão 7.1; mantenha 3 s ou menos)")
    ap.add_argument("--presets", default="lab-ia,neon-shorts,editorial-claro", metavar="A,B,C", help="presets da DA, separados por vírgula (padrão: lab-ia,neon-shorts,editorial-claro)")
    ap.add_argument("--foco", metavar="X,Y", help="centro do recorte vertical em frações do vídeo de origem (ex.: 0.3,0.4)")
    ap.add_argument("--longo", metavar="ARQ", help="vídeo longo para medir o desempenho (legendado inteiro; a saída é apagada depois)")
    ap.add_argument("--longo-palavras", metavar="ARQ", help="transcrição palavra a palavra do vídeo longo")
    return ap


def main(argv=None) -> int:
    args = montar_cli().parse_args(argv)
    for rotulo, arq in (("--video", args.video), ("--palavras", args.palavras), ("--longo", args.longo), ("--longo-palavras", args.longo_palavras)):
        if arq and not Path(arq).expanduser().is_file():
            raise comum.Erro(f"{rotulo}: arquivo não encontrado: {arq}", "Confira o caminho (use aspas se tiver espaço).", 64)
    if bool(args.longo) != bool(args.longo_palavras):
        raise comum.Erro("--longo e --longo-palavras andam juntos: o vídeo longo e a transcrição dele.", codigo=64)
    if args.fim <= args.inicio:
        raise comum.Erro(f"--fim ({args.fim}) precisa ser maior que --inicio ({args.inicio}).", codigo=64)
    args.video, args.palavras = str(Path(args.video).expanduser().resolve()), str(Path(args.palavras).expanduser().resolve())
    da, _, video, _ = comum.kit()
    saida = Path(args.saida).expanduser().resolve()
    prova = Path(args.prova).expanduser().resolve() if args.prova else saida / "prova"
    prova.mkdir(parents=True, exist_ok=True)
    presets = [p.strip() for p in args.presets.split(",") if p.strip()]
    resultados, falhas = [], []
    celulas: dict = {"vertical": [], "horizontal": []}
    for preset in presets:
        for estilo in ESTILOS:
            animacao = ANIMACAO.get((preset, estilo))
            pasta = criar_projeto(saida / "projetos", preset, estilo, animacao)
            for n, (fmt, tam) in enumerate(FORMATOS.items()):
                alvo = pasta / "legendas" / f"corte {fmt}.mp4"
                t0 = time.time()
                try:
                    if n == 0:                                   # vertical pela CLI (como outra skill chamaria)
                        r = subprocess.run([sys.executable, str(SCRIPTS / "legendar.py"), "--video", args.video, "--palavras", args.palavras,
                                            "--saida", str(alvo), "--formato", tam, "--inicio", str(args.inicio), "--fim", str(args.fim), "--json",
                                            *(["--foco", args.foco] if args.foco else [])],
                                           cwd=pasta, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)
                        if r.returncode != 0:
                            raise RuntimeError(f"legendar.py saiu com {r.returncode}: {r.stderr.strip()[-400:]}")
                        res = json.loads(r.stdout)
                    else:                                        # horizontal pela função importável
                        res = legendar.legendar(args.video, args.palavras, alvo, formato=tam, inicio=args.inicio, fim=args.fim, projeto=pasta)
                        res = json.loads(json.dumps(res, default=str))
                    s = video.sondar(alvo)
                    L, A = (int(x) for x in tam.split("x"))
                    conf = da.conferir_carimbo([alvo], da=str(pasta))
                    srt = Path(res["srt"]).read_text(encoding="utf-8")
                    problemas = []
                    if (s["largura"], s["altura"]) != (L, A):
                        problemas.append(f"tamanho {s['largura']}×{s['altura']}")
                    if abs(s["duracao"] - (args.fim - args.inicio)) > 0.12:
                        problemas.append(f"duração {s['duracao']:.2f}")
                    if not s["tem_audio"]:
                        problemas.append("sem áudio")
                    if not res["conferencia"]["zona"]["ok"]:
                        problemas.append("fora da zona")
                    if not conf["ok"]:
                        problemas.append("carimbo: " + conf["pecas"][0]["estado"])
                    if "-->" not in srt:
                        problemas.append("srt vazio")
                    doc = json.loads(Path(res["cues_json"]).read_text(encoding="utf-8"))
                    # dois quadros para a folha: o 1º quadro de uma palavra (pega o pop/fade) e o meio de outra
                    pal = [w for c in doc["cues"] for w in c["palavras"]]
                    w1, w2 = pal[min(2, len(pal) - 1)], pal[min(len(pal) - 1, len(pal) * 2 // 3)]
                    tempos = [w1["a"] + 0.5 / float(s["fps"]), (w2["a"] + w2["b"]) / 2]
                    for k, t in enumerate(tempos):
                        q = video.extrair_quadro(alvo, t, prova / f"_q {preset} {estilo} {fmt} {k}.png", largura=360 if fmt == "vertical" else 640)
                        celulas[fmt].append((q, f"{preset} · {estilo}+{res['animacao']} · {t:.2f} s"))
                    resultados.append({"preset": preset, "estilo": estilo, "animacao": res["animacao"], "formato": fmt, "tamanho": tam,
                                       "cues": res["cues"], "estados": res["estados"], "tempo_s": round(time.time() - t0, 2),
                                       "menor_tamanho_fracao": res["conferencia"]["zona"]["menor_tamanho_fracao"],
                                       "contraste_pior": (res["conferencia"].get("contraste") or {}).get("pior"),
                                       "bytes": alvo.stat().st_size, "problemas": problemas})
                    print(f"{'ok  ' if not problemas else 'FALHA'} {preset:16} {estilo:8} {fmt:10} {res['cues']} cues {res['estados']:3} estados "
                          f"{time.time() - t0:5.1f} s  contraste {resultados[-1]['contraste_pior']}  {'; '.join(problemas)}")
                    if problemas:
                        falhas.append((preset, estilo, fmt, problemas))
                except Exception as e:  # noqa: BLE001
                    falhas.append((preset, estilo, fmt, [str(e)]))
                    print(f"FALHA {preset:16} {estilo:8} {fmt:10} {e}")
    for fmt, itens in celulas.items():
        if itens:
            d = da.carregar(str(saida / "projetos" / f"{presets[0]} {ESTILOS[0]}"))
            video.folha_de_contato([q for q, _ in itens], [leg for _, leg in itens], prova / f"folha {fmt}.png",
                                   colunas=6 if fmt == "vertical" else 3, largura_celula=360 if fmt == "vertical" else 640, da_obj=d,
                                   titulo=f"video-legendas — {fmt}: 3 presets × 3 estilos (1º quadro da palavra · meio da palavra)")
            for q, _ in itens:
                q.unlink(missing_ok=True)
    desempenho = None
    if args.longo and args.longo_palavras:
        da.iniciar(saida / "projetos" / f"{presets[0]} desempenho", nome=f"Teste {presets[0]} desempenho", base=presets[0])   # a DA do preset, sem trocar nada
        pasta = saida / "projetos" / f"{presets[0]} desempenho"
        alvo = pasta / "legendas" / "longo inteiro.mp4"
        t0 = time.time()
        res = legendar.legendar(args.longo, args.longo_palavras, alvo, projeto=pasta)
        parede = time.time() - t0
        s = video.sondar(alvo)
        desempenho = {"video": Path(args.longo).name, "tamanho": f"{s['largura']}x{s['altura']}", "fps": str(s["fps"]), "duracao_s": round(s["duracao"], 2),
                      "cues": res["cues"], "palavras": res["palavras"], "estados": res["estados"], "parede_s": round(parede, 1),
                      "fator_tempo_real": round(parede / s["duracao"], 2), "bytes": alvo.stat().st_size}
        print("desempenho:", json.dumps(desempenho, ensure_ascii=False))
        for t in (10.0, 40.0):
            video.extrair_quadro(alvo, t, prova / f"_longo {int(t)}.png", largura=640)
        video.folha_de_contato([prova / "_longo 10.png", prova / "_longo 40.png"], ["longo · 10 s", "longo · 40 s"], prova / "folha longo.png",
                               colunas=2, largura_celula=640, da_obj=da.carregar(str(pasta)), titulo="video-legendas — vídeo de 75 s inteiro (1280×720)")
        for t in (10, 40):
            (prova / f"_longo {t}.png").unlink(missing_ok=True)
        alvo.unlink()                                            # saída grande: fica só a medida
        Path(str(alvo) + ".da.json").unlink(missing_ok=True)
    (prova / "relatorio.json").write_text(json.dumps({"gerado_em": da.agora_iso(), "resultados": resultados, "desempenho": desempenho,
                                                      "falhas": [list(f) for f in falhas]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(resultados)} render(s), {len(falhas)} falha(s). Folhas e relatório em {prova}")
    return 1 if falhas else 0


if __name__ == "__main__":
    import cues as modulo_cues
    sys.exit(modulo_cues.executar_cli(main))
