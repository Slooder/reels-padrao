#!/usr/bin/env python3
"""Trilha e efeitos sintetizados a partir de videos/<nome>/cues.json → audio/<nome>.wav
48 kHz estéreo, masterizado a −14 LUFS / −1,5 dBTP. Nada de samples: tudo é síntese.
uso: audio/.venv/bin/python audio/synth.py [prefixos...]
"""
import json, os, sys, subprocess, re
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
DORIAN = [0, 2, 3, 5, 7, 9, 10]

def N(d): return max(1, int(round(d * SR)))
def tt(d): return np.arange(N(d)) / SR
def db(x): return 10 ** (x / 20)
def mtof(m): return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)
def peak(x): return float(np.max(np.abs(x))) + 1e-12

# ── filtros ──
def _sos(kind, f, o=2): return signal.butter(o, f, btype=kind, fs=SR, output='sos')
def lp(x, f, o=2): return signal.sosfilt(_sos('lowpass', min(f, SR * .45), o), x)
def hp(x, f, o=2): return signal.sosfilt(_sos('highpass', max(f, 10), o), x)
def bp(x, lo, hi, o=2): return signal.sosfilt(_sos('bandpass', [max(lo, 10), min(hi, SR * .45)], o), x)
def peq(x, f, gain_db, q=1.0):  # pico RBJ
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f / SR; al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]; a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], x)

def stft_filter(x, lo_fn, hi_fn, nfft=1024, slope=0.35):
    """band-pass variável no tempo (receita da casa): máscara cosseno em log2, OLA normalizado"""
    hop = nfft // 2; win = np.hanning(nfft); n = len(x); pad = np.concatenate([x, np.zeros(nfft)])
    out = np.zeros(len(pad)); norm = np.zeros(len(pad)); fr = np.fft.rfftfreq(nfft, 1 / SR); lf = np.log2(np.maximum(fr, 1))
    for i in range(0, n, hop):
        tc = (i + nfft / 2) / SR; lo, hi = lo_fn(tc), hi_fn(tc)
        m = np.clip((lf - np.log2(lo)) / slope + .5, 0, 1) * np.clip((np.log2(hi) - lf) / slope + .5, 0, 1)
        m = .5 - .5 * np.cos(np.pi * m)
        out[i:i + nfft] += np.fft.irfft(np.fft.rfft(pad[i:i + nfft] * win) * m, nfft) * win; norm[i:i + nfft] += win * win
    norm[norm < 1e-6] = 1.0
    return (out / norm)[:n]

def sweep_lp(x, f0, f1, curve=1.0):
    """passa-baixa com corte varrendo de f0 a f1 (exponencial) ao longo do sinal"""
    D = len(x) / SR
    return stft_filter(x, lambda t: 20, lambda t: f0 * (f1 / f0) ** ((min(t, D) / D) ** curve), 2048, .5)

# ── osciladores (PolyBLEP) ──
def _blep(ph, dt):
    y = np.zeros_like(ph); m = ph < dt; t = ph[m] / dt[m]; y[m] = t + t - t * t - 1
    m = ph > 1 - dt; t = (ph[m] - 1) / dt[m]; y[m] = t * t + t + t + 1; return y
def osc(kind, f, d, ph0=0.0):
    n = N(d); f = np.full(n, float(f)) if np.ndim(f) == 0 else np.asarray(f, float)[:n]
    if len(f) < n: f = np.pad(f, (0, n - len(f)), mode='edge')
    dt = np.clip(f / SR, 1e-9, .5); ph = (np.cumsum(dt) + ph0) % 1.0
    if kind == 'sin': return np.sin(2 * np.pi * ph)
    if kind == 'tri': return 4 * np.abs(ph - .5) - 1
    if kind == 'saw': return 2 * ph - 1 - _blep(ph, dt)
    if kind == 'sq': return np.where(ph < .5, 1., -1.) + _blep(ph, dt) - _blep((ph + .5) % 1, dt)
    if kind == 'pulse25': return np.where(ph < .25, 1., -1.) + _blep(ph, dt) - _blep((ph + .75) % 1, dt)
    raise ValueError(kind)
def env(d, a=.005, dec=.1, s=0., r=.05, gate=None):
    n = N(d); t = np.arange(n) / SR; g = gate if gate is not None else d - r
    e = np.where(t < a, t / max(a, 1e-6), s + (1 - s) * np.exp(-(t - a) / max(dec, 1e-6)))
    rel = np.clip(1 - (t - g) / max(r, 1e-6), 0, 1); return e * np.where(t > g, rel, 1)
def fade(x, a=.004, b=.004):
    na, nb = min(N(a), len(x)), min(N(b), len(x)); x = x.copy(); x[:na] *= np.linspace(0, 1, na); x[len(x) - nb:] *= np.linspace(1, 0, nb); return x
def sat(x, k=1.5): return np.tanh(k * x) / np.tanh(k)

R = np.random.default_rng(7)
def noise(d): return R.standard_normal(N(d))
def pink(d):
    n = N(d); s = np.fft.rfft(R.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR); s[1:] /= np.sqrt(f[1:]); s[0] = 0
    x = np.fft.irfft(s, n); return x / peak(x)

# ── reverb por convolução com IR sintetizado (estéreo descorrelacionado) ──
_IR = {}
def ir(size):
    if size not in _IR:
        d = size; t = tt(d); irs = []
        for k in range(2):
            n = np.random.default_rng(11 + k).standard_normal(len(t)) * np.exp(-t / (d / 6.9))
            n = lp(n, 7000) * .7 + lp(n, 2500) * .3; n[:N(.012)] *= np.linspace(0, 1, N(.012)); irs.append(n / np.sqrt(np.sum(n * n)))
        _IR[size] = irs
    return _IR[size]
