"""plano.py — a decupagem aprovada em forma de dados: montagem (chunks), mapa de tempo bruto→final, enquadramento do JP
e eventos de motion ancorados na fala. Compartilhado por montagem.py, motions.py e legendar_final.py.
Tempos de A (IMG_5666), B (IMG_5676) e N (vídeo do Nikolas) são do arquivo bruto; out() converte para o vídeo final."""
import os
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
SKILLS = Path(os.environ.get("CRIABR_SKILLS", "D:/EDIÇÃO DE VÍDEO/.claude/skills"))   # skills da crIAbr (também ligadas no Studio)
FONTES = {
    "A": PROJ / "bruto" / "IMG_5666.MOV",
    "B": PROJ / "bruto" / "IMG_5676.mov",
    "N": PROJ / "broll" / "bruto" / "nikolas-nordeste" / "nikolas-nordeste.mp4",
}
FPS = 30
W, H = 1080, 1920
ROSTO = (0.488, 0.47)          # ponto de ancoragem do zoom no bruto do JP (olhos ~ centro), medido com YuNet
CAUDA = 10.0                   # segundos de preto depois do último quadro do JP: a cartela final (Remotion) cobre

# (fonte, entrada, saída, dissolve_antes): dissolve com o chunk anterior, em segundos (0 = corte)
# v2 (22/10, pedido do JP): a fala corre inteira, sem as falas do vídeo do Nikolas no meio; só sai o "21, 8" e há a troca de take
# (a pausa com whoosh no 0:03 saiu em 24/10: os efeitos sonoros o JP põe à mão)
TRECHOS = [
    ("A", 0.00, 139.00),
    ("A", 140.45, 153.20),    # corte do "21, 8" (fala fica "…em Apocalipse. Os mornos…"); o zoom muda no corte
    ("B", 0.00, 29.36),       # troca de take: corte seco, com outro enquadramento
]
# respiros longos encurtados (24/10, "decupar muito pouco"): só as pausas ≥ 0,68 s (energia do áudio abaixo de 35% entre o piso e
# a fala); sai o miolo e ficam ~0,4 s. Em ordem: "duramente criticado | por um lado", "é esse? | E eu faço", "do Nordeste. | Que",
# "de críticas. | Aonde", "tanto pregam? | Pessoal", "eles passam. | Então", "mudar isso. | E eu"; em B: "a lógica. | As pessoas"
RESPIROS = {"A": [(20.20, 20.50), (59.12, 59.70), (66.12, 66.42), (107.10, 107.38), (116.74, 117.64), (128.50, 128.82),
                  (134.66, 134.94)],
            "B": [(12.92, 13.20)]}


def _sem_respiros(f, a, b):
    pedacos, ini = [], a
    for x, y in RESPIROS.get(f, []):
        if a < x < b:
            pedacos.append((f, ini, x, 0.0))
            ini = y
    return pedacos + [(f, ini, b, 0.0)]


CHUNKS = [p for t in TRECHOS for p in _sem_respiros(*t)]


def chunks(versao: str) -> list[tuple]:
    return CHUNKS


def linha_do_tempo(versao: str) -> list[dict]:
    """Cada chunk com o início no vídeo final (dissolves sobrepõem o fim do anterior)."""
    t, saida = 0.0, []
    for i, (f, a, b, x) in enumerate(chunks(versao)):
        b = a + round((b - a) * FPS) / FPS          # duração em quadros inteiros: vídeo e áudio com o mesmo comprimento
        ini = t - (x if i else 0.0)
        saida.append({"fonte": f, "a": a, "b": b, "x": x, "ini": ini, "fim": ini + (b - a)})
        t = ini + (b - a)
    return saida


def duracao(versao: str) -> float:
    return linha_do_tempo(versao)[-1]["fim"] + CAUDA


def out(versao: str, fonte: str, t: float) -> float | None:
    """Tempo do bruto → tempo do vídeo final (None se aquele instante foi cortado)."""
    for c in linha_do_tempo(versao):
        if c["fonte"] == fonte and c["a"] - 1e-6 <= t <= c["b"] + 1e-6:
            return c["ini"] + (t - c["a"])
    return None


def trecho(versao: str, fonte: str, t: float) -> dict | None:
    """O pedaço da linha do tempo que contém o instante t do bruto (None se ele foi cortado)."""
    return next((c for c in linha_do_tempo(versao) if c["fonte"] == fonte and c["a"] - 1e-6 <= t <= c["b"] + 1e-6), None)


def fim_da_fala(versao: str) -> float:
    return out(versao, "B", 28.90)


