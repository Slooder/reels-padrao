#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressões de robustez do motor: nada trava, nada fica órfão, nada escapa do auditor, seek é puro.

Rodar a partir do kit:  python3 -m unittest testes.test_motor_robustez -v
Pasta temporária com espaço e acento, VIDEO_OPS_HOME isolado. Os renders são minúsculos (≤ 480×270, ≤ 8 s de
peça, quase sempre interrompidos antes) e passam pela trava global de verdade. Cada teste que provoca um
travamento tem prazo curto e mata o que criou; o tearDown confere que não sobrou processo.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
import da  # noqa: E402
import da_ext_motor as motor  # noqa: E402
import trava  # noqa: E402
import video  # noqa: E402

PY = sys.executable
DA_PY = KIT / "da.py"
RENDER = KIT / "motor" / "render.mjs"
FFMPEG = da._bin("ffmpeg")

PARAMS = {
    "titulo": {"titulo": "A conta que não fecha", "sobretitulo": "Capítulo 2", "subtitulo": "Linha de apoio"},
    "gc": {"nome": "João Ávila", "cargo": "Maestro", "selo": "ao vivo"},
    "moldura": {"rotulo": "Arquivo · 2018", "sub": "Reprodução"},
    "citacao": {"texto": "O dinheiro não some: ele muda de endereço.", "autor": "Mariana Albuquerque", "cargo": "Procuradora", "fonte": "Folha, 2024"},
    "barras": {"titulo": "Quanto cada estado recebe", "dados": [{"rotulo": "SC", "valor": 0.31}, {"rotulo": "SP", "valor": 0.28},
                                                             {"rotulo": "BA", "valor": 1.65}], "fonte": "Tesouro Nacional, 2024", "casas": 2},
}