def reverb(x, size=1.8, mix=.25):
    L, Rr = ir(size); wl = signal.fftconvolve(x, L)[:len(x)]; wr = signal.fftconvolve(x, Rr)[:len(x)]
    return np.stack([x * (1 - mix) + wl * mix, x * (1 - mix) + wr * mix])

# ── barramento estéreo ──
class Bus:
    def __init__(self, d): self.x = np.zeros((2, N(d) + N(4)))
    def add(self, t, sig, g=1.0, pan=0.0):
        i = N(max(t, 0)) if t > 0 else 0
        if np.ndim(sig) == 1: sig = np.stack([sig * min(1, 1 - pan), sig * min(1, 1 + pan)])
        if t < 0: sig = sig[:, N(-t):]
        j = min(i + sig.shape[1], self.x.shape[1])
        if j > i: self.x[:, i:j] += sig[:, :j - i] * g
        return self

# ════════════════ INSTRUMENTOS ════════════════
def kick(f0=150, f1=45, dec=.32, click=.35, d=.6):
    t = tt(d); f = f1 + (f0 - f1) * np.exp(-t / .035); x = osc('sin', f, d) * np.exp(-t / dec)
    x += click * hp(noise(d), 1500) * np.exp(-t / .004); return sat(x, 1.6)
def snare(tone=185, d=.35, dec=.14):
    t = tt(d); x = .55 * osc('sin', tone * (1 + .4 * np.exp(-t / .01)), d) * np.exp(-t / .06) + bp(noise(d), 1200, 9000) * np.exp(-t / dec)
    return sat(x, 1.3)
def clap(d=.4):
    t = tt(d); e = np.zeros(len(t))
    for k, o in enumerate([0, .011, .022, .034]): e += (t >= o) * np.exp(-np.clip(t - o, 0, None) / (.008 if k < 3 else .12))
    return bp(noise(d), 900, 6000) * e
def hat(open_=False, d=None):
    d = d or (.45 if open_ else .08); t = tt(d); return hp(noise(d), 7500, 4) * np.exp(-t / (.16 if open_ else .022))
def tom(f=110, d=.6): t = tt(d); return sat(osc('sin', f * (1 + .6 * np.exp(-t / .03)), d) * np.exp(-t / .22) + .2 * lp(noise(d), 800) * np.exp(-t / .05), 1.4)
def taiko(d=1.2): t = tt(d); return sat(osc('sin', 60 * (1 + .9 * np.exp(-t / .04)), d) * np.exp(-t / .4) + .5 * lp(noise(d), 600) * np.exp(-t / .06), 2)
def shaker(d=.12): t = tt(d); return bp(noise(d), 5000, 12000) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 2

def supersaw(m, d, voices=5, det=.12, kind='saw'):
    x = np.zeros(N(d))
    for v in range(voices): cents = (v - (voices - 1) / 2) * det * 100 / max(1, (voices - 1) / 2); x += osc(kind, mtof(m) * 2 ** (cents / 1200), d, ph0=(v * .37) % 1)
    return x / voices
def pad(ms, d, a=1.2, r=1.5, cut=1800, bright=0.0, kind='saw'):
    x = sum(supersaw(m, d + r) for m in ms) / max(1, len(ms)); x = lp(x, cut, 2)
    if bright: x += bright * hp(x, 3000)
    return x * env(d + r, a, 9, 1, r, gate=d)
def strings(ms, d, a=.8, r=1.2, cut=3200):
    t = tt(d + r); x = 0
    for m in ms:
        vib = 1 + .004 * np.sin(2 * np.pi * 5.2 * t + m)
        for k in range(3): x = x + osc('saw', mtof(m) * vib * 2 ** ((k - 1) * 9 / 1200), d + r, ph0=k * .3)
    x = lp(peq(x / (3 * len(ms)), 900, 3, .7), cut, 2); return x * env(d + r, a, 9, 1, r, gate=d)
def pluck(m, d=.5, bright=5000, dark=400, dec=.18, kind='saw'):
    x = osc(kind, mtof(m), d) + .5 * osc(kind, mtof(m) * 1.004, d); e = np.exp(-tt(d) / dec)
    return (lp(x, bright) * e + lp(x, dark) * (1 - e)) * env(d, .002, dec * 1.8, 0, .02) * .6
def bass(m, d, cut=600, kind='saw', sub=.6):
    x = lp(osc(kind, mtof(m), d), cut, 2) * .7 + sub * osc('sin', mtof(m), d); return sat(x * env(d, .004, 9, 1, .03), 1.2)
def epiano(m, d=1.2, vel=1.0):
    t = tt(d); f = mtof(m); I = 2.2 * vel * np.exp(-t / .5)
    x = np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * t)) * np.exp(-t / 1.4) + .25 * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t / .03)
    return x * env(d, .002, 9, 1, .15) * .5
def bell(m, d=2.5, ratio=3.5, idx=3):
    t = tt(d); f = mtof(m); I = idx * np.exp(-t / .8); return np.sin(2 * np.pi * f * t + I * np.sin(2 * np.pi * f * ratio * t)) * np.exp(-t / 1.1) * .4
def glock(m, d=1.6):
    t = tt(d); f = mtof(m); return (np.sin(2 * np.pi * f * t) * np.exp(-t / .9) + .35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t / .25) + .15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t / .08)) * .4