# ───────────────────────────── enquadramento do JP (zoom contínuo, aprovado na prova v3) ──
# (fonte, t, zoom): keyframes do zoom-base; entre eles o zoom anda com ease in-out
ZOOM = [
    ("A", 0.0, 1.00), ("A", 3.2, 1.10), ("A", 6.0, 1.04), ("A", 9.5, 1.05), ("A", 13.5, 1.17), ("A", 16.0, 1.06),
    ("A", 29.8, 1.11), ("A", 44.0, 1.05), ("A", 52.0, 1.08),
    ("A", 56.5, 1.06), ("A", 58.9, 1.18),                         # "que mundo doentio é esse?"
    ("A", 66.0, 1.08), ("A", 84.0, 1.04), ("A", 98.8, 1.06), ("A", 106.5, 1.06),
    ("A", 107.5, 1.04), ("A", 116.0, 1.09),                       # "aonde está o amor…" — zoom bem fraco
    ("A", 121.0, 1.05), ("A", 133.6, 1.10), ("A", 139.0, 1.10), ("A", 140.45, 1.00),   # o corte do "21, 8" vira troca de plano
    ("A", 144.5, 1.05), ("A", 147.6, 1.16), ("A", 153.2, 1.12),   # "o que Deus quer dizer com o morno?"
    ("B", 0.0, 1.04), ("B", 7.3, 1.08), ("B", 12.8, 1.05), ("B", 21.6, 1.04),
    ("B", 28.9, 1.20),                                            # fechamento: push-in lento até o fim
]
ZOOM_JANELA, Y_JANELA = 1.16, 0.56     # com janela aberta o JP desce (o rosto vai a 56% da altura)
RAMPA = 0.6

# ─────────────────────────────────────────────────────────── eventos de motion ──
# v2 (23/10, pedido do JP): poucos inserts, parados, sem sombra; nada depois do versículo (o JP fala até o fim).
# tipo janela = card 16:9 em cima (cantos arredondados), o JP desce enquanto ele está aberto (montagem.py);
# tipo tela = tela cheia (sem o JP e sem legenda); tipo dividida = tela dividida em cima/embaixo (o JP embaixo).
# clipes: trechos do vídeo do Nikolas (N, sem som) em sequência dentro do card. Os eventos vão para o Remotion
# (src/videos/jp-testemunhos) por roteiro/eventos_v2.json, gravado ao rodar este arquivo.
JANELA = (160, 120, 920, 548)          # x0, y0, x1, y1 — 760×428 (16:9): a capa do Felca inteira, acima do cabelo do JP rebaixado
EVENTOS = [
    {"tipo": "janela", "id": "felca", "de": ("A", 4.45), "ate": ("A", 7.30), "imagem": "broll/bruto/imagens/felca-thumb.webp"},
    {"tipo": "tela", "id": "prints", "de": ("A", 30.50), "ate": ("A", 43.15),
     "cartoes": [("01-felipe-neto", ("A", 30.55)), ("02-thiago-felix", ("A", 33.30)), ("04-julia", ("A", 35.45)),
                 ("03-jeff-mattias", ("A", 37.70)), ("06-lazaro-rosa", ("A", 39.90)), ("07-leo-salles", ("A", 41.80))]},
    # "…falar sobre o tema do Nordeste." — só uma passagem de assunto: o mapa desenha, mostra "Nordeste" e sai (24/10: era longo demais)
    {"tipo": "tela", "id": "mapa", "de": ("A", 64.55), "ate": ("A", 67.40)},
    # "…está no ranking das mais pobres e mais violentas…" — ranking do g1 (RANKING abaixo) em gráfico limpo e animado
    {"tipo": "tela", "id": "ranking", "de": ("A", 68.50), "ate": ("A", 72.70)},
    # clipes: [início no vídeo do Nikolas (N, sem som), x, y, largura do recorte no 4K 2160×3840]; dividem o tempo do evento por igual.
    # "…Nikolas Ferreira, foi lá dar voz…" — entra numa janelinha que abre para a tela toda (~3 s cheio) e volta para a janelinha;
    # é o começo do vídeo dele: fala até 2,4 s ("hoje eu vou falar sobre o Nordeste, mas…"), depois levanta da cadeira e sai
    {"tipo": "tela", "id": "nikolas", "de": ("A", 73.55), "ate": ("A", 78.35), "clipes": [(0.0, 0, 0, 2160)]},
    # "Os nordestinos que estão contando as suas histórias…" — tela toda, mesmo enquadramento para todos: rosto a 36% da altura,
    # corpo até o joelho (zoom 1,2 centrado no rosto medido com YuNet); a legenda queimada do vídeo deles aparece, a nossa some
    {"tipo": "tela", "id": "nordestinos", "de": ("A", 83.00), "ate": ("A", 89.90),
     "clipes": [(11.0, 200, 378, 1800), (24.0, 217, 268, 1800), (20.0, 222, 242, 1800)]},   # 11,0: depois do corte das 10,6 s
    # "…uma senhora… ou ela come ou ela trata o seu câncer." — a senhora no vídeo do Nikolas: "faço tratamento de câncer"
    {"tipo": "dividida", "id": "senhora", "de": ("A", 92.15), "ate": ("A", 98.75), "clipes": [(33.6, 480, 820, 1200)]},
    {"tipo": "tela", "id": "versiculo", "de": ("A", 138.10), "ate": ("A", 147.70)},
]
# frases finais (24/10, troca da máquina de escrever): uma por vez no centro, no estilo da legenda, sobre o preto; a última com a bandeira
CARTELA = ["Ninguém é perfeito.",
           "Entre escolher o que\nestá dando errado\ne a mudança,",   # quebras só de diagramação (o "a" não fica sozinho no fim)
           "eu escolho a MUDANÇA.",
           "Flávio Bolsonaro"]