# Cena de casos do auditor: p.caso escolhe o que é montado. Os casos "x_*" têm de reprovar; os "ok_*", passar.
CASOS_JS = r"""
export const meta = { nome: 'casos', dur_padrao: 2, alfa_padrao: false, params: { caso: { tipo: 'texto', obrigatorio: true } } };
const S = {};
const SVG_VERMELHO = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>');
export function build(palco, p, ctx) {
  const base = ctx.el('div');
  Object.assign(base.style, { position: 'absolute', left: '40px', top: '40px', width: '200px', height: '100px', background: ctx.cor('primaria') });
  palco.appendChild(base);
  const c = p.caso;
  const caixa = (css) => { const e = ctx.el('div'); e.style.cssText = 'position:absolute;left:300px;top:40px;width:100px;height:100px;' + css; palco.appendChild(e); return e; };
  if (c === 'x_before') { const st = document.createElement('style'); st.textContent = '.px::before{content:"oi";display:block;background:rgb(255,0,0);color:rgb(0,255,0);font-family:Georgia;width:150px;height:60px}'; document.head.appendChild(st); base.className = 'px'; }
  if (c === 'x_fora_do_palco') { const e = document.createElement('div'); e.style.cssText = 'position:absolute;left:0;top:0;width:200px;height:200px;background:rgb(255,0,0)'; document.body.appendChild(e); }
  if (c === 'x_fundo_do_body') document.body.style.backgroundColor = 'rgb(255,0,0)';
  if (c === 'x_shadow') { const h = caixa(''); h.attachShadow({ mode: 'closed' }).innerHTML = '<div style="width:100px;height:100px;background:rgb(255,0,0)"></div>'; }
  if (c === 'x_canvas') { const cv = document.createElement('canvas'); cv.width = 200; cv.height = 100; cv.style.cssText = 'position:absolute;left:300px;top:40px'; const g = cv.getContext('2d'); g.fillStyle = 'rgb(255,0,0)'; g.fillRect(0, 0, 200, 100); palco.appendChild(cv); }
  if (c === 'x_stop') { const sv = ctx.svg('svg', { width: 200, height: 100, style: 'position:absolute;left:300px;top:40px' }); sv.innerHTML = '<defs><linearGradient id="g"><stop offset="0" stop-color="rgb(255,0,0)"/><stop offset="1" stop-color="rgb(0,0,255)"/></linearGradient></defs><rect width="200" height="100" fill="url(#g)"/>'; palco.appendChild(sv); }
  if (c === 'x_use_defs') { const sv = ctx.svg('svg', { width: 200, height: 100, style: 'position:absolute;left:300px;top:40px' }); sv.innerHTML = '<defs><rect id="forma" width="80" height="80" fill="rgb(255,0,0)"/></defs><use href="#forma"/>'; palco.appendChild(sv); }
  if (c === 'x_img') { const im = document.createElement('img'); im.src = SVG_VERMELHO; im.style.cssText = 'position:absolute;left:300px;top:40px'; palco.appendChild(im); }
  if (c === 'x_svg_image') { const sv = ctx.svg('svg', { width: 200, height: 100, style: 'position:absolute;left:300px;top:40px' }); sv.innerHTML = '<image href="' + SVG_VERMELHO + '" width="100" height="100"/>'; palco.appendChild(sv); }
  if (c === 'x_bg_url') base.style.backgroundImage = 'url("' + SVG_VERMELHO + '")';
  if (c === 'x_border_image') { base.style.border = '10px solid'; base.style.borderImage = 'linear-gradient(rgb(255,0,0), rgb(0,0,255)) 1'; }
  if (c === 'x_filtro') base.style.filter = 'hue-rotate(180deg)';
  if (c === 'x_backdrop') caixa('backdrop-filter: invert(1)');
  if (c === 'x_drop_shadow') base.style.filter = 'drop-shadow(0 0 10px rgb(255,0,0))';
  if (c === 'x_blend') base.style.mixBlendMode = 'difference';
  if (c === 'x_livre_no_palco') { palco.setAttribute('data-da-livre', 'tudo'); base.style.background = 'rgb(255,0,0)'; }
  if (c === 'x_opacidade_zero') caixa('background:rgb(255,0,0);opacity:0');
  if (c === 'x_display_none') caixa('background:rgb(255,0,0);display:none');
  if (c === 'x_janela') S.janela = caixa('background:rgb(255,0,0);visibility:hidden');
  if (c === 'x_cor_no_seek') S.troca = base;
  if (c === 'x_raf') { let x = 0; const f = () => { x += 1; base.style.left = (40 + x % 50) + 'px'; if (x < 5) requestAnimationFrame(f); }; requestAnimationFrame(f); }
  if (c === 'x_random') S.rnd = base;
  if (c === 'x_timeout') setTimeout(() => { base.style.left = '90px'; }, 5);
  if (c === 'x_date') base.style.left = (40 + Date.now() % 7) + 'px';
  if (c === 'x_new_date') base.style.left = (40 + new Date().getSeconds() % 7) + 'px';
  if (c === 'x_performance') base.style.left = (40 + performance.now() % 7) + 'px';
  if (c === 'ok_color_mix') base.style.background = 'color-mix(in srgb, var(--da-cor-primaria) 50%, transparent)';
  // D6 — cor da DA com alfa: a forma da casa funciona; a forma com barra computa transparente e tem de reprovar
  if (c === 'ok_alfa_css') { base.style.background = 'rgba(var(--da-cor-primaria-rgb), 0.5)'; const st = document.createElement('style'); st.textContent = '.qa{background:rgba(var(--da-cor-fundo-rgb), .86);border:2px solid rgba(var(--da-dado-2-rgb), .5)}'; document.head.appendChild(st); S.qa = caixa(''); S.qa.className = 'qa'; }
  if (c === 'x_alfa_barra') base.style.background = 'rgb(var(--da-cor-fundo-rgb) / 0.86)';
  if (c === 'x_alfa_barra_css') { const st = document.createElement('style'); st.textContent = '.qb{background:rgb(var(--da-cor-primaria-rgb) / .5)}'; document.head.appendChild(st); caixa('').className = 'qb'; }
  if (c === 'x_var_inexistente') { const e = ctx.texto('corpo', 'texto com token digitado errado', {}); e.style.color = 'var(--da-cor-primara)'; palco.appendChild(e); }
  if (c === 'x_declaracao_invalida') { const e = caixa(''); e.setAttribute('style', e.getAttribute('style') + 'background: rgb(10 10 / 0.5)'); }
  if (c === 'ok_alfa') { base.style.background = ctx.alfa('primaria', 0.5); base.style.boxShadow = '0 0 8px ' + ctx.alfa('neutro-1', 0.6); }
  if (c === 'ok_drop_shadow_da') base.style.filter = 'drop-shadow(0 0 6px ' + ctx.cor('fundo') + ') blur(1px)';
  if (c === 'ok_img_livre') { const im = document.createElement('img'); im.src = SVG_VERMELHO; im.setAttribute('data-da-livre', 'foto de teste'); im.style.cssText = 'position:absolute;left:300px;top:40px'; palco.appendChild(im); }
  if (c === 'ok_canvas_livre') { const cv = document.createElement('canvas'); cv.width = 50; cv.height = 50; cv.setAttribute('data-da-livre', 'gráfico em canvas'); palco.appendChild(cv); }
  if (c === 'ok_rng') { const r = ctx.rng(7); base.style.left = (40 + Math.floor(r() * 50)) + 'px'; }
  S.ctx = ctx; S.base = base;
  return { fundo_computado: getComputedStyle(base).backgroundColor, qa_computado: S.qa ? getComputedStyle(S.qa).backgroundColor : null };
}
export function seek(t) {
  if (S.janela) S.janela.style.visibility = (t / S.ctx.duracao >= 0.31 && t / S.ctx.duracao <= 0.36) ? 'visible' : 'hidden';
  if (S.troca) S.troca.style.background = (t / S.ctx.duracao >= 0.50 && t / S.ctx.duracao <= 0.58) ? 'rgb(255, 0, 0)' : S.ctx.cor('primaria');
  if (S.rnd) S.rnd.style.left = (40 + Math.random() * 50).toFixed(2) + 'px';
}
"""
# Segunda leva (fecho): o que NÃO aparece no estilo computado — controles nativos, imagem por CSS, marcador, seleção,
# emoji — e o que anima FORA de seek(t) sem passar pelas APIs clássicas — SMIL, mensagens, crypto, imagem animada.
CASOS2_JS = r"""
export const meta = { nome: 'casos2', dur_padrao: 2, alfa_padrao: false, params: { caso: { tipo: 'texto', obrigatorio: true }, img: { tipo: 'arquivo', padrao: null } } };
const S = {};
const SVG_VERMELHO = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="red"/></svg>');
const SVG_ANIMADO = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="40" height="40" fill="red"><animate attributeName="x" from="0" to="60" dur="0.5s" repeatCount="indefinite"/></rect></svg>');
export function build(palco, p, ctx) {
  const base = ctx.el('div');
  Object.assign(base.style, { position: 'absolute', left: '40px', top: '40px', width: '80px', height: '80px', background: ctx.cor('primaria') });
  palco.appendChild(base);
  const c = p.caso;
  const html = (h) => { const d = ctx.el('div'); d.style.cssText = 'position:absolute;left:160px;top:40px;width:280px;height:200px'; d.innerHTML = h; palco.appendChild(d); return d; };
  const texto = (t) => { const e = ctx.texto('corpo', t, { tam: 20 }); e.style.position = 'absolute'; e.style.left = '160px'; e.style.top = '40px'; palco.appendChild(e); ctx.medir(e); return e; };
  const smil = '<svg width="280" height="80"><rect width="80" height="80" fill="' + ctx.cor('primaria') + '"><animate attributeName="x" from="0" to="200" dur="0.7s" repeatCount="indefinite"/></rect></svg>';
  // ── animação fora de seek(t) ──
  if (c === 'v_smil') html(smil);
  if (c === 'v_smil_livre') html(smil).setAttribute('data-da-livre', 'logo animado de terceiros');
  if (c === 'v_smil_set') html('<svg width="280" height="80"><rect width="80" height="80" fill="' + ctx.cor('primaria') + '"><set attributeName="x" to="120" begin="0.3s"/></rect></svg>');
  if (c === 'v_marquee') html('<marquee class="da-corpo" style="color:' + ctx.cor('texto') + '">corre sozinho</marquee>');
  if (c === 'v_msg') { const ch = new MessageChannel(); let x = 0; ch.port1.onmessage = () => { x = (x + 3) % 200; base.style.left = (40 + x) + 'px'; ch.port2.postMessage(0); }; ch.port2.postMessage(0); }
  if (c === 'v_window_msg') { let x = 0; window.addEventListener('message', () => { x = (x + 3) % 200; base.style.left = (40 + x) + 'px'; if (x < 150) window.postMessage('a', '*'); }); window.postMessage('a', '*'); }
  if (c === 'v_promessa') { let x = 0; (async () => { for (;;) { await new Promise((ok) => { const im = new Image(); im.onload = im.onerror = ok; im.src = SVG_VERMELHO + '#' + x; }); x = (x + 3) % 200; base.style.left = (40 + x) + 'px'; } })(); }
  if (c === 'v_crypto') { const a = new Uint8Array(1); crypto.getRandomValues(a); base.style.left = (40 + a[0]) + 'px'; }
  if (c === 'v_uuid') base.dataset.id = crypto.randomUUID();
  if (c === 'v_timeline') base.style.left = (40 + (document.timeline.currentTime % 50)) + 'px';
  if (c === 'v_perf_proto') base.style.left = (40 + Performance.prototype.now.call(performance) % 7) + 'px';
  if (c === 'v_evento') base.style.left = (40 + (new Event('x').timeStamp % 50)) + 'px';
  if (c === 'v_intl') texto('agora são ' + new Intl.DateTimeFormat('pt-BR', { timeStyle: 'medium' }).format());
  if (c === 'v_temporal') base.dataset.t = String(globalThis.Temporal ? Temporal.Now.instant() : Date.now());
  if (c === 'v_micro_laco') { let n = 0; const f = () => { n++; queueMicrotask(f); }; try { f(); } catch (e) { /* o palco corta o laço */ } }
  if (c === 'v_seek_sorteado') S.sorte = base;
  if (c === 'v_gif' || c === 'v_apng') { const im = document.createElement('img'); im.src = p.img; im.setAttribute('data-da-livre', 'figurinha'); im.style.cssText = 'position:absolute;left:160px;top:40px'; palco.appendChild(im); }
  if (c === 'v_gif_fundo') { base.setAttribute('data-da-livre', 'figurinha de fundo'); base.style.backgroundImage = 'url("' + p.img + '")'; }
  if (c === 'v_svg_animado') { const im = document.createElement('img'); im.src = SVG_ANIMADO; im.setAttribute('data-da-livre', 'logo'); im.style.cssText = 'position:absolute;left:160px;top:40px'; palco.appendChild(im); }
  if (c === 'v_editavel') { const e = texto('edite aqui'); e._inner.contentEditable = 'true'; e._inner.focus(); }
  // ── cor que o estilo computado não mostra ──
  if (c === 'v_content_url') base.style.content = 'url("' + SVG_VERMELHO + '")';
  if (c === 'v_paint') base.style.backgroundImage = 'paint(xadrez)';
  if (c === 'v_lista_imagem') html('<ul class="da-corpo" style="list-style-image:url(&quot;' + SVG_VERMELHO + '&quot;);color:' + ctx.cor('texto') + '"><li>um</li><li>dois</li></ul>');
  if (c === 'v_marcador') html('<ul class="da-corpo" style="color:rgb(255,0,0)"><li><span style="color:' + ctx.cor('texto') + '">texto na cor da DA, bolinha vermelha</span></li></ul>');
  if (c === 'v_progress') html('<progress value="0.7" style="width:200px;height:30px"></progress>');
  if (c === 'v_progress_acento') html('<progress value="0.7" style="width:200px;height:30px;accent-color:#ff0000"></progress>');
  if (c === 'v_meter') html('<meter value="0.7" style="width:200px;height:30px"></meter>');
  if (c === 'v_checkbox') html('<input type="checkbox" checked style="width:120px;height:120px">');
  if (c === 'v_range') html('<input type="range" style="width:200px">');
  if (c === 'v_select') html('<select><option>um</option><option>dois</option></select>');
  if (c === 'v_textarea') html('<textarea>texto</textarea>');
  if (c === 'v_button') html('<button>ok</button>');
  if (c === 'v_selecao') { const st = document.createElement('style'); st.textContent = '::selection{background:#ff0000;color:#00ff00}'; document.head.appendChild(st); const e = texto('texto selecionado'); const r = document.createRange(); r.selectNodeContents(e._inner); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); }
  if (c === 'v_emoji') texto('Pegou fogo \u{1F525}');
  // ── o que tem de continuar passando ──
  if (c === 'ok_lista') html('<ul class="da-corpo" style="color:' + ctx.cor('texto') + '"><li>um</li><li><span>dois</span></li></ul><ol class="da-dados" style="color:' + ctx.cor('primaria') + '"><li>três</li></ol>');
  if (c === 'ok_emoji_livre') { const e = texto('Pegou fogo '); const s = document.createElement('span'); s.setAttribute('data-da-livre', 'emoji'); s.textContent = '\u{1F525}'; e._inner.appendChild(s); }
  if (c === 'ok_progress_livre') html('<progress value="0.7" data-da-livre="captura de interface" style="width:200px;height:30px"></progress>');
  if (c === 'ok_gif_parado') { const im = document.createElement('img'); im.src = p.img; im.setAttribute('data-da-livre', 'foto'); im.style.cssText = 'position:absolute;left:160px;top:40px'; palco.appendChild(im); }
  if (c === 'ok_mascara') { base.style.webkitMaskImage = 'url("' + SVG_VERMELHO + '")'; base.style.maskImage = 'url("' + SVG_VERMELHO + '")'; }
  if (c === 'ok_microtarefa') queueMicrotask(() => { base.dataset.pronto = '1'; });
  if (c === 'ok_svg_parado') html('<svg width="200" height="80"><rect width="80" height="80" fill="' + ctx.cor('secundaria') + '"/><text x="90" y="40" class="da-dados" fill="' + ctx.cor('texto') + '">ok</text></svg>');
  if (c === 'ok_simbolos') texto('Sim ✓ · não ✕ · segue →');
  if (c === 'ok_intl_com_data') texto(new Intl.DateTimeFormat('pt-BR').format(new Date(2024, 0, 15)) + ' · ' + new Intl.DateTimeFormat('pt-BR').formatToParts(new Date(2024, 0, 15)).length + ' partes');
  S.ctx = ctx; S.base = base;
}
export function seek(t) {
  if (S.sorte) { const a = new Uint8Array(1); (globalThis.__sorte || (globalThis.__sorte = { n: 0 })).n++; S.sorte.style.left = (40 + (globalThis.__sorte.n * 37) % 150) + 'px'; }
}
"""
CASOS2_RUINS = {  # caso → trecho que a mensagem tem de trazer
    "v_smil": "(SMIL)", "v_smil_livre": "data-da-livre não libera animação", "v_smil_set": "<set> (SMIL)", "v_marquee": "<marquee>",
    "v_msg": "MessageChannel.postMessage", "v_window_msg": "window.postMessage", "v_promessa": "PEÇA INQUIETA",
    "v_crypto": "crypto.getRandomValues", "v_uuid": "crypto.randomUUID", "v_timeline": "document.timeline.currentTime",
    "v_perf_proto": "performance.now", "v_evento": "event.timeStamp", "v_intl": "Intl.DateTimeFormat sem data",
    "v_temporal": "Temporal.Now.instant|Date.now",           # Chromium sem Temporal (< 144) cai no Date.now, que também reprova
    "v_micro_laco": "queueMicrotask em laço", "v_seek_sorteado": "não é função pura de t",
    "v_gif": "GIF animado", "v_gif_fundo": "GIF animado", "v_apng": "APNG", "v_svg_animado": "SVG com animação", "v_editavel": "contenteditable",
    "v_content_url": "content", "v_paint": "paint()", "v_lista_imagem": "list-style-image", "v_marcador": "::marker", "v_progress": "<progress> (controle nativo)",
    "v_progress_acento": "<progress> (controle nativo)", "v_meter": "<meter> (controle nativo)", "v_checkbox": "<input> type=checkbox (controle nativo)",
    "v_range": "<input> type=range (controle nativo)", "v_select": "<select> (controle nativo)", "v_textarea": "<textarea> (controle nativo)",
    "v_button": "<button> (controle nativo)", "v_selecao": "::selection", "v_emoji": "emoji",
}
CASOS2_BONS = ["ok_lista", "ok_emoji_livre", "ok_progress_livre", "ok_gif_parado", "ok_mascara", "ok_microtarefa", "ok_svg_parado", "ok_simbolos",
               "ok_intl_com_data"]

