#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste em lote da biblioteca: um quadro do meio de CADA cena de cenas/, em cada formato e preset, pelo auditor do motor.

  cd ~/.claude/skills/video-animacao-explicativa/scripts
  /opt/homebrew/bin/python3 -B -m testes.lote                          # lab-ia e dossie · horizontal e vertical
  /opt/homebrew/bin/python3 -B -m testes.lote --folhas "<pasta>"       # + uma folha de contato por preset e formato
  /opt/homebrew/bin/python3 -B -m testes.lote --so rag,agente --fracao 0.9 --presets neon-shorts

Sai com 1 se alguma cena: falhar no build, reprovar no auditor (cor ou fonte fora da DA, animação fora de seek),
usar data-da-livre, declarar conteúdo fora da zona segura, sair sem o selo "ilustrativo" ou gerar quadro vazio.
Os projetos de teste nascem numa pasta temporária (apagada no fim) com VIDEO_OPS_HOME dentro dela; tudo roda sob a
trava global do kit, num navegador só por preset. A folha serve para OLHAR: o auditor não vê texto cortado nem
elemento em cima de outro."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from testes import apoio  # noqa: E402
import da  # noqa: E402  (apoio põe o kit no caminho)
import da_ext_motor  # noqa: E402
import video  # noqa: E402
from PIL import Image, ImageStat  # noqa: E402


def conferir(d, pasta: Path, job: dict, escala: float) -> list:
    """→ lista de problemas do quadro (vazia = aprovado)."""
    arq = pasta / job["saida"]
    if not arq.is_file():
        return ["o quadro não foi gravado"]
    try:
        car = da.ler_carimbo(arq)
    except Exception as e:  # carimbo ausente ou ilegível é reprovação, não erro do teste
        return [f"sem carimbo legível ({e})"]
    ruins = []
    if car.get("auditoria") != "ok":
        ruins.append(f'auditoria: {car.get("auditoria")}')
    if car.get("da_sha256") != d.sha256:
        ruins.append("carimbo de outra DA")
    par = car.get("parametros") or {}
    if par.get("livres"):
        ruins.append("usa data-da-livre (nenhuma cena da biblioteca pode)")
    lay = par.get("layout") or {}
    if not lay.get("ilustrativo") or not (lay.get("selo") or job["_texto"]):
        ruins.append('exemplo padrão inventado sem o selo "ilustrativo" (só cena de texto do roteiro sai sem selo)')
    c, a = lay.get("conteudo"), lay.get("area")
    if not c or not a:
        ruins.append("a cena não declarou layout.conteudo/layout.area")
    elif not (a["x"] <= c["x"] and c["x"] + c["w"] <= a["x"] + a["w"] + 1 and a["y"] <= c["y"] and c["y"] + c["h"] <= a["y"] + a["h"] + 1):
        ruins.append(f"conteúdo fora da zona segura: {c} × área {a}")
    im = Image.open(arq).convert("RGB")
    L, A = d.dimensoes(job["formato"])
    if im.size != (round(L * escala), round(A * escala)):
        ruins.append(f"tamanho {im.size}")
    if sum(ImageStat.Stat(im).stddev) < 12:
        ruins.append("quadro quase vazio")
    return ruins


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Um quadro do meio de cada cena, por preset e formato, pelo auditor do motor.")
    ap.add_argument("--presets", default="lab-ia,dossie")
    ap.add_argument("--formatos", default="horizontal,vertical")
    ap.add_argument("--escala", type=float, default=0.3334, help="fração do tamanho do formato (padrão 0.3334 → 640×360)")
    ap.add_argument("--fracao", type=float, default=0.5, help="instante do quadro, como fração da duração padrão da cena")
    ap.add_argument("--so", default="", help="só estas cenas (nomes separados por vírgula)")
    ap.add_argument("--folhas", default="", help="pasta onde gravar folha_<preset>_<formato>.png")
    ap.add_argument("--colunas", type=int, default=0, help="colunas da folha (padrão: 4 no horizontal, 7 no vertical)")
    a = ap.parse_args(argv)
    import storyboard
    metas = {c["nome"]: c["meta"] for c in storyboard.catalogo(None) if c["origem"] == "skill"}
    nomes = [n for n in apoio.NOMES if not a.so or n in a.so.split(",")]
    faltam = [n for n in nomes if n not in metas]
    if faltam or not nomes:
        print("cena sem meta legível (ou nenhuma cena escolhida):", ", ".join(faltam) or a.so)
        return 1
    area, reprovadas, total = apoio.Area(), [], 0
    try:
        for preset in a.presets.split(","):
            d = da.carregar(str(area.projeto(preset)))
            pasta = Path(d.raiz) / "animacoes" / "_lote"
            pasta.mkdir(parents=True, exist_ok=True)
            fila = [{"cena": str(apoio.CENAS / f"{n}.js"), "saida": f"{n}_{f}.png", "formato": f, "escala": a.escala,
                     "quadro": round(metas[n]["dur_padrao"] * a.fracao, 2), "_nome": n,
                     "_texto": str(metas[n]["params"]["ilustrativo"].get("descricao", "")).startswith("null = a tela mostra o texto")}
                    for f in a.formatos.split(",") for n in nomes]
            (pasta / "_fila.json").write_text(json.dumps([{k: v for k, v in j.items() if not k.startswith("_")} for j in fila]), encoding="utf-8")
            r = da_ext_motor.render(["--fila", str(pasta / "_fila.json"), "--json", "--inatividade", "90"], da_obj=d, capturar=True, rotulo="lote das cenas de IA")
            try:
                res = json.loads(r.stdout[r.stdout.index("{"):])
            except ValueError:
                print(f"{preset}: o motor não respondeu em JSON (código {r.returncode})\n{r.stderr[-3000:]}")
                return 1
            erros = {Path(f["saida"]).name: f["erro"] for f in res.get("falhas", [])}
            for j in fila:
                total += 1
                ruins = [erros[j["saida"]].strip()[:700]] if j["saida"] in erros else conferir(d, pasta, j, a.escala)
                if ruins:
                    reprovadas.append(f'{preset} · {j["formato"]} · {j["_nome"]}: ' + "; ".join(ruins))
            if a.folhas:
                destino = Path(a.folhas)
                destino.mkdir(parents=True, exist_ok=True)
                for f in a.formatos.split(","):
                    feitos = [j for j in fila if j["formato"] == f and (pasta / j["saida"]).is_file()]
                    if feitos:
                        folha = destino / f"folha_{preset}_{f}.png"
                        video.folha_de_contato([pasta / j["saida"] for j in feitos], [f'{j["_nome"]} · t={j["quadro"]} s' for j in feitos], str(folha),
                                               colunas=a.colunas or (4 if f == "horizontal" else 7), largura_celula=round(d.dimensoes(f)[0] * a.escala), da_obj=d,
                                               titulo=f"{preset} · {f} · {len(feitos)} cenas")
                        print("folha:", folha)
    finally:
        area.limpar()
    for linha in reprovadas:
        print("REPROVADA", linha)
    print(f"LOTE: {total - len(reprovadas)} de {total} quadros aprovados ({len(nomes)} cenas × {a.formatos} × {a.presets})")
    return 1 if reprovadas else 0


if __name__ == "__main__":
    sys.exit(main())