CARTELA_NUMERO = "22"      # na última tela: o nome, o número grande embaixo e a bandeira menor por último (24/10)
VERSICULO = "Assim, porque és morno, e não és frio nem quente, vomitar-te-ei da minha boca."
VERSICULO_REF = "Apocalipse 3:16"
GRIFOS = ["morno", "vomitar-te-ei da minha boca"]
RANKING = [  # print do g1 — Anuário Brasileiro de Segurança Pública 2025 (dados de 2024), taxa por 100 mil hab.
    ("Maranguape", "CE", "79,9", -3.89, -38.68), ("Jequié", "BA", "77,6", -13.86, -40.08),
    ("Juazeiro", "BA", "76,2", -9.41, -40.50), ("Camaçari", "BA", "74,8", -12.70, -38.32),
    ("Cabo de Santo Agostinho", "PE", "73,3", -8.28, -35.03), ("São Lourenço da Mata", "PE", "73", -8.00, -35.02),
    ("Simões Filho", "BA", "71,4", -12.78, -38.40), ("Caucaia", "CE", "68,7", -3.74, -38.65),
    ("Maracanaú", "CE", "68,5", -3.88, -38.63), ("Feira de Santana", "BA", "65,2", -12.27, -38.97),
]
FONTE_RANKING = "Fonte: Anuário Brasileiro de Segurança Pública 2025 · mortes violentas por 100 mil hab."
UFS_NORDESTE = {"21", "22", "23", "24", "25", "26", "27", "28", "29"}   # MA PI CE RN PB PE AL SE BA (código IBGE)

# a legenda some nas telas cheias (o Remotion esconde); a lista de palavras fica completa
SEM_LEGENDA = []


def eventos(versao: str) -> list[dict]:
    """Eventos com tempos já no vídeo final."""
    ev = []
    for e in EVENTOS:
        e2 = dict(e)
        for k in ("de", "ate", "troca", "troca2"):
            if e.get(k):
                e2[k] = out(versao, *e[k])
        if e2["ate"] is None:
            e2["ate"] = duracao(versao)
        if "cartoes" in e:
            e2["cartoes"] = [(n, out(versao, *t)) for n, t in e["cartoes"]]
        ev.append(e2)
    return ev


if __name__ == "__main__":
    for v in ("v2",):
        print(v, f"{duracao(v):.2f} s")
        for c in linha_do_tempo(v):
            print(f"   {c['fonte']} {c['a']:7.2f}–{c['b']:7.2f}  →  {c['ini']:7.2f}–{c['fim']:7.2f}  (dissolve {c['x']})")
        for e in eventos(v):
            print(f"   {e['id']:10s} {e['de']:7.2f}–{e['ate']:7.2f}")
        import json
        destino = PROJ / "roteiro" / f"eventos_{v}.json"          # lido pelo Remotion (src/videos/jp-testemunhos)
        json.dump({"janela": JANELA, "eventos": eventos(v), "cartela": CARTELA, "numero": CARTELA_NUMERO,
                   "fim_fala": round(fim_da_fala(v), 3), "fim_jp": round(linha_do_tempo(v)[-1]["fim"], 3), "ranking": [r[:3] for r in RANKING], "fonte_ranking": FONTE_RANKING},
                  open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("→", destino)