CASOS_RUINS = ["x_before", "x_fora_do_palco", "x_fundo_do_body", "x_shadow", "x_canvas", "x_stop", "x_use_defs", "x_img", "x_svg_image",
               "x_bg_url", "x_border_image", "x_filtro", "x_backdrop", "x_drop_shadow", "x_blend", "x_livre_no_palco", "x_opacidade_zero",
               "x_display_none", "x_raf", "x_random", "x_timeout", "x_date", "x_new_date", "x_performance",
               "x_alfa_barra", "x_alfa_barra_css", "x_var_inexistente", "x_declaracao_invalida"]
CASOS_RUINS_EM_VIDEO = ["x_janela", "x_cor_no_seek"]          # só existem entre as 5 amostras antigas (0/25/50/75/100 %)
CASOS_BONS = ["ok_color_mix", "ok_alfa", "ok_alfa_css", "ok_drop_shadow_da", "ok_img_livre", "ok_canvas_livre", "ok_rng"]


def rodar(cmd, cwd=None, env=None, timeout=120):
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, timeout=timeout)


def esperar(condicao, prazo=20.0, passo=0.1) -> bool:
    limite = time.monotonic() + prazo
    while time.monotonic() < limite:
        if condicao():
            return True
        time.sleep(passo)
    return bool(condicao())