def marimba(m, d=.8):
    t = tt(d); f = mtof(m); return (np.sin(2 * np.pi * f * t) * np.exp(-t / .35) + .3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / .06) + .2 * np.sin(2 * np.pi * f * 10 * t) * np.exp(-t / .01)) * .5
def piano(m, d=2.0, vel=1.0):
    t = tt(d); f = mtof(m); x = np.zeros(len(t))
    for k in range(1, 9): x += (vel ** (k * .3)) / k ** 1.2 * np.sin(2 * np.pi * f * k * (1 + .0004 * k * k) * t) * np.exp(-t * (.6 + k * .55))
    x += .15 * lp(noise(d), 2500) * np.exp(-t / .01); return x * env(d, .002, 9, 1, .2) * .35
def pizz(m, d=.5): t = tt(d); x = lp(osc('saw', mtof(m), d), 1600) * np.exp(-t / .12); return x * .7
def chip(m, d, kind='pulse25', vib=0.0):
    t = tt(d); f = mtof(m) * (1 + vib * np.sin(2 * np.pi * 6 * t) * np.clip(t / .15, 0, 1)); return osc(kind, f, d) * env(d, .002, 9, 1, .02) * .35
def chipnoise(d=.12, dec=.04):
    n = N(d); x = np.repeat(R.choice([-1., 1.], n // 6 + 1), 6)[:n]; return x * np.exp(-tt(d) / dec) * .4
def brass(ms, d, a=.06, cut0=300, cut1=2600):
    x = sum(supersaw(m, d, 3, .06) for m in ms) / len(ms); return sat(sweep_lp(x, cut0, cut1, .6), 2.0) * env(d, a, 9, 1, .4)

# ════════════════ EFEITOS (receitas da casa + extras) ════════════════
def fx_whoosh(d=.45, f0=300, f1=3000, a=.02, dec=.11, rv=.3):
    t = tt(d); x = stft_filter(noise(d), lambda u: f0 * (f1 / f0) ** (u / d) / 2 ** .6, lambda u: f0 * (f1 / f0) ** (u / d) * 2 ** .6, 1024)
    x = x * np.clip(t / a, 0, 1) * np.exp(-np.clip(t - d * .55, 0, None) / dec); return reverb(x, 1.0, rv)[0]
def fx_impact(d=1.2, f0=80, f1=45, tr=.35):
    t = tt(d); f = f1 + (f0 - f1) * np.clip(1 - t / .35, 0, 1); x = osc('sin', f, d) * np.exp(-t / .38)
    x += tr * bp(noise(d), 120, 2500) * np.exp(-t / .012); return sat(x, 1.8) * env(d, .002, 9, 1, .15)
def fx_riser(d=.8, f0=200, f1=6000):
    t = tt(d); x = stft_filter(noise(d), lambda u: f0 * (f1 / f0) ** (u / d) / 2 ** .8, lambda u: f0 * (f1 / f0) ** (u / d) * 2 ** .8, 1024)
    x = x * (t / d) ** 1.6; x[-N(.003):] *= np.linspace(1, 0, N(.003)); return x
def fx_tick(d=.06): t = tt(d); return stft_filter(noise(d), lambda u: 2000, lambda u: 6000, 512, .25) * np.clip(t / .001, 0, 1) * np.exp(-t / .008)
def fx_blip(f1=880, f2=1320):
    x = np.zeros(N(.12))
    for f, o in [(f1, .01), (f2, .055)]: s = tt(.04); x[N(o):N(o) + len(s)] += np.sin(2 * np.pi * f * s) * np.sin(np.pi * s / .04) ** 1.2
    return x
def fx_paper(d=.25):
    t = tt(d); x = bp(pink(d), 1000, 4000); e = .7 * np.exp(-((t - .07) / .06) ** 2) + .5 * np.exp(-t / .09)
    gran = 1 + .35 * bp(noise(d), 20, 120) / 3; return x * e * gran
def fx_key():  # tecla de máquina de escrever: batida metálica + baque
    d = .16; t = tt(d); x = bp(noise(d), 1800, 7000) * np.exp(-t / .006) + .6 * osc('sin', 220 * (1 + np.exp(-t / .005)), d) * np.exp(-t / .03)
    x += .25 * bp(noise(d), 3000, 5000) * np.exp(-np.clip(t - .018, 0, None) / .01) * (t > .018); return sat(x, 1.5)
def fx_carriage():  # alavanca + campainha
    d = 1.1; t = tt(d); x = np.zeros(len(t))
    for k in range(9): o = .02 + k * .028; x += (t > o) * bp(noise(d), 2500, 8000) * np.exp(-np.clip(t - o, 0, None) / .004) * .5
    o = .32; x += (t > o) * (np.sin(2 * np.pi * 2900 * (t - o)) + .5 * np.sin(2 * np.pi * 4100 * (t - o))) * np.exp(-np.clip(t - o, 0, None) / .35) * .35
    return x
def fx_marker(d=.32):
    t = tt(d); f = 2400 + 700 * np.sin(2 * np.pi * 23 * t); x = stft_filter(noise(d), lambda u: 1800, lambda u: 5200, 512, .3)
    x = x * (.6 + .4 * np.sin(2 * np.pi * 37 * t)) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** .6; x += .15 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d); return x
def fx_thread(): d = .7; t = tt(d); return lp(osc('saw', 98 * (1 + .03 * np.exp(-t / .05)), d), 1400) * np.exp(-t / .2) * .8 + .2 * bp(noise(d), 2000, 6000) * np.exp(-t / .01)
def fx_switch(): d = .2; t = tt(d); return bp(noise(d), 1500, 9000) * np.exp(-t / .003) + .6 * bp(noise(d), 800, 3000) * np.exp(-np.clip(t - .045, 0, None) / .004) * (t > .045)
def fx_swell(d=1.6):
    t = tt(d); x = stft_filter(noise(d), lambda u: 3000, lambda u: 14000, 1024, .5) * (t / d) ** 2.2; x[-N(.15):] *= np.linspace(1, 0, N(.15)); return reverb(x, 1.6, .4)[0]
def fx_braam(d=3.6, root=38):
    x = brass([root, root + 7, root + 12, root - 12], d, a=.08, cut0=200, cut1=1800); x += .5 * fx_impact(d, 70, 38, .2); return x
def fx_hit_soft(d=1.4): t = tt(d); x = osc('sin', 55 * (1 + .5 * np.exp(-t / .02)), d) * np.exp(-t / .5) + .2 * lp(noise(d), 1200) * np.exp(-t / .03); return sat(x, 1.4)
def fx_cut(): d = .5; t = tt(d); return osc('sin', 48 * (1 + 1.2 * np.exp(-t / .015)), d) * np.exp(-t / .12) + .25 * lp(noise(d), 900) * np.exp(-t / .01)
def fx_glitch(d=.3):
    x = np.zeros(N(d)); pos = 0
    while pos < len(x): L = N(R.uniform(.008, .04)); k = R.integers(0, 3); seg = (osc('sq', R.uniform(80, 1800), L / SR) if k == 0 else bp(noise(L / SR), R.uniform(300, 2000), R.uniform(3000, 12000)) if k == 1 else np.zeros(L)); x[pos:pos + L] += seg[:len(x) - pos]; pos += L
    return np.round(x * 8) / 8 * .7
def fx_pop(f=600): d = .12; t = tt(d); return osc('sin', f * (1 + 1.5 * np.exp(-t / .006)), d) * np.exp(-t / .03)
def fx_click(): d = .05; t = tt(d); return bp(noise(d), 2500, 9000) * np.exp(-t / .0025) + .4 * osc('sin', 1800, d) * np.exp(-t / .006)
def fx_chime(m=84): return bell(m, 2.4, 2.0, 1.5) + .6 * bell(m + 7, 2.4, 2.0, 1.2)
def fx_coin(): d = .9; t = tt(d); return (np.sin(2 * np.pi * 1975 * t) * (t < .08) + np.sin(2 * np.pi * 2637 * t) * (t >= .08)) * np.exp(-np.clip(t - .08, 0, None) / .25) * .4
def fx_sparkle(d=1.2):
    x = np.zeros(N(d))
    for k in range(14): o = R.uniform(0, d * .7); m = R.integers(88, 104); s = glock(m, .6) * .5; i = N(o); x[i:i + len(s)] += s[:len(x) - i]
    return x
def fx_sub_drop(d=1.6): t = tt(d); return sat(osc('sin', 30 + 90 * np.exp(-t / .25), d) * np.exp(-t / .7), 1.3)
def fx_boom(d=2.4): return fx_impact(d, 90, 32, .5) + .4 * reverb(lp(noise(d), 400) * np.exp(-tt(d) / .25), 2.4, .6)[0]
def fx_shutter(): d = .25; t = tt(d); return bp(noise(d), 1500, 8000) * (np.exp(-t / .006) + .7 * np.exp(-np.clip(t - .07, 0, None) / .008) * (t > .07))
def fx_swoosh(d=.25): return fx_whoosh(d, 600, 5000, .01, .05, .2)
def fx_heart(): d = .7; t = tt(d); return kick(70, 38, .12, 0, d) + .6 * np.roll(kick(65, 36, .1, 0, d), N(.24))
def fx_bubble(): d = .18; t = tt(d); return np.sin(2 * np.pi * np.cumsum(500 + 1600 * (t / d) ** .5) / SR) * np.sin(np.pi * t / d) * .6
def fx_zap(d=.35): t = tt(d); return osc('saw', 1800 * np.exp(-t / .06) + 120, d) * np.exp(-t / .1) * .5
def fx_type(): d = .05; t = tt(d); return bp(noise(d), 2000, 8000) * np.exp(-t / .004) + .3 * osc('sin', 300, d) * np.exp(-t / .01)
def fx_ding(): return bell(88, 1.8, 2.0, 1.0)
def fx_scratch(d=.4): t = tt(d); return stft_filter(noise(d), lambda u: 800 + 3000 * abs(np.sin(u * 30)), lambda u: 6000, 512, .4) * np.sin(np.pi * t / d)
def fx_reverse(d=1.0): x = fx_impact(d, 80, 50, .5)[::-1] * (tt(d) / d) ** 2; return x
def fx_tape_stop(d=.6): t = tt(d); return osc('saw', 220 * (1 - t / d) ** 2 + 20, d) * (1 - t / d) * .5

def fx_bird():  # canto curto de passarinho: 3 a 5 assobios com glissando
    x = np.zeros(N(.9)); r = np.random.default_rng(int(R.integers(0, 1e6)))
    for k in range(int(r.integers(3, 6))):
        o = k * .13 + r.uniform(0, .03); d = r.uniform(.05, .1); t = tt(d); f0 = r.uniform(2600, 4200)
        f = f0 * (1 + .35 * np.sin(np.pi * t / d) * (1 if k % 2 else -1)); s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 1.5
        i = N(o); x[i:i + len(s)] += s[:len(x) - i]
    return reverb(x, 1.4, .35)[0]

def fx_bark(f0=560, n=1):  # latido: pulso glotal rico em harmônicos + formantes + sopro, queda de altura
    x = np.zeros(N(.24 + .2 * (n - 1)))
    for k in range(n):
        d = .2; t = tt(d); f = f0 * (1 - .06 * k) * (1 + .3 * np.exp(-t / .015)) * (1 - .38 * t / d)
        ph = 2 * np.pi * np.cumsum(f) / SR; src = sum(np.sin(h * ph) / h ** .8 for h in range(1, 16)) + .5 * noise(d)
        v = peq(peq(bp(src, 350, 4200), 950, 9, 1.4), 2300, 6, 1.6)
        e = np.clip(t / .006, 0, 1) * np.exp(-t / .055) * (1 + .6 * np.exp(-t / .012))
        s = sat(v * e * 1.6, 2.2); i = N(k * .2); x[i:i + len(s)] += s[:len(x) - i]
    return reverb(x, .5, .12)[0]
def fx_boing(d=.55):  # mola: senoide com vibrato que morre
    t = tt(d); f = 190 * (1 + .45 * np.sin(2 * np.pi * 17 * t) * np.exp(-t / .2)) * (1 + .35 * t / d)
    ph = 2 * np.pi * np.cumsum(f) / SR; return (np.sin(ph) + .25 * np.sin(2 * ph)) * np.exp(-t / .2) * np.clip(t / .004, 0, 1)
def fx_squeak(f=1300):  # brinquedo de apertar: assobio que sobe e desce
    d = .13; t = tt(d); fr = f * (1 + .55 * np.sin(np.pi * t / d)); ph = 2 * np.pi * np.cumsum(fr) / SR
    return bp(np.sin(ph) + .35 * np.sign(np.sin(ph)) * .3, 700, 7000) * np.sin(np.pi * t / d) ** .6

def fx_lata(f=1.0):  # latinha de alumínio batendo: parciais inarmônicos curtos + baque oco + estalo
    d = .45; t = tt(d); x = np.zeros(len(t))
    for fr, a, dc in [(1730, 1, .07), (2890, .7, .05), (4310, .5, .035), (6020, .35, .02), (930, .45, .09)]:
        x += a * np.sin(2 * np.pi * fr * f * t * (1 + .002 * np.sin(2 * np.pi * 7 * t))) * np.exp(-t / dc)
    x += .8 * osc('sin', 210 * f * (1 + .5 * np.exp(-t / .01)), d) * np.exp(-t / .05) + .5 * bp(noise(d), 2500, 9000) * np.exp(-t / .004)
    return x * .5
def fx_fogo(d=.9):  # labareda: sopro grave que incha + estalos
    t = tt(d); x = lp(noise(d), 700) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** .7 * 1.2
    r = np.random.default_rng(5)
    for k in range(14):
        i = N(r.uniform(.05, d - .06)); L = N(.012); x[i:i + L] += bp(noise(.012), 1500, 7000)[:len(x[i:i + L])] * r.uniform(.3, .9) * np.exp(-np.arange(L) / SR / .003)
    return x

# tipo → (função, pico alvo dBFS antes da masterização, abre no estéreo?)
SFX = {
 'lata': (lambda p: fx_lata(p.get('f', 1.0)), -12, False), 'fogo': (lambda p: fx_fogo(p.get('d', .9)), -15, True),
 'whoosh_in': (lambda p: fx_whoosh(), -11, True), 'whoosh_out': (lambda p: fx_whoosh(.35, 3000, 300, .015, .09, .25), -14, True),
 'whoosh_slow': (lambda p: fx_whoosh(1.3, 200, 2200, .5, .35, .45), -14, True), 'swoosh': (lambda p: fx_swoosh(), -13, True),
 'riser': (lambda p: fx_riser(p.get('d', .8)), -12, True), 'hit_low': (lambda p: fx_impact(), -5, False), 'impact': (lambda p: fx_impact(), -5, False),
 'hit_soft': (lambda p: fx_hit_soft(), -10, False), 'braam': (lambda p: fx_braam(p.get('d', 3.6), p.get('root', 38)), -4, False),
 'tick': (lambda p: fx_tick(), -20, False), 'ui_blip': (lambda p: fx_blip(), -19, False), 'paper': (lambda p: fx_paper(), -17, False),
 'key': (lambda p: fx_key(), -17, False), 'carriage': (lambda p: fx_carriage(), -15, False), 'marker': (lambda p: fx_marker(), -15, False),
 'thread': (lambda p: fx_thread(), -17, False), 'lamp_click': (lambda p: fx_switch(), -13, False), 'focus_tick': (lambda p: fx_click(), -24, False),
 'credit_swell': (lambda p: fx_swell(), -27, True), 'cut': (lambda p: fx_cut(), -10, False), 'glitch': (lambda p: fx_glitch(p.get('d', .3)), -15, True),
 'pop': (lambda p: fx_pop(p.get('f', 600)), -14, False), 'click': (lambda p: fx_click(), -17, False), 'chime': (lambda p: fx_chime(p.get('m', 84)), -15, True),
 'coin': (lambda p: fx_coin(), -14, False), 'sparkle': (lambda p: fx_sparkle(), -17, True), 'sub_drop': (lambda p: fx_sub_drop(), -6, False),
 'boom': (lambda p: fx_boom(), -4, False), 'shutter': (lambda p: fx_shutter(), -14, False), 'heart': (lambda p: fx_heart(), -10, False),
 'bubble': (lambda p: fx_bubble(), -17, False), 'zap': (lambda p: fx_zap(), -15, False), 'type': (lambda p: fx_type(), -21, False),
 'ding': (lambda p: fx_ding(), -15, False), 'scratch': (lambda p: fx_scratch(), -16, False), 'reverse': (lambda p: fx_reverse(p.get('d', 1.0)), -10, True),
 'tape_stop': (lambda p: fx_tape_stop(), -12, False), 'snap': (lambda p: clap(.3) * .8, -12, False), 'drone_in': (lambda p: np.zeros(10), -60, False),
 'tom': (lambda p: tom(p.get('f', 110)), -9, False), 'bird': (lambda p: fx_bird(), -18, True), 'taiko': (lambda p: taiko(), -6, False),
 'bark': (lambda p: fx_bark(p.get('f', 560), p.get('n', 1)), -8, False), 'boing': (lambda p: fx_boing(), -13, False), 'squeak': (lambda p: fx_squeak(p.get('f', 1300)), -15, False),
}

# ════════════════ TRILHAS ════════════════
def chord(root, scale, deg, n=3, inv=0):
    notes = []
    for k in range(n):
        i = deg + 2 * k; notes.append(root + scale[i % 7] + 12 * (i // 7))
    return notes
def sections(C, D):
    """cues 'm:<nome>' delimitam seções da música: devolve lista (t0, t1, nome)"""
    m = sorted([(c['t'], c['type'][2:]) for c in C if c['type'].startswith('m:')])
    if not m or m[0][0] > 0: m = [(0, 'intro')] + m
    out = []
    for i, (t, n) in enumerate(m): out.append((t, m[i + 1][0] if i + 1 < len(m) else D, n))
    return out
def sec_at(S, t):
    for a, b, n in S:
        if a <= t < b: return n
    return S[-1][2]

def st_thriller(D, bpm, key, C):
    root = 26 + NOTES[key]; mus = Bus(D); S = sections(C, D); beat = 60 / bpm
    stop = next((c['t'] for c in C if c['type'] == 'm:stop'), D)
    # drone grave que respira
    d = stop + 2.5; t = tt(d); x = supersaw(root + 12, d, 4, .08) * .6 + supersaw(root + 19, d, 3, .06) * .35
    x = sweep_lp(x, 140, 520, 1.0) * np.clip(t / 3.5, 0, 1) * (1 - .25 * np.sin(2 * np.pi * t / 7.3) ** 2)
    x[N(stop):] *= np.exp(-np.arange(len(x) - N(stop)) / SR / .35); mus.add(0, reverb(x, 3.0, .35), .9)
    # batimento cardíaco que acelera
    tb, k = .6, 0
    while tb < stop - .2:
        inten = min(1, tb / stop * 1.3); mus.add(tb, lp(fx_heart(), 900), .22 + .28 * inten); k += 1; tb += beat * (1.0 - .25 * inten)
    # cluster agudo inquietante (segunda menor)
    for a, b, n in S:
        if n in ('tension', 'board'):
            dd = min(b, stop) - a
            if dd > .5: mus.add(a, reverb(pad([root + 50, root + 51], dd, 2, 1.5, 4000, kind='tri') * .35, 3.0, .5), .5)
    # motivo em pizzicato
    mot = [0, 3, 7, 8, 7, 3]; tp = 4.0; i = 0
    while tp < stop - 1:
        mus.add(tp, reverb(pizz(root + 36 + MINOR[[0, 2, 4, 5, 4, 2][i % 6]], .6), 2.0, .4), .55, (-.3 if i % 2 else .3)); tp += beat * 2; i += 1
    # cauda após o título: pad grave sustentado
    if stop < D: mus.add(stop + .1, reverb(strings([root + 12, root + 19, root + 24], D - stop - .4, 1.5, 1.6, 1500), 3.0, .45), .7)
    return mus.x

def st_launch(D, bpm, key, C, flavor='clean'):
    """eletrônico limpo de lançamento: intro → build → drop → outro. cues m:build m:drop m:break m:outro m:stop"""
    root = 45 + NOTES[key] - 12 * (NOTES[key] > 7); sc = MINOR; beat = 60 / bpm; bar = 4 * beat
    mus = Bus(D); drums = Bus(D); S = sections(C, D); prog = [0, 5, 2, 6] if flavor != 'bright' else [0, 4, 5, 3]
    if flavor == 'bright': sc = MAJOR
    stop = next((c['t'] for c in C if c['type'] == 'm:stop'), D)
    nb = int(np.ceil(stop / bar))
    for b in range(nb):
        t0 = b * bar; sec = sec_at(S, t0 + .01); ch = chord(root, sc, prog[b % 4], 4)
        full = sec in ('drop', 'main'); light = sec in ('intro', 'break', 'outro'); build = sec == 'build'
        dur_bar = min(bar, stop - t0)
        if dur_bar <= 0: break
        mus.add(t0, pad([n + 12 for n in ch], dur_bar, .4 if not full else .05, .6, 1400 if light else 3200), .22 if full else .3)
        # baixo em colcheias (sincopado)
        if not light:
            for s in range(8):
                ts = t0 + s * beat / 2
                if ts >= stop: break
                if s % 2 == 1 or full: mus.add(ts, bass(ch[0] - 12, beat / 2 * .9, 500 if build else 900), .42)
        # arpejo em semicolcheias
        arp = [ch[0] + 24, ch[1] + 24, ch[2] + 24, ch[3] + 24, ch[2] + 24, ch[1] + 24]
        for s in range(16):
            ts = t0 + s * beat / 4
            if ts >= stop: break
            if light and s % 2: continue
            mus.add(ts, pluck(arp[s % 6], .3, 2500 if light else 6000, 300, .09), .13, (-.35 if s % 2 else .35))
        # bateria
        for q in range(4):
            tq = t0 + q * beat
            if tq >= stop: break
            if full or build or (sec == 'main'):
                drums.add(tq, kick(), .9)
            if full and q % 2 == 1: drums.add(tq, clap(), .35)
            if not light or q % 2: drums.add(tq + beat / 2, hat(), .16)
            if full: drums.add(tq + beat / 4, hat(), .06); drums.add(tq + 3 * beat / 4, hat(), .07)
        if build:
            for s in range(8): drums.add(t0 + s * beat / 2, snare(), .08 + .2 * s / 8)
    # sidechain: a música respira com o bumbo
    sc_env = np.ones(mus.x.shape[1]); kicks = np.abs(drums.x[0]); k_t = [i for i in range(0, nb * 4)]
    for b in range(nb * 4):
        tq = b * beat
        if tq >= stop: break
        sec = sec_at(S, tq + .01)
        if sec in ('drop', 'main', 'build'):
            i = N(tq); L = N(beat * .9); e = 1 - .55 * np.exp(-np.arange(L) / SR / .09); j = min(i + L, len(sc_env)); sc_env[i:j] *= e[:j - i]
    mus.x *= sc_env
    out = Bus(D); out.x = mus.x + drums.x
    # final: acorde longo com reverb
    if stop < D - .3: out.add(stop, reverb(pad([n + 12 for n in chord(root, sc, 0, 4)], max(.3, D - stop - .6), .01, 1.0, 2400), 2.5, .4), .35)
    return out.x

def st_ambient(D, bpm, key, C, scale=None):
    """pads lentos + pulso filtrado + arpejo vítreo; kick suave só em 'drop'"""
    root = 40 + NOTES[key]; sc = scale or MINOR; beat = 60 / bpm; bar = 4 * beat; S = sections(C, D)
    stop = next((c['t'] for c in C if c['type'] == 'm:stop'), D); mus = Bus(D); drums = Bus(D)
    prog = [0, 5, 3, 6]; nb = int(np.ceil(stop / bar))
    for b in range(nb):
        t0 = b * bar; sec = sec_at(S, t0 + .01); dur = min(bar, stop - t0)
        if dur <= .05: break
        ch = chord(root, sc, prog[b % 4], 4)
        mus.add(t0, reverb(pad([n + 12 for n in ch], dur, 1.4, 1.8, 1600 if sec in ('intro', 'break') else 2600), 3.0, .5), .3)
        if sec != 'intro':
            for s in range(16):
                ts = t0 + s * beat / 4
                if ts >= stop: break
                n = [ch[0] + 24, ch[2] + 24, ch[1] + 36, ch[3] + 24][s % 4]
                if sec == 'break' and s % 4: continue
                mus.add(ts, reverb(pluck(n, .4, 3800, 500, .12, 'tri'), 1.6, .45), .11, (.4 if s % 2 else -.4))
            mus.add(t0, bass(ch[0] - 12, dur * .95, 260, 'tri', .8), .32)
        if sec in ('drop', 'main'):
            for q in range(4):
                tq = t0 + q * beat
                if tq >= stop: break
                if sec == 'drop' or q % 2 == 0: drums.add(tq, kick(110, 42, .28, .15), .55)
                drums.add(tq + beat / 2, hat(), .07)
                if sec == 'drop' and q % 2: drums.add(tq, clap(), .16)
    out = Bus(D); out.x = mus.x + drums.x
    if stop < D - .3: out.add(stop, reverb(pad([n + 12 for n in chord(root, sc, 0, 4)], max(.3, D - stop - .5), .05, 1.2, 2200), 3.0, .5), .35)
    return out.x

def st_explainer(D, bpm, key, C):
    """trilha de explainer corporativo leve (a da referência): piano em acordes sincopados, marimba em colcheias,
    baixo redondo, bumbo macio no 1 e 3, estalo no 2 e 4, chocalho. Maior e otimista. Seções: m:main (padrão),
    m:break (só piano e marimba), m:stop (acorde final com cauda)."""
    root = 50 + NOTES[key] - 12 * (NOTES[key] > 5); sc = MAJOR; beat = 60 / bpm; bar = 4 * beat; S = sections(C, D)
    stop = next((c['t'] for c in C if c['type'] == 'm:stop'), D); mus = Bus(D); drums = Bus(D)
    prog = [0, 4, 5, 3]; nb = int(np.ceil(stop / bar))
    for b in range(nb):
        t0 = b * bar; sec = sec_at(S, t0 + .01); ch = chord(root, sc, prog[b % 4], 3)
        cheio = sec not in ('intro', 'break')
        for off, dur, vel in [(0, 1.5, 1.0), (1.5, 1.0, .8), (2.5, 1.5, .9)]:   # piano: 1, "e" do 2, "e" do 3
            ts = t0 + off * beat
            if ts >= stop: break
            for k, n in enumerate(ch): mus.add(ts + k * .006, piano(n + 12, dur * beat + .6, vel), .32, (k - 1) * .25)
        arp = [ch[0] + 24, ch[1] + 24, ch[2] + 24, ch[1] + 24, ch[0] + 36, ch[2] + 24, ch[1] + 24, ch[2] + 24]
        for s in range(8):
            ts = t0 + s * beat / 2
            if ts >= stop: break
            mus.add(ts, marimba(arp[s], .6), .3 if s % 2 == 0 else .22, (-.35 if s % 2 else .35))
        if cheio:
            for q in range(4):
                tq = t0 + q * beat
                if tq >= stop: break
                if q in (0, 2): bd = beat * 1.4; mus.add(tq, bass(ch[0] - 12, bd, 420, 'tri', .7) * np.exp(-tt(bd) / .28), .26); drums.add(tq, kick(120, 46, .22, .12), .5)
                if q in (1, 3): drums.add(tq, clap(.25), .14)
                for s in range(4):
                    if tq + s * beat / 4 < stop: drums.add(tq + s * beat / 4, shaker(), .05 if s % 2 else .09, .3)
    out = Bus(D); out.x = mus.x + drums.x
    if stop < D - .1:
        fim = chord(root, sc, 0, 3); dd = max(.4, D - stop + .4)
        for k, n in enumerate(fim + [fim[0] + 12]): out.add(stop + k * .012, reverb(piano(n + 12, dd, .9), 2.2, .35), .3)
        out.add(stop, reverb(glock(root + 36, 1.6), 2.0, .4), .18)
    return out.x

STYLES = {'explainer': st_explainer, 'ambient': st_ambient, 'ambient_major': lambda D, b, k, C: st_ambient(D, b, k, C, MAJOR), 'thriller': st_thriller, 'launch': st_launch, 'launch_bright': lambda D, b, k, C: st_launch(D, b, k, C, 'bright')}

def rms_db(x):
    v = np.sqrt(np.mean(x ** 2)) + 1e-12; return 20 * np.log10(v)

def build(name):
    vdir = os.path.join(ROOT, 'videos', name); cj = json.load(open(os.path.join(vdir, 'cues.json')))
    D, bpm = cj['dur'], cj.get('bpm', 120); music = cj.get('music') or {}; C = cj.get('cues', [])
    if not music:
        page = open(os.path.join(vdir, 'index.html')).read(); m = re.search(r"music:\s*(\{[^}]*\})", page)
        if m: music = json.loads(re.sub(r"(\w+):", r'"\1":', m.group(1)).replace("'", '"'))
    mix = Bus(D)
    style = music.get('style')
    if style in STYLES:
        mx = STYLES[style](D, bpm, music.get('key', 'A'), C); act = mx[:, :N(D)]
        g = db(-19 - rms_db(act[np.abs(act) > 1e-4] if np.any(np.abs(act) > 1e-4) else act)) * db(music.get('gain', 0))
        mix.x[:, :mx.shape[1]] += mx[:, :mix.x.shape[1]] * g
    # narração (se houver): cadeia de voz + ducking da trilha
    nj = os.path.join(vdir, 'narration.json')
    if os.path.exists(nj):
        segs = json.load(open(nj))['segments']; voice = np.zeros(mix.x.shape[1]); duck = np.ones(mix.x.shape[1])
        for sg in segs:
            sr0, v = wavfile.read(os.path.join(ROOT, sg['file'])); v = v.astype(np.float64) / 32768
            if v.ndim > 1: v = v.mean(axis=1)
            if sr0 != SR: v = signal.resample_poly(v, SR, sr0)
            v = peq(hp(v, 85), 3200, 2.5, .8); v = sat(v * 1.4, 1.2); v = v / (np.sqrt(np.mean(v[np.abs(v) > 1e-3] ** 2)) + 1e-9) * db(-18)
            i = N(sg['start']); j = min(i + len(v), len(voice)); voice[i:j] += v[:j - i]
            a0, a1 = N(max(0, sg['start'] - .15)), N(sg['start'] + sg['dur'] + .25); duck[a0:a1] = db(-11)
        k = np.ones(N(.12)) / N(.12); duck = np.convolve(duck, k, mode='same')
        mix.x *= duck; mix.x += np.stack([voice, voice])
    side = 1
    for c in C:
        k = c['type']
        if k.startswith('m:') or k not in SFX: continue
        fn, tgt, wide = SFX[k]; s = fade(fn(c)); s = s / peak(s) * db(tgt + c.get('gain', 0))
        pan = c.get('pan', (.25 * side if wide else 0)); side = -side
        mix.add(c['t'] + c.get('off', 0), s, 1.0, pan)
    x = mix.x[:, :N(D)]
    p = peak(x)
    if p > .95: x *= .95 / p; print(f'  guard: {20 * np.log10(.95 / p):.1f} dB')
    x[:, -N(.05):] *= np.linspace(1, 0, N(.05))
    raw = os.path.join(ROOT, 'audio', name + '.raw.wav'); wavfile.write(raw, SR, (x.T * 32767).astype(np.int16))
    # masterização: loudnorm em dois passes (−14 LUFS, −1,5 dBTP)
    m = subprocess.run(['ffmpeg', '-hide_banner', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    j = json.loads(m[m.rindex('{'):m.rindex('}') + 1])
    af = f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', af, '-ar', str(SR), '-c:a', 'pcm_s16le', os.path.join(ROOT, 'audio', name + '.wav')], check=True)
    os.remove(raw)
    print(f'{name}: {len(C)} cues, estilo={style}, entrada {j["input_i"]} LUFS → −14')

if __name__ == '__main__':
    pre = sys.argv[1:]; names = sorted(d for d in os.listdir(os.path.join(ROOT, 'videos')) if os.path.exists(os.path.join(ROOT, 'videos', d, 'cues.json')))
    for n in names:
        if not pre or any(n.startswith(p) for p in pre): build(n)