def quadro_do_video(arquivo: Path, n: int, destino: Path):
    from PIL import Image
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(arquivo), "-vf", f"select=eq(n\\,{n})", "-frames:v", "1", "-update", "1",
                        "-pix_fmt", "rgba", str(destino)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return Image.open(destino).convert("RGBA")


class TestRobustezMotor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = Path(tempfile.mkdtemp(prefix="da robustez é ")).resolve()
        cls.home = cls.base / "video ops home"
        cls.home.mkdir()
        cls._env = {k: os.environ.get(k) for k in ("VIDEO_OPS_HOME", "DA_JSON", "VIDEO_OPS_INATIVIDADE")}
        os.environ["VIDEO_OPS_HOME"] = str(cls.home)
        os.environ.pop("DA_JSON", None)
        os.environ.pop("VIDEO_OPS_INATIVIDADE", None)
        cls.node = motor.achar_node()
        cls.proj = cls.base / "projeto robustez ção"
        assert da.iniciar(cls.proj, nome="Teste de robustez", base="dossie")["criou_da"]
        cls.d = da.carregar(cls.proj)
        cls.anim = cls.proj / "animacoes"
        (cls.anim / "casos.js").write_text(CASOS_JS, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        subprocess.run(["pkill", "-KILL", "-f", str(cls.base)], capture_output=True)
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.base, ignore_errors=True)

    def tearDown(self):
        sobras = self.processos_da_pasta()
        if sobras:
            subprocess.run(["pkill", "-KILL", "-f", str(self.base)], capture_output=True)
            self.fail(f"o teste deixou {len(sobras)} processo(s) vivo(s): {sobras}")

    # -- ajudantes -------------------------------------------------------------
    def processos_da_pasta(self) -> list[int]:
        """Processos (node, ffmpeg…) cuja linha de comando cita a pasta deste teste."""
        r = subprocess.run(["pgrep", "-f", str(self.base)], capture_output=True, text=True)
        return [int(x) for x in r.stdout.split() if x.strip() and int(x) != os.getpid()]

    def da_py(self, *args, cwd=None, env=None, timeout=120):
        return rodar([PY, DA_PY, *args], cwd=cwd or self.proj, env=env, timeout=timeout)

    def cena(self, nome: str, corpo: str) -> Path:
        arq = self.anim / f"{nome}.js"
        arq.write_text(corpo, encoding="utf-8")
        return arq

    def ffmpeg_falso(self, nome: str, corpo: str) -> Path:
        arq = self.base / nome
        arq.write_text("#!/bin/sh\n" + corpo + "\n", encoding="utf-8")
        arq.chmod(arq.stat().st_mode | stat.S_IXUSR)
        return arq

    def render_em_segundo_plano(self, saida: Path, dur=8, direto=False) -> subprocess.Popen:
        """Lança um render de vídeo e devolve o Popen com o ffmpeg já recebendo quadros.
        (O .parcial não serve de gatilho: o ffmpeg só cria o arquivo depois de sondar ~5 s de entrada — em peça curta, no fim.)"""
        base_cmd = [self.node, str(RENDER)] if direto else [PY, str(DA_PY), "render"]
        p = subprocess.Popen([*base_cmd, "--cena", "teste_movimento", "--saida", str(saida), "--dur", str(dur), "--escala", "0.25"],
                             cwd=str(self.proj), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        parcial = str(saida) + ".parcial"

        def ffmpeg_rodando():
            r = subprocess.run(["pgrep", "-f", f"ffmpeg.*{Path(parcial).name}"], capture_output=True, text=True)
            return bool(r.stdout.strip())

        if not esperar(lambda: ffmpeg_rodando() or p.poll() is not None, 120):
            p.kill()
            self.fail("o render não começou a codificar em 120 s")
        if p.poll() is not None:
            self.fail(f"o render terminou antes da hora (rc {p.returncode}): {p.stderr.read()[-600:]}")
        time.sleep(0.7)
        return p

    def arvore(self, pid: int) -> set[int]:
        return trava._arvore([pid], trava._tabela()) - {os.getpid()}

    # -- 1. linha de comando estrita -----------------------------------------------
    def test_01_opcao_desconhecida_e_erros_de_uso_saem_com_64(self):
        x = self.anim / "uso.png"
        r = self.da_py("render", "--cena", "titulo", "--saida", x, "--quadro", "1", "--params", '{"titulo": "x"}', "--escla", "0.5")
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("opção desconhecida --escla", r.stderr)
        self.assertIn("--escala", r.stderr)                                    # sugestão
        for fps in ("0", "abc"):
            r = self.da_py("render", "--cena", "titulo", "--saida", self.anim / "uso.mp4", "--fps", fps, "--params", '{"titulo": "x"}')
            self.assertEqual(r.returncode, 64, f"--fps {fps}: {r.stderr}")
        r = self.da_py("render", "--cena", "titulo", "--saida", x, "--params", '{"titulo": "x"}', "--quadro")
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("--quadro: faltou o valor", r.stderr)                    # antes engolia o --da anexado pelo da.py
        r = self.da_py("render", "--cena", "titulo", "--saida", x, "--quadro", "99", "--params", '{"titulo": "x"}', "--validar")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("VÁLIDO: 1 job(s)", r.stdout)
        self.assertIn("fora da peça", r.stderr)                                # --quadro ajustado ao intervalo AVISA
        self.assertFalse(x.exists(), "--validar não pode renderizar")
        fila = self.anim / "fila uso.json"
        fila.write_text(json.dumps([{"cena": "titulo", "saida": "u.png", "quadro": 1, "escla": 0.5, "params": {"titulo": "x"}}]), encoding="utf-8")
        r = self.da_py("render", "--fila", fila)
        self.assertEqual(r.returncode, 64, r.stderr)
        self.assertIn("escla", r.stderr)
        r = rodar([self.node, RENDER, "--cena", "titulo", "--saida", "x.png", "--quadro", "0", "--params", '{"titulo": "x"}'], cwd=self.base)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn("erro: erro:", r.stderr)

    def test_02_erro_de_uso_aparece_antes_da_fila_da_trava(self):
        # trava PRIVADA ocupada por 30 s: o erro de uso tem de sair na hora, sem esperar a vez
        arquivo = self.base / "trava ocupada.lock"
        env = {trava.VAR_ARQUIVO: str(arquivo)}
        segura = subprocess.Popen([PY, str(KIT / "trava.py"), "--rotulo", "segura", "--", PY, "-c", "import time; time.sleep(30)"],
                                  env={**os.environ, **env})
        try:
            self.assertTrue(esperar(lambda: arquivo.exists() and not trava.estado(str(arquivo))["livre"], 10))
            t0 = time.monotonic()
            r = rodar([self.node, RENDER, "--cena", "titulo", "--saida", self.anim / "fila.png", "--quadro", "1", "--params", '{"titulo": "x", "naoexiste": 1}'],
                      cwd=self.proj, env=env, timeout=25)
            self.assertEqual(r.returncode, 64, r.stderr)
            self.assertIn("naoexiste", r.stderr)
            self.assertLess(time.monotonic() - t0, 15)
            self.assertNotIn("aguardando trava", r.stderr)
        finally:
            segura.send_signal(signal.SIGTERM)
            segura.wait(timeout=10)

    # -- 2. ffmpeg que morre ou trava -------------------------------------------------
    def test_03_ffmpeg_que_morre_no_meio_do_encode_nao_trava(self):
        falso = self.ffmpeg_falso("ffmpeg que morre", "head -c 200000 > /dev/null\nexit 9")
        saida = self.anim / "morre ção.mp4"
        t0 = time.monotonic()
        r = self.da_py("render", "--cena", "teste_movimento", "--saida", saida, "--dur", "6", "--escala", "0.25",
                       env={"VIDEO_OPS_FFMPEG": str(falso)}, timeout=90)       # antes: travava para sempre com a trava global
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertLess(time.monotonic() - t0, 60)
        self.assertRegex(r.stderr, r"o ffmpeg saiu com código 9 no quadro \d+/\d+")
        self.assertFalse(saida.exists())
        self.assertFalse(Path(str(saida) + ".parcial").exists())
        self.assertFalse(Path(str(saida) + ".da.json").exists())

    def test_04_ffmpeg_que_nao_le_a_entrada_e_abortado_pela_inatividade(self):
        falso = self.ffmpeg_falso("ffmpeg que dorme", "exec sleep 300")
        saida = self.anim / "dorme ção.mp4"
        t0 = time.monotonic()
        r = self.da_py("render", "--cena", "teste_movimento", "--saida", saida, "--dur", "6", "--escala", "0.25", "--inatividade", "3",
                       env={"VIDEO_OPS_FFMPEG": str(falso)}, timeout=90)
        self.assertEqual(r.returncode, 124, r.stderr)
        self.assertLess(time.monotonic() - t0, 45)
        self.assertIn("sem progresso", r.stderr)
        self.assertFalse(saida.exists())
        self.assertFalse(Path(str(saida) + ".parcial").exists())
        self.assertTrue(esperar(lambda: not self.processos_da_pasta(), 5))

    def test_05_laco_sem_fim_em_seek_e_abortado_pela_inatividade(self):
        cena = self.cena("laco", """
export const meta = { nome: 'laco', dur_padrao: 1, params: {} };
export function build(palco, p, ctx) { const t = ctx.texto('titulo', 'Laço', { tam: ctx.tam('h2') }); palco.appendChild(t); ctx.medir(t); }
export function seek(t) { if (t > 0.3) { for (;;) { /* nunca volta */ } } }
""")
        t0 = time.monotonic()
        r = self.da_py("render", "--cena", cena, "--saida", self.anim / "laco.png", "--quadro", "0.6", "--formato", "320x180",
                       "--sem-auditoria", "--inatividade", "3", timeout=90)
        self.assertEqual(r.returncode, 124, r.stderr)
        self.assertLess(time.monotonic() - t0, 45)
        self.assertIn("sem progresso", r.stderr)
        self.assertFalse((self.anim / "laco.png").exists())

    def test_06_erro_em_seek_tem_mensagem_de_uma_linha(self):
        cena = self.cena("quebra", """
export const meta = { nome: 'quebra', dur_padrao: 1, params: {} };
export function build(palco, p, ctx) { const t = ctx.texto('titulo', 'Quebra', { tam: ctx.tam('h2') }); palco.appendChild(t); ctx.medir(t); }
export function seek(t) { if (t > 0.2) throw new Error('faltou o elemento X'); }
""")
        r = self.da_py("render", "--cena", cena, "--saida", self.anim / "quebra.png", "--quadro", "0.75", "--formato", "320x180")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("a cena lançou erro em seek(t=0.750): faltou o elemento X", r.stderr)
        self.assertNotIn("    at ", r.stderr, "a pilha do page.evaluate não é mensagem acionável")
        r = self.da_py("render", "--cena", "titulo", "--saida", "/dev/null/x/y.png", "--quadro", "1", "--params", '{"titulo": "x"}')
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("não consegui criar a pasta de saída", r.stderr)
        self.assertNotIn("    at ", r.stderr)

    # -- 3. sinais: nada fica órfão ---------------------------------------------------
    def test_07_sigterm_no_da_py_render_mata_node_chromium_e_ffmpeg(self):
        saida = self.anim / "sinal term ção.mp4"
        p = self.render_em_segundo_plano(saida)
        familia = self.arvore(p.pid)
        self.assertGreaterEqual(len(familia), 4, "esperava da.py + node + Chromium + ffmpeg vivos")
        t0 = time.monotonic()
        p.send_signal(signal.SIGTERM)
        _, err = p.communicate(timeout=30)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM, err)
        self.assertLess(time.monotonic() - t0, 12)
        self.assertTrue(esperar(lambda: not any(trava._vivo(x) for x in familia), 5),
                        f"órfãos depois do SIGTERM: {[x for x in familia if trava._vivo(x)]}")
        self.assertFalse(Path(str(saida) + ".parcial").exists())
        self.assertFalse(saida.exists())
        dono = (trava.estado().get("dono") or {}).get("pid")
        self.assertNotEqual(dono, p.pid, "a trava continuou registrada no processo morto")

    def test_08_sigkill_no_dono_o_motor_aborta_sozinho(self):
        saida = self.anim / "sinal kill ção.mp4"
        p = self.render_em_segundo_plano(saida)
        familia = self.arvore(p.pid) - {p.pid}
        self.assertGreaterEqual(len(familia), 3)
        p.kill()                                                    # o dono não roda tratador nenhum
        p.communicate(timeout=10)
        self.assertTrue(esperar(lambda: not any(trava._vivo(x) for x in familia), 12),
                        f"o render seguiu órfão: {[x for x in familia if trava._vivo(x)]}")
        self.assertFalse(Path(str(saida) + ".parcial").exists())
        self.assertFalse(saida.exists())

    def test_09_sigterm_no_node_chamado_direto_atravessa_a_reexecucao(self):
        saida = self.anim / "sinal node ção.mp4"
        p = self.render_em_segundo_plano(saida, direto=True)          # node → trava.py → node → Chromium/ffmpeg
        familia = self.arvore(p.pid)
        self.assertGreaterEqual(len(familia), 5)
        p.send_signal(signal.SIGTERM)
        p.communicate(timeout=30)
        self.assertEqual(p.returncode, 128 + signal.SIGTERM)
        self.assertTrue(esperar(lambda: not any(trava._vivo(x) for x in familia), 5))
        self.assertFalse(Path(str(saida) + ".parcial").exists())

    # -- 4. cenas embutidas: função pura de t em toda a duração -------------------------
    def test_10_quadro_T_e_identico_ao_quadro_T_do_video_inclusive_na_saida(self):
        import numpy as np
        from PIL import Image
        pasta = self.anim / "pureza ção"
        pasta.mkdir(exist_ok=True)
        quadros = (30, 51, 57)                                      # repouso, janela de saída (1,5–2 s com dur 2) e fim
        jobs = []
        for cena, params in PARAMS.items():
            jobs.append({"cena": cena, "saida": f"{cena}.mov", "dur": 2, "formato": "480x270", "codec": "prores4444", "params": params})
            for n in quadros:
                jobs.append({"cena": cena, "saida": f"{cena} q{n}.png", "dur": 2, "formato": "480x270", "quadro": round(n * 1001 / 30000, 4), "params": params})
        (pasta / "fila.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        r = self.da_py("render", "--fila", pasta / "fila.json", timeout=240)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        for cena in PARAMS:
            for n in quadros:
                v = np.array(quadro_do_video(pasta / f"{cena}.mov", n, pasta / f"{cena} v{n}.png")).astype(int)
                q = np.array(Image.open(pasta / f"{cena} q{n}.png").convert("RGBA")).astype(int)
                pv, pq = v[..., :3] * v[..., 3:4] // 255, q[..., :3] * q[..., 3:4] // 255      # pré-multiplicado: alfa 0 não tem cor
                dif = np.maximum(np.abs(pv - pq).max(axis=2), np.abs(v[..., 3] - q[..., 3]))
                self.assertEqual(int((dif > 60).sum()), 0,
                                 f"{cena}: --quadro do quadro {n} difere do vídeo em {int((dif > 60).sum())} px (máx {int(dif.max())})")
                self.assertLess(float(dif.mean()), 2.5, f"{cena} quadro {n}: diferença média {dif.mean():.2f}")
        # o GC na janela de saída não pode sair vazio (era o sintoma: --quadro devolvia só a caixa, sem nome)
        gc = np.array(Image.open(pasta / "gc q51.png").convert("RGBA")).astype(int)
        visivel = gc[gc[..., 3] > 8][:, :3]
        self.assertGreater(len(visivel), 500)
        self.assertGreater(int(visivel.max(axis=1).max()) - int(visivel.max(axis=1).min()), 100, "o GC na saída perdeu o texto (caixa chapada)")

    def test_11_cena_que_depende_do_seek_anterior_e_reprovada(self):
        cena = self.cena("impura", """
export const meta = { nome: 'impura', dur_padrao: 2, params: {} };
const S = {};
export function build(palco, p, ctx) { S.t = ctx.texto('titulo', 'Impura', { tam: ctx.tam('h1') }); palco.appendChild(S.t); ctx.medir(S.t); S.ctx = ctx; }
export function seek(t) { if (t >= 1.2) return; S.t.style.opacity = (t / 1.2).toFixed(3); }   // depois de 1,2 s fica como o seek anterior deixou
""")
        r = self.da_py("render", "--cena", cena, "--saida", self.anim / "impura.png", "--quadro", "1.5", "--formato", "320x180")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("não é função pura de t", r.stderr)
        self.assertIn("CENA IMPURA", r.stderr)
        self.assertFalse((self.anim / "impura.png").exists())

    # -- 5. auditor sem escapes implícitos ------------------------------------------------
    def test_12_auditor_reprova_todos_os_caminhos_estruturais(self):
        jobs = [{"cena": "casos.js", "saida": f"aud {c}.png", "quadro": 0.5, "formato": "480x270", "params": {"caso": c}} for c in CASOS_RUINS + CASOS_BONS]
        jobs += [{"cena": "casos.js", "saida": f"aud {c}.mp4", "dur": 2, "formato": "320x180", "params": {"caso": c}} for c in CASOS_RUINS_EM_VIDEO]
        fila = self.anim / "fila auditor.json"
        fila.write_text(json.dumps(jobs), encoding="utf-8")
        r = self.da_py("render", "--fila", fila, "--json", timeout=240)
        self.assertEqual(r.returncode, 1, r.stderr[-2000:])
        rel = json.loads(r.stdout)
        ok = sorted(Path(x["saida"]).stem.replace("aud ", "") for x in rel["renderizados"])
        falhou = sorted(Path(x["saida"]).stem.replace("aud ", "") for x in rel["falhas"])
        self.assertEqual(ok, sorted(CASOS_BONS), f"passaram (só os ok_* podiam): {ok}\n{r.stderr[-1500:]}")
        self.assertEqual(falhou, sorted(CASOS_RUINS + CASOS_RUINS_EM_VIDEO))
        for trecho in ("::before", "body", "(shadow)", "<canvas>", "stop-color", "<img>", "<image> (SVG)", "url(", "border-image-source",
                       "hue-rotate()", "backdrop-filter", "mix-blend-mode", "data-da-livre no palco", "requestAnimationFrame",
                       "Math.random", "setTimeout", "Date.now", "new Date()", "performance.now", "ctx.rng",
                       "depois de trocar as variáveis", "rgba(var(--da-cor-<nome>-rgb), a)", "--da-cor-primara não existe", "declaração inválida:"):
            self.assertIn(trecho, r.stderr, f"faltou {trecho!r} no relatório do auditor")
        # D6: a forma única de alfa computa a cor da DA com o alfa pedido (medido no Chromium do kit, pelo layout do carimbo)
        layout = json.loads((self.anim / "aud ok_alfa_css.png.da.json").read_text(encoding="utf-8"))["parametros"]["layout"]
        self.assertEqual(layout["fundo_computado"], "rgba({}, {}, {}, 0.5)".format(*self.d.rgb("primaria")))
        self.assertEqual(layout["qa_computado"], "rgba({}, {}, {}, 0.86)".format(*self.d.rgb("fundo")))
        for c in CASOS_RUINS + CASOS_RUINS_EM_VIDEO:
            self.assertFalse(list(self.anim.glob(f"aud {c}.*")), f"{c}: peça reprovada não pode ser gravada nem carimbada")
        # data-da-livre explícito passa — e fica no carimbo para a conferência final listar
        carimbo = json.loads((self.anim / "aud ok_img_livre.png.da.json").read_text(encoding="utf-8"))
        self.assertEqual(carimbo["auditoria"], "ok")
        livres = carimbo["parametros"]["livres"]
        self.assertEqual(len(livres), 1, livres)
        self.assertEqual((livres[0]["tag"], livres[0]["motivo"]), ("img", "foto de teste"))
        self.assertIn("img", livres[0]["seletor"])
        self.assertGreater(livres[0]["area"], 0)
        self.assertEqual(json.loads((self.anim / "aud ok_alfa.png.da.json").read_text(encoding="utf-8"))["parametros"]["livres"], [])
        r = self.da_py("conferir-carimbo", self.anim / "aud ok_img_livre.png", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        peca = json.loads(r.stdout)["pecas"][0]
        self.assertEqual(peca["livres"][0]["motivo"], "foto de teste")
        self.assertIn("data-da-livre", peca["detalhe"])

    def test_13_amostragem_cobre_as_ancoras_e_uma_grade_fina(self):
        r = self.da_py("render", "--cena", "gc", "--saida", self.anim / "amostras.mov", "--dur", "4", "--formato", "320x180",
                       "--params", json.dumps(PARAMS["gc"]))
        self.assertEqual(r.returncode, 0, r.stderr)
        import re
        m = re.search(r"auditoria ok \((\d+) instantes?, pureza em (\d+), quietude em 1\)", r.stderr)
        self.assertIsNotNone(m, r.stderr)
        self.assertGreaterEqual(int(m.group(1)), 17)                 # grade de 0,25 s em 4 s (17) + âncoras; antes eram 5
        self.assertLessEqual(int(m.group(1)), 64)                    # teto
        self.assertGreaterEqual(int(m.group(2)), 3)

    def test_20_auditor_ve_o_que_o_estilo_computado_nao_mostra_e_o_que_anima_fora_do_seek(self):
        """Fecho. Eram `auditoria: ok`: SMIL, laço por MessageChannel, crypto, document.timeline, controles nativos (azul e
        verde do sistema), `content: url()` no elemento, list-style-image, ::selection — e GIF animado dentro de data-da-livre.
        Da mesma família, fechados juntos: event.timeStamp, Intl.DateTimeFormat sem data, Temporal.Now e imagem por paint()."""
        from PIL import Image
        pasta = self.anim / "fecho ção"
        pasta.mkdir(exist_ok=True)
        (pasta / "casos2.js").write_text(CASOS2_JS, encoding="utf-8")
        # da-livre:inicio — imagens de teste (2 quadros = animada; 1 quadro = parada)
        a, b = Image.new("RGB", (60, 60), (255, 0, 0)), Image.new("RGB", (60, 60), (0, 0, 255))
        # da-livre:fim
        a.save(pasta / "anima é.gif", save_all=True, append_images=[b], duration=700, loop=0)      # lenta: a quietude de 120 ms não veria
        a.save(pasta / "anima.png", save_all=True, append_images=[b], duration=700, loop=0)         # APNG
        a.save(pasta / "parada.gif")
        img = {"v_gif": "anima é.gif", "v_gif_fundo": "anima é.gif", "v_apng": "anima.png", "ok_gif_parado": "parada.gif"}
        jobs = [{"cena": "casos2.js", "saida": f"f {c}.png", "quadro": 0.5, "formato": "480x270",
                 "params": {"caso": c, **({"img": img[c]} if c in img else {})}} for c in [*CASOS2_RUINS, *CASOS2_BONS]]
        (pasta / "fila.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        r = self.da_py("render", "--fila", pasta / "fila.json", "--json", timeout=420)
        self.assertEqual(r.returncode, 1, r.stderr[-2000:])
        rel = json.loads(r.stdout)
        ok = sorted(Path(x["saida"]).stem[2:] for x in rel["renderizados"])
        self.assertEqual(ok, sorted(CASOS2_BONS), f"passaram (só os ok_* podiam): {ok}\n{r.stderr[-2500:]}")
        self.assertEqual(sorted(Path(x["saida"]).stem[2:] for x in rel["falhas"]), sorted(CASOS2_RUINS))
        # cada caso reprova pelo motivo certo: o trecho esperado aparece no bloco de log DAQUELE job
        blocos = r.stderr.split("[casos2.js] 480x270")
        self.assertEqual(len(blocos), len(jobs) + 1, "um bloco de log por job")
        for (caso, trecho), bloco in zip(CASOS2_RUINS.items(), blocos[1:]):
            self.assertTrue(any(alt in bloco for alt in trecho.split("|")), f"{caso}: faltou {trecho!r} no relatório\n{bloco[-900:]}")
            self.assertFalse(list(pasta.glob(f"f {caso}.*")), f"{caso}: peça reprovada não pode ser gravada nem carimbada")
        # o que foi declarado livre passa — e fica no carimbo
        livres = json.loads((pasta / "f ok_emoji_livre.png.da.json").read_text(encoding="utf-8"))["parametros"]["livres"]
        self.assertEqual([(x["tag"], x["motivo"]) for x in livres], [("span", "emoji")])
        livres = json.loads((pasta / "f ok_progress_livre.png.da.json").read_text(encoding="utf-8"))["parametros"]["livres"]
        self.assertEqual([(x["tag"], x["motivo"]) for x in livres], [("progress", "captura de interface")])
        self.assertEqual(json.loads((pasta / "f ok_lista.png.da.json").read_text(encoding="utf-8"))["auditoria"], "ok")

    # -- 6. identidade da DA no carimbo ----------------------------------------------------
    def test_14_da_que_muda_durante_o_render_nao_e_carimbada(self):
        saida = self.anim / "corrida ção.mp4"
        da_json = self.proj / "da" / "da.json"
        original = da_json.read_text(encoding="utf-8")
        p = self.render_em_segundo_plano(saida, dur=5)
        try:
            dados = json.loads(original)
            dados["cor"]["paleta"]["primaria"] = "#00C7FF"
            da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
            _, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 1, err)
            self.assertIn("a DA mudou", err)
            self.assertFalse(saida.exists(), "a peça desenhada com a DA antiga não pode virar a saída")
            self.assertFalse(Path(str(saida) + ".da.json").exists(), "nem ser carimbada com a DA nova")
            self.assertFalse(Path(str(saida) + ".parcial").exists())
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
            da_json.write_text(original, encoding="utf-8")
            da.compilar_da(da_json)
        # API: carimbar com a identidade esperada recusa quando a DA atual é outra, e aceita quando é a mesma
        peca = self.anim / "esperado.png"
        peca.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
        d = da.carregar(self.proj)
        with self.assertRaises(da.DAErro) as e:
            da.carimbar(peca, "teste", "horizontal", {}, "n/a", da=d, sha_esperado="0" * 64)
        self.assertIn("a DA mudou", str(e.exception))
        self.assertFalse(Path(str(peca) + ".da.json").exists())
        da.carimbar(peca, "teste", "horizontal", {}, "n/a", da=d, sha_esperado=d.sha256)
        self.assertTrue(Path(str(peca) + ".da.json").is_file())

    def test_15_da_alterada_depois_de_aprovada_avisa_no_render_e_reprova_no_conferir(self):
        proj = self.base / "projeto aprovação é"
        da.iniciar(proj, nome="Aprovação", base="quadro-negro")
        peca = proj / "animacoes" / "antes.png"
        args = ["render", "--cena", "titulo", "--saida", peca, "--quadro", "1", "--formato", "320x180", "--params", '{"titulo": "Antes"}']
        self.assertEqual(self.da_py(*args, cwd=proj).returncode, 0)
        # DA nunca aprovada: ok sem a exigência, reprovada com ela (é como a conferência final chama)
        r = self.da_py("conferir-carimbo", peca, cwd=proj)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = self.da_py("conferir-carimbo", peca, "--exigir-aprovada", cwd=proj)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("DA NÃO APROVADA", r.stdout)
        self.assertEqual(self.da_py("aprovar", cwd=proj).returncode, 0)
        self.assertEqual(self.da_py("conferir-carimbo", peca, "--exigir-aprovada", cwd=proj).returncode, 0)
        # edita depois de aprovar
        da_json = proj / "da" / "da.json"
        dados = json.loads(da_json.read_text(encoding="utf-8"))
        dados["cor"]["paleta"]["destaque"] = "#12AB34"
        da_json.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        depois = proj / "animacoes" / "depois.png"
        r = self.da_py("render", "--cena", "titulo", "--saida", depois, "--quadro", "1", "--formato", "320x180", "--params", '{"titulo": "Depois"}', cwd=proj)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DA ALTERADA DEPOIS DA APROVAÇÃO", r.stderr)      # aviso visível no render
        carimbo = json.loads(Path(str(depois) + ".da.json").read_text(encoding="utf-8"))
        self.assertTrue(carimbo["da_alterada_apos_aprovacao"])
        self.assertFalse(carimbo["da_aprovada"])
        r = self.da_py("conferir-carimbo", depois, "--json", cwd=proj)
        self.assertEqual(r.returncode, 1, r.stdout)
        rel = json.loads(r.stdout)
        self.assertEqual(rel["pecas"][0]["estado"], "da_alterada")
        self.assertTrue(rel["da_alterada_apos_aprovacao"])
        r = self.da_py("conferir-carimbo", depois, cwd=proj)
        self.assertIn("DA ALTERADA APÓS APROVAÇÃO", r.stdout)
        # o caminho de volta: revisar + aprovar
        self.assertEqual(self.da_py("revisar", cwd=proj).returncode, 0)
        self.assertEqual(self.da_py("aprovar", cwd=proj).returncode, 0)
        r = self.da_py("conferir-carimbo", depois, "--exigir-aprovada", cwd=proj)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    # -- 7. barras no vertical: o crédito tem faixa própria --------------------------------
    def test_16_barras_vertical_com_8_categorias_o_credito_nao_cai_no_titulo(self):
        estados = ["São Paulo", "Minas Gerais", "Rio de Janeiro", "Bahia", "Paraná", "Rio Grande do Sul", "Pernambuco", "Santa Catarina"]
        params = {"titulo": "Quanto cada estado recebe de volta", "fonte": "Tesouro Nacional, 2024", "casas": 2,
                  "dados": [{"rotulo": e, "valor": round(0.3 + i * 0.27, 2)} for i, e in enumerate(estados)]}
        for preset in ("neon-shorts", "dossie"):                     # crédito em cima (neon) e embaixo (os outros)
            proj = self.base / f"projeto barras {preset} ção"
            da.iniciar(proj, nome=f"Barras {preset}", base=preset)
            d = da.carregar(proj)
            saida = proj / "animacoes" / "barras v8.png"
            r = self.da_py("render", "--cena", "barras", "--saida", saida, "--formato", "vertical", "--quadro", "2.5", "--dur", "5",
                           "--escala", "0.25", "--params", json.dumps(params, ensure_ascii=False), cwd=proj)
            self.assertEqual(r.returncode, 0, r.stderr)
            layout = json.loads(Path(str(saida) + ".da.json").read_text(encoding="utf-8"))["parametros"]["layout"]
            c, t, b = layout["credito"], layout["titulo"], layout["bloco"]
            m = d.margens("vertical")
            self.assertFalse(c["y"] < b["y1"] and b["y"] < c["y1"], f"{preset}: o crédito ({c}) sobrepõe o bloco do gráfico ({b})")
            self.assertFalse(c["y"] < t["y1"] and t["y"] < c["y1"], f"{preset}: o crédito ({c}) sobrepõe o título ({t})")
            for nome, rect in (("bloco", b), ("crédito", c)):
                self.assertGreaterEqual(rect["y"], m["y0"] - 1.5, f"{preset}: {nome} acima da zona segura")
                self.assertLessEqual(rect["y1"], m["y1"] + 1.5, f"{preset}: {nome} abaixo da zona segura")

    # -- 8. video.executar: stdin nunca fica pendurado ----------------------------------------
    def test_17_video_executar_com_entrada_por_pipe(self):
        import io
        from PIL import Image
        saida = self.proj / "render" / "t pipe.mp4"
        args = [*video.args_png_para_yuv420("30"), *video.args_encode("30", audio=False)]
        t0 = time.monotonic()
        with self.assertRaises(da.DAErro) as e:                      # antes: ffmpeg esperando o stdin para sempre, com a trava presa
            video.executar(args, saida, rotulo="t_pipe")
        self.assertIn("entrada", str(e.exception))
        self.assertLess(time.monotonic() - t0, 2)

        def quadros(n=12):
            for i in range(n):
                buf = io.BytesIO()
                Image.new("RGB", (64, 64), self.d.rgb("primaria") if i % 2 else self.d.rgb("fundo")).save(buf, "PNG")
                yield buf.getvalue()

        video.executar(args, saida, rotulo="t_pipe", entrada=quadros())
        info = video.sondar(saida)
        self.assertEqual((info["largura"], info["altura"], info["quadros"]), (64, 64, 12))
        self.assertFalse(saida.with_name("t pipe.parcial.mp4").exists())
        # ffmpeg que sai antes de ler tudo (argumento inválido): erro limpo, sem travar na escrita
        with self.assertRaises(da.DAErro) as e:
            video.executar([*video.args_png_para_yuv420("30"), "-c:v", "codec_que_nao_existe"], self.proj / "render" / "t ruim.mp4", entrada=quadros(200))
        self.assertIn("ffmpeg falhou", str(e.exception))

    def test_18_video_executar_mata_ffmpeg_sem_progresso(self):
        falso = self.ffmpeg_falso("ffmpeg parado", "exec sleep 300")
        original = video.FFMPEG
        video.FFMPEG = str(falso)
        try:
            t0 = time.monotonic()
            with self.assertRaises(da.DAErro) as e:
                video.executar(["-i", "nada.mp4"], self.proj / "render" / "t parado.mp4", rotulo="parado", inatividade=2)
            self.assertIn("travou", str(e.exception))
            self.assertIn("sem progresso", str(e.exception))
            self.assertLess(time.monotonic() - t0, 15)
        finally:
            video.FFMPEG = original
        self.assertFalse((self.proj / "render" / "t parado.parcial.mp4").exists())

    # -- 9. pequenas divergências doc × código --------------------------------------------------
    def test_19_conferir_ignora_temporarios_e_o_build_da_da(self):
        (self.proj / "render").mkdir(exist_ok=True)
        (self.proj / "render" / "meio.parcial.mp4").write_bytes(b"0" * 32)      # nome do temporário do video.executar
        (self.proj / "render" / "outro.mp4.parcial").write_bytes(b"0" * 32)     # nome do temporário do motor
        rel = da.conferir_carimbo([self.proj / "render"], da=self.proj)
        self.assertFalse([p for p in rel["pecas"] if "parcial" in p["arquivo"]], rel["pecas"])
        (self.proj / "da" / "build" / "prancha").mkdir(parents=True, exist_ok=True)
        (self.proj / "da" / "build" / "prancha" / "antes.png").write_bytes(b"0" * 32)
        rel = da.conferir_carimbo([self.proj / "da"], da=self.proj)
        self.assertFalse([p for p in rel["pecas"] if "/build/" in p["arquivo"]], rel["pecas"])
        r = self.da_py("grade", "--formato", "640x360")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), self.d.grade(640, 360))


if __name__ == "__main__":
    unittest.main(verbosity=2)
