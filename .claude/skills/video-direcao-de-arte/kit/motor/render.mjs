#!/usr/bin/env node
// render.mjs — renderizador genérico HTML → imagem/vídeo submetido à direção de arte (DA) do projeto.
//
//   node render.mjs --cena <modulo.js> --saida <arquivo> [--formato horizontal|vertical|quadrado|thumbnail|LxA]
//                   [--dur S] [--fps N/D] [--params '<json>'|@arquivo.json] [--alfa] [--quadro T]
//                   [--codec h264|prores4444|vp9alfa] [--escala 0.5] [--sem-auditoria] [--da <da.json>] [--fila fila.json]
//                   [--de <pasta>] [--sem-trava] [--json] [--validar] [--inatividade SEG]
//
// Camadas garantidas aqui: C1 (acha a DA ou código 2; recompila se o lock estiver velho), C3 (auditor de estilos
// computados antes de gastar o render; --sem-auditoria pula e fica registrado), C4 (carimbo <saida>.da.json com a
// identidade da DA lida NO INÍCIO: se o da.json mudar durante o render, o job falha em vez de carimbar a DA nova).
// A auditoria tem quatro partes, nesta ordem: estilos computados (auditor.js), imagens animadas no disco (GIF, APNG,
// WebP, SVG com animação), pureza (seek(t) não depende do seek anterior) e quietude (com o MESMO seek(t), dois retratos
// separados por 120 ms são idênticos — pega SMIL, vídeo, laço por mensagem/promessa/observer, cursor piscando).
// Vídeo: quadros PNG por pipe para o ffmpeg (-threads 2), cache por key(t), <saida>.parcial renomeado só com rc 0,
// conferência por ffprobe. O render inteiro roda sob a trava global (trava.py), reexecutando-se se preciso.
// Nada aqui espera para sempre: escrita no ffmpeg desiste assim que ele sai; SIGINT/SIGTERM/SIGHUP, a morte do dono
// da trava e --inatividade (padrão 120 s sem progresso) abortam matando ffmpeg e Chromium e apagando o .parcial.
// Códigos de saída: 0 ok · 1 falha (auditoria, render, ffprobe, fila com falha) · 2 nenhuma DA · 64 uso incorreto ·
// 124 abortado por inatividade · 129/130/143 interrompido por sinal.
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import { spawn } from 'node:child_process';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import {
  MOTOR, KIT_FINAL, KIT_VERSAO, PALCO_HTML, CENAS_DIR, ARGS_CHROME, MotorErro, url, acharChromium, acharFfmpeg,
  sobTrava, donoDaTrava, reexecutarSobTrava, carregarDA, carimbar, ffprobe, dimensoesPng, num, fpsRacional, mkdirp, tamanhoMB,
} from './comum.mjs';

const AJUDA = `uso: node render.mjs --cena <modulo.js> --saida <arquivo> [opções]
       node render.mjs --fila <fila.json> [--da …] [--sem-auditoria]

Renderiza uma cena HTML (módulo ES) em PNG ou vídeo, submetida à DA do projeto.

opções
  --cena ARQ          módulo da cena (nome de uma cena embutida — titulo, gc, moldura, citacao, barras — ou caminho .js)
  --saida ARQ         arquivo gerado (.mp4 para h264, .mov para prores4444, .webm para vp9alfa, .png com --quadro)
  --formato NOME      horizontal | vertical | quadrado | thumbnail | LxA (ex.: 960x540); padrão: horizontal
  --dur S             duração em segundos (padrão: meta.dur_padrao da cena)
  --fps N/D           taxa de quadros (padrão: a do formato na DA)
  --params JSON       parâmetros da cena em JSON, ou @arquivo.json
  --alfa              fundo transparente (padrão: o que a cena pedir em meta.alfa_padrao)
  --quadro T          gera um PNG único do instante T (prova, thumbnail); T pode ser "fim"
  --codec NOME        h264 (opaco) | prores4444 (alfa, Premiere) | vp9alfa (alfa, compor via ffmpeg)
  --escala F          prévia em resolução reduzida (deviceScaleFactor), mesmo layout; ex.: 0.5
  --sem-auditoria     pula o auditor C3 (fica registrado no carimbo: conferir-carimbo reprova)
  --da ARQ            da.json (ou pasta do projeto); vence DA_JSON e a descoberta
  --de PASTA          pasta de onde começar a procurar da/da.json (padrão: diretório atual)
  --fila ARQ          JSON com uma lista de jobs ({cena, saida, formato, dur, fps, params, alfa, quadro, codec, escala})
  --json              resumo final em JSON no stdout
  --validar           confere argumentos, DA, cenas e params de todos os jobs e sai sem renderizar (não entra na trava)
  --inatividade SEG   aborta (código 124) se o render ficar SEG segundos sem progresso (padrão: 120; 0 desliga)
  --sem-trava         não entra na fila da trava global (só para quem já a segura por fora)
  -h, --help          esta ajuda

Erros de uso (opção desconhecida, param inválido, cena inexistente) saem com 64 ANTES de entrar na fila da trava.
Códigos de saída: 0 ok · 1 falha · 2 nenhuma DA · 64 uso incorreto · 124 sem progresso · 129/130/143 interrompido.
Kit ${KIT_VERSAO} · ${KIT_FINAL}/motor`;

// ──────────────────────────────────────────────────────────────── argumentos ──
const BOOLEANAS = new Set(['alfa', 'sem-auditoria', 'json', 'sem-trava', 'help', 'silencioso', 'validar']);
const COM_VALOR = new Set(['cena', 'saida', 'formato', 'dur', 'fps', 'params', 'quadro', 'codec', 'escala', 'da', 'de', 'fila', 'inatividade']);
const CHAVES_DE_JOB = new Set(['cena', 'saida', 'formato', 'dur', 'fps', 'params', 'alfa', 'quadro', 'codec', 'escala', 'sem_auditoria', 'sem-auditoria']);

function parseArgs(argv) {
  const a = { _: [] };
  const conhecidas = [...BOOLEANAS, ...COM_VALOR];
  for (let i = 0; i < argv.length; i++) {
    const x = argv[i];
    if (x === '-h' || x === '--help') { a.help = true; continue; }
    if (!x.startsWith('--')) { a._.push(x); continue; }
    const [k, vInline] = x.slice(2).split(/=(.*)/s);
    if (BOOLEANAS.has(k)) { a[k] = vInline == null ? true : !/^(0|false|não|nao|no)$/i.test(vInline); continue; }
    if (!COM_VALOR.has(k)) {
      throw new MotorErro(`opção desconhecida --${k}.${sugerir(k, conhecidas).replace(/"([^"]+)"/g, '--$1')}`,
        { dica: 'Veja as opções com --help. Parâmetros da cena vão dentro de --params \'{…}\'.', codigo: 64 });
    }
    const v = vInline != null ? vInline : argv[++i];
    if (v == null || (vInline == null && /^--[a-z]/.test(v) && conhecidas.includes(v.slice(2).split('=')[0]))) {
      throw new MotorErro(`argumento --${k}: faltou o valor`, { codigo: 64 });
    }
    a[k] = v;
  }
  return a;
}

function lerParams(bruto) {
  if (bruto == null || bruto === '') return {};
  if (typeof bruto === 'object') return bruto;
  let texto = String(bruto), origem = 'linha de comando';
  if (texto.startsWith('@')) {
    origem = texto.slice(1);
    try { texto = fs.readFileSync(origem, 'utf8'); } catch (e) { throw new MotorErro(`--params: não consegui ler ${origem} (${e.message})`, { codigo: 64 }); }
  }
  try { return JSON.parse(texto); } catch (e) {
    throw new MotorErro(`--params não é JSON válido (${origem}): ${e.message}`, { dica: 'ex.: --params \'{"titulo": "Capítulo 1"}\' ou --params @params.json', codigo: 64 });
  }
}

function sugerir(nome, opcoes) {
  const n = String(nome).toLowerCase();
  const perto = opcoes.filter((o) => (n.length >= 3 && (o.toLowerCase().includes(n) || n.includes(o.toLowerCase()))) || distancia(n, o.toLowerCase()) <= 2)
    .sort((x, y) => distancia(n, x.toLowerCase()) - distancia(n, y.toLowerCase())).slice(0, 3);
  return perto.length ? ` Quis dizer ${perto.map((p) => JSON.stringify(p)).join(' ou ')}?` : '';
}

function distancia(a, b) {
  const m = a.length, n = b.length;
  const d = Array.from({ length: m + 1 }, (_, i) => [i, ...Array(n).fill(0)]);
  for (let j = 1; j <= n; j++) d[0][j] = j;
  for (let i = 1; i <= m; i++) for (let j = 1; j <= n; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[m][n];
}

// ─────────────────────────────────────────────────────────── cena e params ──
function resolverCena(nome, base = process.cwd()) {
  if (!nome) throw new MotorErro('faltou --cena', { dica: `Cenas embutidas: ${listarCenas().join(', ')}; ou o caminho de um módulo .js`, codigo: 64 });
  const candidatos = [];
  if (/[/\\]|\.m?js$/.test(nome)) candidatos.push(path.resolve(base, nome), path.resolve(nome));   // fila: relativo à pasta do fila.json, depois ao cwd
  candidatos.push(path.join(CENAS_DIR, nome + '.js'), path.join(CENAS_DIR, nome));
  for (const c of candidatos) if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
  throw new MotorErro(`cena ${JSON.stringify(nome)} não encontrada.`, { dica: `Cenas embutidas: ${listarCenas().join(', ')}.${sugerir(nome, listarCenas())}`, codigo: 64 });
}

function listarCenas() {
  try { return fs.readdirSync(CENAS_DIR).filter((f) => f.endsWith('.js') && !f.startsWith('_')).map((f) => f.replace(/\.js$/, '')); } catch { return []; }
}

async function importarMeta(cenaArq) {
  let mod;
  try { mod = await import(pathToFileURL(cenaArq).href); } catch (e) {
    throw new MotorErro(`não consegui importar a cena ${cenaArq}: ${e.message}`,
      { dica: 'A cena é um módulo ES puro: nada de document/window no nível do módulo — todo DOM fica dentro de build().' });
  }
  if (typeof mod.build !== 'function' || typeof mod.seek !== 'function') throw new MotorErro(`${cenaArq} precisa exportar build(palco, params, ctx) e seek(t)`);
  return { meta: mod.meta || {}, mod };
}

const TIPOS = new Set(['texto', 'numero', 'inteiro', 'booleano', 'lista', 'objeto', 'arquivo', 'cor', 'papel', 'opcao', 'plataforma']);
// nomes canônicos de plataforma e apelidos → chave de formatos.margens_seguras (a mesma tabela de runtime.js e de da.py)
const ZONA_DA_PLATAFORMA = { reels: 'instagram', instagram_reels: 'instagram', reel: 'instagram', ig: 'instagram', insta: 'instagram',
  youtube_shorts: 'shorts', short: 'shorts', tt: 'tiktok', 'tik-tok': 'tiktok', youtube: 'padrao', youtube_longo: 'padrao', yt: 'padrao' };

/**
 * Confere um valor contra a definição do parâmetro (recursivo: `itens` de lista e `campos` de objeto).
 * Devolve o valor normalizado; erro de uso = MotorErro com código 64, antes de abrir o browser.
 */
function conferirValor(nome, v, def, DA, baseArquivos, fmt, avisos) {
  const tipo = def.tipo || 'texto';
  if (!TIPOS.has(tipo)) throw new MotorErro(`meta.params.${nome}.tipo ${JSON.stringify(tipo)} não é um tipo conhecido (${[...TIPOS].join(', ')})`);
  const k = JSON.stringify(nome);
  const erroTipo = (esperado) => new MotorErro(`parâmetro ${k}: esperado ${esperado}, veio ${JSON.stringify(v)}`, { dica: def.descricao ? `${nome}: ${def.descricao}` : null, codigo: 64 });
  if (v === null || v === undefined) return null;
  switch (tipo) {
    case 'texto': if (typeof v !== 'string') { if (typeof v === 'number') v = String(v); else throw erroTipo('texto'); } break;
    case 'numero': if (typeof v !== 'number' || !Number.isFinite(v)) throw erroTipo('número'); break;
    case 'inteiro': if (!Number.isInteger(v)) throw erroTipo('número inteiro'); break;
    case 'booleano': if (typeof v !== 'boolean') throw erroTipo('true/false'); break;
    case 'lista': {
      if (!Array.isArray(v)) throw erroTipo('lista […]');
      if (def.min != null && v.length < def.min) throw new MotorErro(`parâmetro ${k}: a lista tem ${v.length} item(ns), o mínimo é ${def.min}`, { dica: def.descricao ? `${nome}: ${def.descricao}` : null, codigo: 64 });
      if (def.max != null && v.length > def.max) throw new MotorErro(`parâmetro ${k}: a lista tem ${v.length} item(ns), o máximo é ${def.max}`, { dica: def.descricao ? `${nome}: ${def.descricao}` : null, codigo: 64 });
      if (def.itens) v = v.map((x, i) => {
        if (x === null || x === undefined) throw new MotorErro(`parâmetro ${JSON.stringify(`${nome}[${i}]`)}: item vazio (null) na lista`, { dica: def.descricao ? `${nome}: ${def.descricao}` : null, codigo: 64 });
        return conferirValor(`${nome}[${i}]`, x, def.itens, DA, baseArquivos, fmt, avisos);
      });
      return v;
    }
    case 'objeto': {
      if (typeof v !== 'object' || Array.isArray(v)) throw erroTipo('objeto {…}');
      if (def.campos) {
        const campos = Object.keys(def.campos);
        const saida = {};
        for (const c of Object.keys(v)) {
          if (!(c in def.campos)) throw new MotorErro(`parâmetro ${k}: campo ${JSON.stringify(c)} não existe.`, { dica: `Campos aceitos: ${campos.join(', ')}.${sugerir(c, campos)}`, codigo: 64 });
        }
        for (const [c, dc] of Object.entries(def.campos)) {
          let x = v[c];
          if (x === undefined || x === null) {
            if (dc.obrigatorio && dc.padrao === undefined) throw new MotorErro(`parâmetro ${k}: faltou o campo obrigatório ${JSON.stringify(c)}${dc.descricao ? ` (${dc.descricao})` : ''}.`, { dica: `Campos: ${campos.join(', ')}.`, codigo: 64 });
            x = dc.padrao === undefined ? null : JSON.parse(JSON.stringify(dc.padrao));
          }
          saida[c] = conferirValor(`${nome}.${c}`, x, dc, DA, baseArquivos, fmt, avisos);
        }
        return saida;
      }
      return v;
    }
    case 'opcao':
      if (!(def.opcoes || []).includes(v)) throw new MotorErro(`parâmetro ${k}: ${JSON.stringify(v)} não é uma opção (${(def.opcoes || []).join(', ')})`, { codigo: 64 });
      break;
    case 'papel':
      if (!(v in DA.tipografia.papeis)) throw new MotorErro(`parâmetro ${k}: papel ${JSON.stringify(v)} não existe na DA (${Object.keys(DA.tipografia.papeis).join(', ')})`, { codigo: 64 });
      break;
    case 'cor': {
      if (typeof v !== 'string') throw erroTipo('token de cor');
      const ok = v in DA.cor.paleta || /^(dado|neutro)-\d+$/.test(v) || DA.cor.permitidas.includes(v.toUpperCase());
      if (!ok) throw new MotorErro(`parâmetro ${k}: cor ${JSON.stringify(v)} não é um token da DA (${Object.keys(DA.cor.paleta).join(', ')}, dado-N, neutro-N)`, { codigo: 64 });
      break;
    }
    case 'plataforma': {
      // zona segura: nome conferido ANTES do browser; zona que só existe em outro formato cai no padrão deste, com aviso
      if (typeof v !== 'string') throw erroTipo('nome de plataforma');
      const tabela = DA.formatos.margens_seguras;
      const baixo = v.toLowerCase();
      const chave = ZONA_DA_PLATAFORMA[baixo] || baixo;
      const todas = new Set();
      for (const b of Object.values(tabela)) if (b && typeof b === 'object') for (const n of Object.keys(b)) todas.add(n);
      const aceitos = [...new Set([...todas, 'reels', 'youtube'])];
      if (!todas.has(v) && !todas.has(chave) && !(baixo in ZONA_DA_PLATAFORMA)) {
        throw new MotorErro(`parâmetro ${k}: plataforma ${JSON.stringify(v)} não existe.`, { dica: `Zonas seguras da DA: ${aceitos.join(', ')}.${sugerir(v, aceitos)}`, codigo: 64 });
      }
      if (fmt) {
        const ori = fmt.L > fmt.A ? 'horizontal' : fmt.L < fmt.A ? 'vertical' : 'quadrado';
        const bloco = tabela[fmt.nome] || tabela[ori] || tabela.horizontal;
        if (!(v in bloco) && !(chave in bloco)) {
          const padrao = 'uniao' in bloco ? 'uniao' : 'padrao' in bloco ? 'padrao' : Object.keys(bloco)[0];
          if (avisos) avisos.push(`parâmetro ${nome}: a zona ${JSON.stringify(v)} não existe no formato ${fmt.nome} (${Object.keys(bloco).join(', ')}); a cena usa ${JSON.stringify(padrao)}`);
        }
      }
      break;
    }
    case 'arquivo': {
      if (typeof v !== 'string') throw erroTipo('caminho de arquivo');
      const abs = path.resolve(baseArquivos, v);
      if (!fs.existsSync(abs)) throw new MotorErro(`parâmetro ${k}: arquivo não encontrado: ${abs}`, { codigo: 64 });
      v = pathToFileURL(abs).href;
      break;
    }
  }
  if (def.min != null && typeof v === 'number' && v < def.min) throw new MotorErro(`parâmetro ${k}: ${v} está abaixo do mínimo (${def.min})`, { codigo: 64 });
  if (def.max != null && typeof v === 'number' && v > def.max) throw new MotorErro(`parâmetro ${k}: ${v} está acima do máximo (${def.max})`, { codigo: 64 });
  return v;
}

function validarParams(meta, params, DA, baseArquivos, fmt = null, avisos = null) {
  const esquema = meta.params || {};
  const nomes = Object.keys(esquema);
  const saida = {};
  for (const k of Object.keys(params)) {
    if (!(k in esquema)) throw new MotorErro(`parâmetro ${JSON.stringify(k)} não existe na cena ${meta.nome || ''}.`, { dica: `Parâmetros aceitos: ${nomes.join(', ') || '(nenhum)'}.${sugerir(k, nomes)}`, codigo: 64 });
  }
  for (const [k, def] of Object.entries(esquema)) {
    let v = params[k];
    if (v === undefined) {
      if (def.obrigatorio && def.padrao === undefined) throw new MotorErro(`parâmetro obrigatório ${JSON.stringify(k)} não informado (${def.descricao || def.tipo}).`, { codigo: 64 });
      v = def.padrao === undefined ? null : JSON.parse(JSON.stringify(def.padrao));
    }
    saida[k] = conferirValor(k, v, def, DA, baseArquivos, fmt, avisos);
  }
  return saida;
}

// ───────────────────────────────────────────────────────────────── formato ──
function resolverFormato(DA, nome, fpsPedido) {
  nome = nome || 'horizontal';
  let L, A, fps = null, nomeFmt = nome, auto = false;
  const m = /^(\d+)\s*[x×]\s*(\d+|auto)$/i.exec(nome);
  if (m) {
    L = parseInt(m[1], 10);
    auto = /auto/i.test(m[2]);
    A = auto ? Math.round(L * 9 / 16 / 2) * 2 : parseInt(m[2], 10);     // auto: a altura vem do conteúdo (só com --quadro)
    nomeFmt = auto ? `${L}xauto` : `${L}x${A}`;
    const ori = L > A ? 'horizontal' : L < A ? 'vertical' : 'quadrado';
    const ref = DA.formatos[ori];
    if (ref && ref.fps_num) fps = { num: ref.fps_num, den: ref.fps_den };
  } else {
    const f = DA.formatos[nome];
    if (!f || !f.largura) {
      const validos = Object.entries(DA.formatos).filter(([, v]) => v && v.largura).map(([k]) => k);
      throw new MotorErro(`formato ${JSON.stringify(nome)} não existe na DA (${validos.join(', ')}) nem é LxA.`, { codigo: 64 });
    }
    L = f.largura; A = f.altura;
    if (f.fps_num) fps = { num: f.fps_num, den: f.fps_den };
  }
  if (fpsPedido) {
    try { fps = fpsRacional(fpsPedido); } catch (e) { throw new MotorErro(`--fps: ${e.message}`, { codigo: 64 }); }
  }
  if (L % 2 || A % 2) throw new MotorErro(`formato ${nomeFmt}: largura e altura precisam ser pares (yuv420p)`, { codigo: 64 });
  return { nome: nomeFmt, L, A, fps, auto, fpsTexto: fps ? `${fps.num}/${fps.den}` : null, fpsFloat: fps ? fps.num / fps.den : null };
}

const CODECS = {
  h264: { ext: ['.mp4', '.mov', '.m4v'], alfa: false, pix: 'yuv420p', rotulo: 'H.264 yuv420p bt709' },
  prores4444: { ext: ['.mov'], alfa: true, pix: 'yuva444p10le', rotulo: 'ProRes 4444 com alfa' },
  vp9alfa: { ext: ['.webm'], alfa: true, pix: 'yuva420p', rotulo: 'VP9 com alfa (WebM)' },
};

function argsCodec(codec, fmt, fps, saida, dimsSaida) {
  const base = ['-y', '-v', 'error', '-nostdin', '-threads', '2', '-f', 'image2pipe', '-framerate', `${fps.num}/${fps.den}`, '-vcodec', 'png', '-i', '-'];
  const vf = [];
  const [w, h] = dimsSaida;
  if (w % 2 || h % 2) vf.push(`crop=${w - (w % 2)}:${h - (h % 2)}:0:0`);
  const r = [`${fps.num}/${fps.den}`];
  if (codec === 'h264') {
    // ffmpeg 8 + libx264 ignoram -color_primaries/-color_trc: a marcação bt709 vai pelo scale e pelos x264-params
    vf.push('scale=in_range=full:out_range=tv:out_color_matrix=bt709:out_primaries=bt709:out_transfer=bt709', 'format=yuv420p');
    return [...base, '-vf', vf.join(','), '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-threads', '2',
      '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709:range=tv', '-color_range', 'tv',
      '-r', ...r, '-video_track_timescale', String(fps.num), '-movflags', '+faststart', '-f', 'mp4', saida];
  }
  if (codec === 'prores4444') {
    vf.push('format=rgba');
    return [...base, '-vf', vf.join(','), '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', '-qscale:v', '11',
      '-threads', '2', '-r', ...r, '-video_track_timescale', String(fps.num), '-f', 'mov', saida];
  }
  if (codec === 'vp9alfa') {
    vf.push('format=rgba');
    return [...base, '-vf', vf.join(','), '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-auto-alt-ref', '0', '-crf', '24', '-b:v', '0',
      '-deadline', 'good', '-cpu-used', '2', '-row-mt', '1', '-threads', '2', '-r', ...r, '-f', 'webm', saida];
  }
  throw new MotorErro(`codec ${JSON.stringify(codec)} desconhecido (h264, prores4444, vp9alfa)`, { codigo: 64 });
}

// ─────────────────────────────────────────────────────────────────── job ──
function prepararJob(bruto, DA, baseArquivos, padroes) {
  const cenaArq = resolverCena(bruto.cena, baseArquivos);
  return { ...padroes, ...bruto, cenaArq, baseArquivos, params: lerParams(bruto.params), bruto: bruto._chaves || null };
}

async function planejarJob(job, DA) {
  const avisos = [];
  for (const k of Object.keys(job.bruto || {})) {
    if (!CHAVES_DE_JOB.has(k) && !k.startsWith('_')) throw new MotorErro(`fila: chave ${JSON.stringify(k)} não existe num job.${sugerir(k, [...CHAVES_DE_JOB])}`,
      { dica: `Chaves aceitas: ${[...CHAVES_DE_JOB].filter((c) => c !== 'sem-auditoria').join(', ')}.`, codigo: 64 });
  }
  const { meta, mod } = await importarMeta(job.cenaArq);
  const fmt = resolverFormato(DA, job.formato, job.fps);
  if (meta.formatos && meta.formatos.length && !/^\d+x\d+$/.test(fmt.nome) && !meta.formatos.includes(fmt.nome)) {
    throw new MotorErro(`a cena ${meta.nome || job.cena} não declara o formato ${fmt.nome} (declara: ${meta.formatos.join(', ')})`, { codigo: 64 });
  }
  const params = validarParams(meta, job.params, DA, job.baseArquivos, fmt, avisos);
  const alfa = job.alfa != null ? !!job.alfa : !!meta.alfa_padrao;
  let dur = job.dur != null ? Number(job.dur) : (meta.dur_padrao ?? 4);
  if (!(dur > 0) || !Number.isFinite(dur)) throw new MotorErro(`duração inválida: ${job.dur} (segundos, maior que zero)`, { codigo: 64 });
  if (typeof mod.duracao === 'function') {
    // contrato opcional: a cena calcula a própria duração a partir da DA (ex.: teste_movimento); --dur chega em `pedida`
    let propria;
    try { propria = Number(mod.duracao({ DA, params, formato: fmt, pedida: job.dur != null ? dur : null })); } catch (e) {
      throw new MotorErro(`a cena ${meta.nome || job.cena} falhou ao calcular a duração: ${e && e.message ? e.message : e}`);
    }
    if (!(propria > 0) || !Number.isFinite(propria)) throw new MotorErro(`a cena ${meta.nome || job.cena} devolveu uma duração inválida em duracao(): ${propria}`);
    if (job.dur != null && Math.abs(propria - dur) > 0.0005) avisos.push(`--dur ${num(dur, 3)}: a cena ${meta.nome || ''} calcula a duração pelas durações da DA e não corta animação; usei ${num(propria, 3)} s`);
    dur = propria;
  }
  const escala = job.escala != null ? Number(job.escala) : 1;
  if (!(escala > 0 && escala <= 2)) throw new MotorErro(`--escala ${job.escala} inválida (use entre 0,1 e 2)`, { codigo: 64 });
  let quadro = null;
  if (fmt.auto && job.quadro == null) throw new MotorErro(`o formato ${fmt.nome} (altura automática) só serve para PNG: use --quadro`, { codigo: 64 });
  if (job.quadro != null) {
    quadro = String(job.quadro) === 'fim' ? dur : Number(job.quadro);
    if (!Number.isFinite(quadro)) throw new MotorErro(`--quadro ${job.quadro} inválido (segundos ou "fim")`, { codigo: 64 });
    const pedido = quadro;
    quadro = Math.max(0, Math.min(dur, quadro));
    if (quadro !== pedido) avisos.push(`--quadro ${num(pedido, 3)} está fora da peça (0 a ${num(dur, 3)} s): usei ${num(quadro, 3)}`);
  }
  if (!job.saida) throw new MotorErro('faltou --saida', { codigo: 64 });
  const saida = path.resolve(job.saida);
  const ext = path.extname(saida).toLowerCase();
  let codec = job.codec || null;
  if (quadro == null) {
    if (!fmt.fps) throw new MotorErro(`o formato ${fmt.nome} não tem fps na DA; use --fps ou --quadro para um PNG`, { codigo: 64 });
    if (!codec) codec = alfa ? (ext === '.webm' ? 'vp9alfa' : 'prores4444') : 'h264';
    const c = CODECS[codec];
    if (!c) throw new MotorErro(`codec ${JSON.stringify(codec)} desconhecido (h264, prores4444, vp9alfa)`, { codigo: 64 });
    if (alfa && !c.alfa) throw new MotorErro('peça com alfa não cabe em h264; use --codec prores4444 (Premiere) ou vp9alfa (compor via ffmpeg)', { codigo: 64 });
    if (!c.ext.includes(ext)) throw new MotorErro(`${codec} precisa de saída ${c.ext.join(' ou ')} (veio ${ext || 'sem extensão'})`, { codigo: 64 });
  } else if (ext !== '.png') {
    throw new MotorErro('--quadro gera um PNG: use --saida algo.png', { codigo: 64 });
  }
  const dims = [Math.round(fmt.L * escala), Math.round(fmt.A * escala)];
  return { ...job, meta, mod, fmt, params, alfa, dur, escala, quadro, saida, codec, dims, avisos, semAuditoria: !!job['sem-auditoria'] };
}

/**
 * Instantes que o auditor visita: uma grade temporal (passo ≤ 0,25 s em peça curta, 24 fatias em peça longa),
 * as âncoras da timeline da cena (o instante, logo depois e com a entrada adiantada) e as fronteiras que a cena
 * devolveu no layout (fim_entrada, inicio_saida). Teto de amostras: as âncoras ficam, a grade é rareada.
 */
function amostrasDaAuditoria(dur, ancoras = [], layout = null, teto = 64) {
  const fixas = new Set(), grade = new Set();
  const norm = (t) => +Math.max(0, Math.min(dur, t)).toFixed(4);
  fixas.add(0); fixas.add(norm(dur));
  for (const a of ancoras || []) {
    if (!a || !Number.isFinite(a.t)) continue;
    for (const d of [0, 0.05, 0.25]) fixas.add(norm(a.t + d));
  }
  const bordas = [];
  const colher = (o, nivel) => {
    if (!o || typeof o !== 'object' || nivel > 2) return;
    for (const [k, v] of Object.entries(o)) {
      if (typeof v === 'number' && /^(fim_entrada|inicio_saida|corte)$/.test(k)) bordas.push(v);
      else if (v && typeof v === 'object') colher(v, nivel + 1);
    }
  };
  colher(layout, 0);
  for (const b of bordas) for (const d of [-0.05, 0.05, 0.15]) fixas.add(norm(b + d));
  const passo = Math.max(dur / 24, Math.min(0.25, dur / 8));
  for (let t = 0; t <= dur + 1e-9; t += passo) grade.add(norm(t));
  let lista = [...fixas];
  if (lista.length > teto) lista = lista.sort((x, y) => x - y).filter((_, i, v) => i === 0 || i === v.length - 1 || i % Math.ceil(v.length / teto) === 0);
  const resto = [...grade].filter((t) => !fixas.has(t)).sort((x, y) => x - y);
  const vagas = Math.max(0, teto - lista.length);
  const salto = resto.length > vagas ? resto.length / Math.max(1, vagas) : 1;
  for (let i = 0; i < resto.length && vagas; i += salto) lista.push(resto[Math.floor(i)]);
  return [...new Set(lista)].sort((x, y) => x - y);
}

/** Instantes da checagem de pureza: meio da entrada, repouso, dentro da janela de saída e o fim. */
function instantesDePureza(dur, layout) {
  const fe = layout && Number.isFinite(layout.fim_entrada) ? layout.fim_entrada : dur * 0.3;
  const is = layout && Number.isFinite(layout.inicio_saida) ? layout.inicio_saida : dur * 0.8;
  const v = [fe * 0.5, (fe + is) / 2, is + (dur - is) * 0.4, dur * 0.97];
  return [...new Set(v.map((t) => +Math.max(0, Math.min(dur, t)).toFixed(4)))];
}

// ───────────────────────────────────────────────────── imagens animadas ──
/**
 * A imagem (bytes do arquivo ou de uma data: URL) anima sozinha? Devolve o motivo ('GIF com 12 quadros', 'APNG',
 * 'WebP animado', 'SVG com <animate>') ou null. Imagem animada roda no relógio do navegador: o quadro deixa de ser função de t.
 */
function animacaoDaImagem(buf) {
  if (!buf || buf.length < 12) return null;
  const ascii = (i, n) => buf.toString('latin1', i, i + n);
  if (ascii(0, 4) === 'GIF8') {
    // conta os descritores de imagem (0x2C) andando pelos blocos; dois ou mais = animação
    let i = 13, quadros = 0;
    const flags = buf[10];
    if (flags & 0x80) i += 3 * (1 << ((flags & 7) + 1));
    while (i < buf.length) {
      const b = buf[i];
      if (b === 0x3B) break;
      if (b === 0x21) { i += 2; while (i < buf.length && buf[i]) i += buf[i] + 1; i++; continue; }
      if (b === 0x2C) {
        quadros++;
        if (quadros > 1) return 'GIF animado';
        const f = buf[i + 9]; i += 10;
        if (f & 0x80) i += 3 * (1 << ((f & 7) + 1));
        i++;                                                   // tamanho mínimo do código LZW
        while (i < buf.length && buf[i]) i += buf[i] + 1;
        i++;
        continue;
      }
      break;                                                   // bloco desconhecido: arquivo truncado
    }
    return null;
  }
  if (buf[0] === 0x89 && ascii(1, 3) === 'PNG') {
    for (let i = 8; i + 8 <= buf.length;) {
      const tam = buf.readUInt32BE(i), tipo = ascii(i + 4, 4);
      if (tipo === 'acTL') return 'PNG animado (APNG)';
      if (tipo === 'IDAT' || tipo === 'IEND') return null;
      i += 12 + tam;
    }
    return null;
  }
  if (ascii(0, 4) === 'RIFF' && ascii(8, 4) === 'WEBP') return ascii(12, 4) === 'VP8X' && (buf[20] & 0x02) ? 'WebP animado' : null;
  if (ascii(4, 4) === 'ftyp') return /avis|msf1/.test(ascii(8, 24)) ? 'AVIF animado (sequência)' : null;
  const inicio = buf.toString('utf8', 0, Math.min(buf.length, 4096));
  if (/<svg[\s>]/i.test(inicio)) {
    const tudo = buf.toString('utf8', 0, Math.min(buf.length, 4 * 1024 * 1024));
    const m = /<(animate|animateTransform|animateMotion|set)[\s>/]|@keyframes|animation(?:-name)?\s*:/.exec(tudo);
    return m ? `SVG com animação (${m[1] ? '<' + m[1] + '>' : 'CSS'})` : null;
  }
  return null;
}

/** Lê os bytes de uma URL de imagem da página (file:// ou data:); http(s) e blob: ficam de fora (null). */
function bytesDaImagem(u) {
  try {
    if (u.startsWith('data:')) {
      const v = u.indexOf(',');
      if (v < 0) return null;
      const cab = u.slice(5, v), corpo = u.slice(v + 1);
      return /;base64/i.test(cab) ? Buffer.from(corpo, 'base64') : Buffer.from(decodeURIComponent(corpo), 'utf8');
    }
    if (u.startsWith('file:')) {
      const arq = fileURLToPath(u.split('#')[0].split('?')[0]);
      const st = fs.statSync(arq);
      if (!st.isFile() || st.size > 64 * 1024 * 1024) return null;
      return fs.readFileSync(arq);
    }
  } catch { /* arquivo sumiu ou URL estranha: quem reclama é o carregamento da própria página */ }
  return null;
}

/** [{url, motivo}] das imagens da página que animam sozinhas. */
function imagensAnimadas(urls) {
  const achadas = [];
  for (const u of urls || []) {
    const motivo = animacaoDaImagem(bytesDaImagem(String(u)));
    if (motivo) achadas.push({ url: u.startsWith('data:') ? u.slice(0, 40) + '…' : decodeURIComponent(u.replace(/^file:\/\//, '')), motivo });
  }
  return achadas;
}

// ─────────────────────────────────────────────────── comparação de retratos ──
/** PNG de 8 bits, RGB ou RGBA, sem entrelaçamento (o que o Chromium grava) → { L, A, canais, px } ou null. */
function decodificarPng(buf) {
  try {
    if (buf.length < 33 || buf.readUInt32BE(0) !== 0x89504e47) return null;
    let i = 8, L = 0, A = 0, tipoCor = 0, bits = 0, entrelacado = 0;
    const partes = [];
    while (i + 8 <= buf.length) {
      const tam = buf.readUInt32BE(i), tipo = buf.toString('latin1', i + 4, i + 8);
      if (tipo === 'IHDR') { L = buf.readUInt32BE(i + 8); A = buf.readUInt32BE(i + 12); bits = buf[i + 16]; tipoCor = buf[i + 17]; entrelacado = buf[i + 20]; }
      else if (tipo === 'IDAT') partes.push(buf.subarray(i + 8, i + 8 + tam));
      else if (tipo === 'IEND') break;
      i += 12 + tam;
    }
    const canais = tipoCor === 6 ? 4 : tipoCor === 2 ? 3 : 0;
    if (!canais || bits !== 8 || entrelacado || !L || !A) return null;
    const bruto = zlib.inflateSync(Buffer.concat(partes));
    const passo = L * canais, px = Buffer.allocUnsafe(passo * A);
    for (let y = 0; y < A; y++) {
      const f = bruto[y * (passo + 1)], lin = y * (passo + 1) + 1, o = y * passo;
      for (let x = 0; x < passo; x++) {
        const esq = x >= canais ? px[o + x - canais] : 0, cima = y ? px[o + x - passo] : 0;
        let v = bruto[lin + x];
        if (f === 1) v += esq;
        else if (f === 2) v += cima;
        else if (f === 3) v += (esq + cima) >> 1;
        else if (f === 4) {
          const diag = (y && x >= canais) ? px[o + x - passo - canais] : 0;
          const p = esq + cima - diag, pa = Math.abs(p - esq), pb = Math.abs(p - cima), pc = Math.abs(p - diag);
          v += (pa <= pb && pa <= pc) ? esq : (pb <= pc ? cima : diag);
        }
        px[o + x] = v & 255;
      }
    }
    return { L, A, canais, px };
  } catch { return null; }
}

/**
 * Dois retratos PNG mostram o MESMO quadro? Bytes iguais = sim. Bytes diferentes: decodifica e ignora o ruído de
 * rasterização do Chromium (medido: 11 pixels com diferença ≤ 50 numa prancha de 480×1940 com foto reduzida, de um
 * retrato para o outro, sem nada mudar na página). Quadro diferente = pelo menos max(24, 0,002 % da área) pixels com
 * diferença ≥ 48 em algum canal — uma caixa que anda 3 px ou um cursor piscando passam disso com folga.
 */
function mesmoQuadro(a, b) {
  if (a.equals(b)) return true;
  const A = decodificarPng(a), B = decodificarPng(b);
  if (!A || !B || A.L !== B.L || A.A !== B.A || A.canais !== B.canais) return false;
  const limite = Math.max(24, Math.round(A.L * A.A * 0.00002));
  let fortes = 0;
  for (let i = 0; i < A.px.length; i += A.canais) {
    let d = 0;
    for (let k = 0; k < A.canais; k++) { const v = Math.abs(A.px[i + k] - B.px[i + k]); if (v > d) d = v; }
    if (d >= 48 && ++fortes >= limite) return false;
  }
  return true;
}

// ─────────────────────────────────────────────────────────────── render ──
function log(...a) { console.error(...a); }
const dormir = (ms) => new Promise((ok) => setTimeout(ok, ms));

// Tudo o que precisa morrer junto com este processo. O Chromium é morto pelo próprio Playwright no evento 'exit'
// (ele registra o grupo de processos do browser); ffmpeg e .parcial são daqui.
const VIVO = { ff: null, parciais: new Set(), progresso: Date.now(), fase: 'início', abortando: false };
function progresso(fase) { VIVO.progresso = Date.now(); if (fase) VIVO.fase = fase; }

function abortar(codigo, mensagem) {
  if (VIVO.abortando) return;
  VIVO.abortando = true;
  try { if (mensagem) console.error(mensagem); } catch { /* stderr fechado */ }
  try { if (VIVO.ff) VIVO.ff.kill('SIGKILL'); } catch { /* já morreu */ }
  for (const p of VIVO.parciais) { try { fs.unlinkSync(p); } catch { /* não existia */ } }
  process.exit(codigo);
}

function armarVigias(limiteInatividade) {
  for (const [sinal, codigo] of [['SIGINT', 130], ['SIGTERM', 143], ['SIGHUP', 129]]) {
    process.on(sinal, () => abortar(codigo, `erro: interrompido por ${sinal} — render abortado (ffmpeg e Chromium encerrados, .parcial apagado)`));
  }
  const dono = donoDaTrava();
  const pai = process.ppid;
  const t = setInterval(() => {
    if (dono) {
      let vivo = true;
      try { process.kill(dono, 0); } catch (e) { vivo = e.code === 'EPERM'; }
      if (!vivo) abortar(1, `erro: o dono da trava (pid ${dono}) morreu — render abortado para não seguir fora da fila`);
    }
    // quem pediu o render morreu (até por SIGKILL): ninguém mais espera esta peça, e ela não pode seguir órfã
    if (pai > 1 && process.ppid !== pai) abortar(1, `erro: o processo que pediu o render (pid ${pai}) morreu — render abortado`);
    const parado = (Date.now() - VIVO.progresso) / 1000;
    if (limiteInatividade > 0 && parado > limiteInatividade) {
      abortar(124, `erro: render sem progresso há ${Math.round(parado)} s (${VIVO.fase}) — abortado; ffmpeg e Chromium encerrados e a trava liberada.\n` +
        'Se a cena é mesmo lenta assim, aumente com --inatividade SEG; senão procure um laço sem fim em seek()/build().');
    }
  }, 500);
  t.unref();
}

async function abrirPagina(browser, plano, da) {
  const ctx = await browser.newContext({ viewport: { width: plano.fmt.L, height: plano.fmt.A }, deviceScaleFactor: plano.escala });
  const page = await ctx.newPage();
  const errosPagina = [];
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errosPagina.push(m.text()); });
  page.on('pageerror', (e) => errosPagina.push(String(e.message || e)));
  await page.goto(url(PALCO_HTML));
  const cfg = {
    da_css: url(path.join(da.build, 'da.css')), da_js: url(path.join(da.build, 'da.js')),
    runtime: url(path.join(MOTOR, 'runtime.js')), auditor: url(path.join(MOTOR, 'auditor.js')),
    cena: url(plano.cenaArq), formato: { nome: plano.fmt.nome, L: plano.fmt.L, A: plano.fmt.A, fps: plano.fmt.fpsFloat, auto: !!plano.fmt.auto },
    dur: plano.dur, params: plano.params, alfa: plano.alfa, grao: plano.grao,
  };
  let info, timer = null;
  try {
    info = await Promise.race([
      page.evaluate((c) => window.__palco.iniciar(c), cfg),
      new Promise((_, falha) => { timer = setTimeout(() => falha(new Error('a cena não ficou pronta em 90 s (READY)')), 90000); timer.unref(); }),
    ]);
  } catch (e) {
    const detalhe = errosPagina.length ? `\n  página: ${errosPagina.slice(0, 5).join('\n  página: ')}` : '';
    try { await ctx.close(); } catch { /* ok */ }
    throw new MotorErro(`a cena falhou ao montar: ${String(e.message || e).split('\n')[0]}${detalhe}`);
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (plano.fmt.auto) {                                      // altura automática: fixa o viewport na altura real do conteúdo
    const h = Math.max(2, Math.ceil((info.altura || plano.fmt.A) / 2) * 2);
    plano.fmt.A = h;
    plano.fmt.nome = `${plano.fmt.L}x${h}`;
    plano.dims = [Math.round(plano.fmt.L * plano.escala), Math.round(h * plano.escala)];
    await page.setViewportSize({ width: plano.fmt.L, height: h });
    await page.evaluate((hh) => window.__palco.fixarAltura(hh), h);
  }
  return { ctx, page, info, errosPagina };
}

function imprimirAuditoria(rel, plano) {
  log(`AUDITORIA REPROVADA — ${rel.violacoes.length} violação(ões), ${rel.animacoes.length} animação(ões) em ${path.basename(plano.cenaArq)}:`);
  for (const v of rel.violacoes.slice(0, 40)) {
    log(`  t=${v.t}s  ${v.seletor}  ${v.propriedade}: ${v.valor}  — ${v.motivo}${v.proximo ? (v.propriedade === 'font-family' ? `; ${v.proximo}` : `; mais próximo: ${v.proximo}`) : ''}`);
  }
  if (rel.violacoes.length > 40) log(`  … e mais ${rel.violacoes.length - 40}`);
  for (const a of rel.animacoes) log(`  t=${a.t}s  ${a.seletor}  ${a.tipo}${a.nome ? ' ' + a.nome : ''} — animação ativa (document.getAnimations)`);
  log('  Use tokens (ctx.cor, var(--da-*), .da-<papel>). Foto, logo de terceiros, captura de tela: data-da-livre="motivo" no elemento (fica no carimbo). Para pular: --sem-auditoria (fica no carimbo).');
}

/** Roda uma função na página; erro de seek/build vira MotorErro de uma linha (sem a pilha do page.evaluate). */
async function naPagina(page, fn, arg, oQue) {
  try { return await page.evaluate(fn, arg); } catch (e) {
    const linha = String(e && e.message || e).split('\n')[0].replace(/^(?:page\.evaluate: )?(?:Error: )?/, '');
    throw new MotorErro(/a cena lançou erro/.test(linha) ? linha : `${oQue}: ${linha}`,
      { dica: 'O erro é da cena (módulo .js): confira seek(t)/build() com os params usados.' });
  }
}

function descreverMorte(m, i, N, erroFf) {
  const como = m && m.erro ? `não iniciou (${m.erro.message})` : m && m.sinal ? `morreu com o sinal ${m.sinal}` : `saiu com código ${m ? m.codigo : '?'}`;
  return `o ffmpeg ${como} no quadro ${i}/${N} — nada foi gravado.${erroFf.trim() ? '\n' + erroFf.trim().slice(-600) : ''}`;
}

async function renderizarJob(browser, plano, da, opcoesGlobais) {
  const t0 = Date.now();
  const { fmt, saida } = plano;
  try { mkdirp(path.dirname(saida)); } catch (e) {
    throw new MotorErro(`não consegui criar a pasta de saída ${path.dirname(saida)}: ${e.code || e.message}`, { dica: 'Confira o caminho de --saida (pasta gravável).' });
  }
  progresso(`abrindo ${path.basename(plano.cenaArq)}`);
  const { ctx, page, info, errosPagina } = await abrirPagina(browser, plano, da);
  let auditoria = 'pulada';
  const resultado = { cena: path.basename(plano.cenaArq), saida, formato: fmt.nome, dur: plano.dur, alfa: plano.alfa, codec: plano.codec, escala: plano.escala };
  const tmp = saida + '.parcial';
  try {
    log(`[${resultado.cena}] ${fmt.nome} ${fmt.L}×${fmt.A}${plano.escala !== 1 ? ` (escala ${plano.escala} → ${plano.dims.join('×')})` : ''}` +
        `${plano.quadro == null ? ` ${fmt.fpsTexto} fps · ${num(plano.dur, 3)} s` : ` · quadro t=${num(plano.quadro, 3)}`}` +
        `${plano.alfa ? ' · alfa' : ''}${info.meta.grao ? ' · grão' : ''}` +
        (info.fontes ? ` · fontes: ${Object.entries(info.fontes).map(([k, f]) => `${k}${f.carregada ? '' : '✗'}`).join(' ')}` : ''));
    for (const w of plano.avisos || []) log(`[${resultado.cena}] ! ${w}`);
    let livres = [];
    if (!plano.semAuditoria) {
      progresso('auditoria');
      const amostras = plano.quadro != null ? [plano.quadro] : amostrasDaAuditoria(plano.dur, info.ancoras, info.layout);
      const rel = await naPagina(page, (a) => window.__palco.auditar({ amostras: a }), amostras, 'o auditor falhou');
      if (!rel.ok) {
        imprimirAuditoria(rel, plano);
        throw new MotorErro(`auditoria reprovada (${rel.violacoes.length} violação(ões), ${rel.animacoes.length} animação(ões))`);
      }
      // pureza: seek(t) não pode depender de onde o seek anterior parou (senão --quadro T ≠ quadro T do vídeo)
      const instantes = plano.quadro != null ? [plano.quadro] : instantesDePureza(plano.dur, info.layout);
      const lay = info.layout || {};
      const repouso = Number.isFinite(lay.fim_entrada) && Number.isFinite(lay.inicio_saida) && lay.inicio_saida > lay.fim_entrada
        ? (lay.fim_entrada + lay.inicio_saida) / 2 : plano.dur / 2;
      const passoQuadro = fmt.fps ? fmt.fps.den / fmt.fps.num : 1 / 30;
      const suspeitos = await naPagina(page, ([a, op]) => window.__palco.pureza(a, op), [instantes, { repouso, passo: passoQuadro }], 'a checagem de pureza falhou');
      const impuros = [];
      for (const s of suspeitos) {                               // o DOM difere: só é impureza de verdade se os PIXELS diferirem
        await naPagina(page, ([antes, t]) => { window.seek(antes); window.seek(t); }, [0, s.t], 'seek falhou');
        const a = await page.screenshot({ type: 'png', omitBackground: plano.alfa });
        await naPagina(page, ([antes, t]) => { window.seek(antes); window.seek(t); }, [s.de, s.t], 'seek falhou');
        const b = await page.screenshot({ type: 'png', omitBackground: plano.alfa });
        if (!mesmoQuadro(a, b)) impuros.push(s);
      }
      if (impuros.length) {
        const i = impuros[0];
        log(`CENA IMPURA — seek(${num(i.t, 3)}) desenha um quadro diferente conforme o seek anterior em ${path.basename(plano.cenaArq)}:`);
        log(`  vindo de seek(0):${' '.repeat(Math.max(1, num(i.de, 3).length))} ${i.depois_de_0.replace(/\s+/g, ' ').slice(0, 200)}`);
        log(`  vindo de seek(${num(i.de, 3)}): ${i.depois_de_outro.replace(/\s+/g, ' ').slice(0, 200)}`);
        log('  Em seek(t), aplique SEMPRE o estado completo de cada elemento para aquele t (inclusive na janela de saída); nada de "return" antes de posicionar os filhos.');
        throw new MotorErro(`a cena não é função pura de t (${impuros.length} instante(s) divergem; o 1º é t=${num(i.t, 3)} s)`);
      }
      // imagens que animam sozinhas (GIF, APNG, WebP, SVG com animação): conferidas no disco, inclusive as data-da-livre
      const animadas = imagensAnimadas(await naPagina(page, () => window.__palco.imagens(), null, 'a listagem de imagens falhou'));
      if (animadas.length) {
        log(`IMAGEM ANIMADA — ${animadas.length} imagem(ns) de ${path.basename(plano.cenaArq)} anima(m) no relógio do navegador, fora de seek(t):`);
        for (const a of animadas.slice(0, 8)) log(`  ${a.motivo}: ${a.url}`);
        log('  Use um quadro parado (PNG/JPG) ou componha o trecho em vídeo no ffmpeg (video.compor_overlay); data-da-livre libera a cor, não o movimento.');
        throw new MotorErro(`imagem animada na peça (${animadas[0].motivo}): o quadro deixa de ser função de t`);
      }
      // quietude: com o MESMO seek(t), dois retratos separados por 120 ms têm de ser idênticos — senão algo anima fora de
      // seek(t) (SMIL, vídeo, laço por mensagem, promessa ou observer, cursor piscando); e repetir o seek(t) não muda nada
      {
        progresso('auditoria (quietude)');
        const tq = plano.quadro != null ? plano.quadro : instantes[Math.min(1, instantes.length - 1)];
        const foto = () => page.screenshot({ type: 'png', omitBackground: plano.alfa });
        await naPagina(page, (t) => { window.seek(t); }, tq, 'seek falhou');
        const a = await foto();
        await dormir(120);
        let ref = await foto();
        let motivo = null, par = null;
        if (!mesmoQuadro(a, ref)) {
          await dormir(160);
          const c = await foto();
          // a ≠ b e b = c: a página só terminou de assentar (imagem grande decodificando); a ≠ b ≠ c: está se mexendo
          if (!mesmoQuadro(ref, c)) { motivo = 'dois retratos do MESMO instante, sem nenhum seek entre eles, saíram diferentes: algo anima no relógio do navegador'; par = [ref, c]; }
          ref = c;
        }
        if (!motivo) {
          await naPagina(page, (t) => { window.seek(t); }, tq, 'seek falhou');
          const d = await foto();
          if (!mesmoQuadro(ref, d)) { motivo = 'chamar seek(t) duas vezes com o mesmo t desenhou quadros diferentes: há relógio ou sorteio escondido em seek()'; par = [ref, d]; }
        }
        if (motivo) {
          log(`PEÇA INQUIETA — em t=${num(tq, 3)} s, ${motivo} (${path.basename(plano.cenaArq)}).`);
          try {                                                  // os dois retratos ficam no build da DA: compare-os para achar o que se mexe
            const pasta = path.join(da.build, 'depurar');
            mkdirp(pasta);
            fs.writeFileSync(path.join(pasta, 'quietude_a.png'), par[0]); fs.writeFileSync(path.join(pasta, 'quietude_b.png'), par[1]);
            log(`  Os dois retratos: ${path.join(pasta, 'quietude_a.png')} e quietude_b.png — a diferença entre eles mostra o que se mexe.`);
          } catch { /* sem pasta gravável: segue só com a mensagem */ }
          log('  Procure: <animate>/<set> (SMIL), GIF ou vídeo, laço por MessageChannel/postMessage, promessa ou observer que se reagenda, contenteditable com foco.');
          log('  Tudo o que muda na tela tem de ser calculado dentro de seek(t), a partir de t.');
          throw new MotorErro(`a peça se mexe fora de seek(t) (t=${num(tq, 3)} s): ${motivo.split(':')[0]}`);
        }
      }
      // usos de API proibida DEPOIS da auditoria de estilos (laço que só começou a rodar agora) também reprovam
      const tardios = await naPagina(page, (n) => window.__palco.apis.slice(n), (rel.apis_vistas ?? 0), 'a conferência de APIs falhou');
      if (tardios.length) {
        log(`API PROIBIDA — ${tardios.length} uso(s) depois do build em ${path.basename(plano.cenaArq)}:`);
        for (const u of tardios.slice(0, 10)) log(`  ${u.api}${u.vezes > 1 ? ` ×${u.vezes}` : ''} em ${u.onde} (${u.fase})`);
        throw new MotorErro(`a cena usa ${tardios[0].api} fora de seek(t): a peça tem de ser função pura de t`);
      }
      auditoria = 'ok';
      livres = rel.livres || [];
      log(`[${resultado.cena}] auditoria ok (${amostras.length} instante${amostras.length > 1 ? 's' : ''}, pureza em ${instantes.length}, quietude em 1)` +
          (livres.length ? ` · ${livres.length} elemento(s) data-da-livre: ${livres.map((l) => l.seletor + (l.motivo ? ` (${l.motivo})` : '')).slice(0, 6).join(', ')}` : ''));
    } else {
      log(`[${resultado.cena}] AUDITORIA PULADA (--sem-auditoria): o carimbo registra e conferir-carimbo reprova`);
    }
    progresso('render');
    const parametros = {
      cena: plano.cena, cena_arquivo: plano.cenaArq, params: plano.params, formato: fmt.nome, largura: plano.dims[0], altura: plano.dims[1],
      fps: fmt.fpsTexto, dur: plano.dur, alfa: plano.alfa, codec: plano.codec, escala: plano.escala, quadro: plano.quadro,
      ancoras: info.ancoras || [], layout: info.layout || null, livres,
      chromium: path.basename(path.dirname(path.dirname(opcoesGlobais.chrome))), kit_versao: KIT_VERSAO,
    };
    VIVO.parciais.add(tmp);
    if (plano.quadro != null) {
      await naPagina(page, (t) => window.seek(t), plano.quadro, 'seek falhou');
      const png = await page.screenshot({ type: 'png', omitBackground: plano.alfa, fullPage: false });
      fs.writeFileSync(tmp, png);
      const d = dimensoesPng(tmp);
      if (d.largura !== plano.dims[0] || d.altura !== plano.dims[1]) throw new MotorErro(`PNG saiu ${d.largura}×${d.altura}, esperava ${plano.dims.join('×')}`);
      resultado.quadros = 1;
    } else {
      const fps = fmt.fps;
      const N = Math.round(plano.dur * fps.num / fps.den);
      const args = argsCodec(plano.codec, fmt, fps, tmp, plano.dims);
      const ff = spawn(opcoesGlobais.ffmpeg, args, { stdio: ['pipe', 'ignore', 'pipe'] });
      VIVO.ff = ff;
      let erroFf = '';
      ff.stderr.on('data', (d) => { erroFf = (erroFf + d.toString()).slice(-4000); });
      // `fim` nasce junto com o processo: nunca se registra um listener depois de o evento já ter passado
      let morte = null;
      const fim = new Promise((ok) => {
        ff.once('error', (e) => { morte = morte || { erro: e }; ok(morte); });
        ff.once('close', (codigo, sinal) => { morte = { codigo, sinal }; ok(morte); });
      });
      ff.stdin.on('error', () => { /* EPIPE: quem decide é a corrida contra `fim` */ });
      let quadroAtual = 0;
      const ffSaiu = fim.then((m) => { throw new MotorErro(descreverMorte(m, quadroAtual, N, erroFf)); });
      ffSaiu.catch(() => { /* só interessa a quem estiver esperando uma escrita */ });
      const escrever = (buf) => Promise.race([
        new Promise((ok, falha) => {
          if (morte || ff.stdin.destroyed) return falha(new Error('stdin do ffmpeg fechado'));
          ff.stdin.write(buf, (e) => (e ? falha(e) : ok()));     // o callback só vem quando o pedaço foi entregue (contrapressão)
        }),
        ffSaiu,
      ]);
      const cache = new Map();
      let reuso = 0;
      const passo = fps.den / fps.num;
      try {
        for (let i = 0; i < N; i++) {
          quadroAtual = i;
          const t = Math.min(plano.dur, i * passo);
          const key = await naPagina(page, (tt) => { window.seek(tt); return window.frameKey ? window.frameKey(tt) : null; }, t, 'seek falhou');
          let buf = key != null ? cache.get(key) : undefined;
          if (buf) reuso++;
          else {
            buf = await page.screenshot({ type: 'png', omitBackground: plano.alfa });
            if (key != null) cache.set(key, buf);
          }
          try { await escrever(buf); } catch (e) {
            if (e instanceof MotorErro) throw e;
            const m = await Promise.race([fim, new Promise((ok) => setTimeout(() => ok(null), 3000))]);   // EPIPE: espera o código de saída
            throw new MotorErro(descreverMorte(m || { codigo: `? (${e.code || e.message})` }, i, N, erroFf));
          }
          progresso(`quadro ${i + 1}/${N}`);
          if (i && i % 120 === 0) log(`[${resultado.cena}] ${i}/${N} quadros · ${((Date.now() - t0) / 1000).toFixed(0)} s${reuso ? ` · reuso ${reuso}` : ''}`);
        }
        quadroAtual = N;
        progresso('fechando o ffmpeg');
        ff.stdin.end();
        const m = await fim;
        if (m.erro || m.codigo !== 0) throw new MotorErro(descreverMorte(m, N, N, erroFf));
      } catch (e) {
        try { ff.stdin.destroy(); ff.kill('SIGKILL'); } catch { /* já morreu */ }
        throw e;
      } finally {
        VIVO.ff = null;
      }
      progresso('conferindo com ffprobe');
      const s = ffprobe(tmp, { formato: { h264: 'mp4', prores4444: 'mov', vp9alfa: 'webm' }[plano.codec] });
      const problemas = [];
      if (s.width !== plano.dims[0] - (plano.dims[0] % 2) || s.height !== plano.dims[1] - (plano.dims[1] % 2)) problemas.push(`resolução ${s.width}×${s.height} ≠ ${plano.dims.join('×')}`);
      if (s.r_frame_rate !== `${fps.num}/${fps.den}` && s.avg_frame_rate !== `${fps.num}/${fps.den}`) problemas.push(`fps ${s.r_frame_rate} ≠ ${fps.num}/${fps.den}`);
      const nq = parseInt(s.nb_read_frames || s.nb_frames, 10);
      if (nq !== N) problemas.push(`quadros ${nq} ≠ ${N}`);
      const pixEsperado = { h264: /^yuv420p$/, prores4444: /^yuva444p1[02]le$/, vp9alfa: /^yuva420p$/ }[plano.codec];
      if (!pixEsperado.test(s.pix_fmt)) problemas.push(`pix_fmt ${s.pix_fmt} (esperava ${CODECS[plano.codec].pix})`);
      if (problemas.length) throw new MotorErro('ffprobe: ' + problemas.join('; '));
      resultado.quadros = N; resultado.reuso = reuso; resultado.pix_fmt = s.pix_fmt; resultado.codec_ffprobe = s.codec_name;
      parametros.quadros = N; parametros.quadros_reaproveitados = reuso;
    }
    // A peça foi desenhada com a DA do INÍCIO. O carimbo é calculado sobre o .parcial exigindo essa mesma identidade:
    // se o da.json mudou no meio, o da.py recusa, o .parcial é apagado e a saída anterior (com o carimbo dela) fica intacta.
    progresso('carimbo');
    parametros.tempo_s = +((Date.now() - t0) / 1000).toFixed(2);
    resultado.carimbo = carimbar(saida, { da_json: da.da_json, formato: fmt.nome, parametros, auditoria, sha_esperado: da.DA._meta.sha256, origem: tmp });
    fs.renameSync(tmp, saida);
    VIVO.parciais.delete(tmp);
    resultado.auditoria = auditoria;
    resultado.livres = livres.length;
    resultado.mb = tamanhoMB(saida);
    resultado.tempo_s = parametros.tempo_s;
    progresso('job concluído');
    log(`[${resultado.cena}] OK ${saida}  ${resultado.mb} MB · ${resultado.tempo_s} s${resultado.reuso ? ` · ${resultado.reuso}/${resultado.quadros} quadros reaproveitados` : ''} · carimbo ${path.basename(resultado.carimbo)}`);
    if (errosPagina.length) log(`[${resultado.cena}] avisos da página: ${errosPagina.slice(0, 3).join(' | ')}`);
    return resultado;
  } catch (e) {
    try { if (fs.existsSync(tmp)) fs.unlinkSync(tmp); } catch { /* ok */ }
    VIVO.parciais.delete(tmp);
    throw e;
  } finally {
    try { await ctx.close(); } catch { /* ok */ }
  }
}

// ──────────────────────────────────────────────────────────────── principal ──
async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || (!a.cena && !a.fila)) { console.log(AJUDA); return a.help ? 0 : 64; }
  if (a._.length) throw new MotorErro(`argumentos não reconhecidos: ${a._.join(' ')}`, { codigo: 64 });
  let inatividade = 120;
  const pedida = a.inatividade ?? process.env.VIDEO_OPS_INATIVIDADE;
  if (pedida != null && String(pedida).trim() !== '') {
    inatividade = Number(pedida);
    if (!Number.isFinite(inatividade) || inatividade < 0) throw new MotorErro(`--inatividade ${pedida} inválido (segundos; 0 desliga)`, { codigo: 64 });
  }
  const dentro = !!a['sem-trava'] || sobTrava();
  const jaAvisado = process.env.VIDEO_OPS_MOTOR_AVISADO === '1';

  // 1. Tudo o que é erro de uso aparece AQUI, antes da fila da trava e antes de abrir o browser.
  const da = carregarDA({ da: a.da || null, de: a.de || null });
  if (!jaAvisado) {
    if (da.recompilou) log(`[da] build recompilado (${da.da_json})`);
    for (const w of da.avisos || []) log(`[da] ! ${w}`);
    if (da.DA._meta.alterada_apos_aprovacao) {
      log(`[da] ! DA ALTERADA DEPOIS DA APROVAÇÃO (revisão ${da.DA._meta.revisao}): as peças saem carimbadas como NÃO aprovadas e conferir-carimbo acusa. ` +
          'Rode `da.py revisar` e depois `da.py aprovar` quando o visual estiver fechado.');
    }
  }
  const padroes = { formato: a.formato, dur: a.dur, fps: a.fps, alfa: a.alfa, quadro: a.quadro, codec: a.codec, escala: a.escala, 'sem-auditoria': a['sem-auditoria'] };
  let jobs;
  if (a.fila) {
    let lista;
    try { lista = JSON.parse(fs.readFileSync(a.fila, 'utf8')); } catch (e) { throw new MotorErro(`--fila: não consegui ler ${a.fila} (${e.message})`, { codigo: 64 }); }
    if (!Array.isArray(lista) || !lista.length) throw new MotorErro('--fila: o arquivo precisa ser uma lista JSON de jobs', { codigo: 64 });
    const base = path.dirname(path.resolve(a.fila));
    jobs = lista.map((j, i) => {
      if (!j || typeof j !== 'object' || Array.isArray(j)) throw new MotorErro(`--fila: job ${i} não é um objeto`, { codigo: 64 });
      const saida = j.saida ? path.resolve(base, j.saida) : null;
      return prepararJob({ ...j, saida, alfa: j.alfa, 'sem-auditoria': j.sem_auditoria ?? j['sem-auditoria'] ?? a['sem-auditoria'], _chaves: j }, da.DA, base, padroes);
    });
  } else {
    jobs = [prepararJob({ cena: a.cena, saida: a.saida, params: a.params }, da.DA, process.cwd(), padroes)];
  }
  const planos = [];
  for (const [i, j] of jobs.entries()) {
    try { planos.push(await planejarJob(j, da.DA)); } catch (e) {
      if (e instanceof MotorErro && a.fila) e.message = `job ${i} (${j.cena}): ${e.message}`;
      throw e;
    }
  }
  if (a.validar) {
    const linhas = planos.map((p, i) => `  ${String(i).padStart(2)}  ${path.basename(p.cenaArq).padEnd(22)} ${p.fmt.nome.padEnd(11)} ${p.quadro != null ? `quadro ${num(p.quadro, 3)}` : `${num(p.dur, 3)} s ${p.codec}`}  → ${p.saida}`);
    for (const p of planos) for (const w of p.avisos) log(`! ${path.basename(p.cenaArq)}: ${w}`);
    if (a.json) console.log(JSON.stringify({ ok: true, validado: true, da_sha256: da.DA._meta.sha256, jobs: planos.map((p) => ({ cena: path.basename(p.cenaArq), saida: p.saida, formato: p.fmt.nome, dur: p.dur, quadro: p.quadro, codec: p.codec })) }, null, 1));
    else console.log(`VÁLIDO: ${planos.length} job(s), nada foi renderizado.\n${linhas.join('\n')}`);
    return 0;
  }
  if (!dentro) {
    const rotulo = a.fila ? `render fila ${path.basename(a.fila)}` : `render ${path.basename(String(a.cena))}`;
    return reexecutarSobTrava(rotulo);
  }

  // 2. Daqui em diante há processos pesados: sinais, morte do dono da trava e inatividade abortam tudo.
  armarVigias(inatividade);
  const chrome = acharChromium();
  const ffmpeg = acharFfmpeg('ffmpeg');
  progresso('abrindo o Chromium');
  const browser = await chromium.launch({ executablePath: chrome, headless: true, args: ARGS_CHROME, handleSIGINT: false, handleSIGTERM: false, handleSIGHUP: false });
  const ok = [], falhas = [];
  try {
    for (const plano of planos) {
      try { ok.push(await renderizarJob(browser, plano, da, { chrome, ffmpeg })); }
      catch (e) {
        const msg = e instanceof MotorErro ? e.toString() : (e && e.stack) || String(e);
        log(`[${path.basename(plano.cenaArq)}] FALHA: ${msg}`);
        falhas.push({ cena: path.basename(plano.cenaArq), saida: plano.saida, erro: msg.split('\n')[0] });
      }
    }
  } finally {
    progresso('fechando o Chromium');
    await browser.close();
  }
  if (planos.length > 1 || a.fila) {
    log(`\nRESUMO: ${ok.length} ok, ${falhas.length} falha(s)`);
    for (const o of ok) log(`  OK     ${path.basename(o.saida).padEnd(32)} ${o.quadros} quadro(s) · ${o.mb} MB · ${o.tempo_s} s`);
    for (const f of falhas) log(`  FALHA  ${path.basename(f.saida || '?').padEnd(32)} ${f.erro}`);
  }
  if (a.json) console.log(JSON.stringify({ ok: !falhas.length, da_sha256: da.DA._meta.sha256, renderizados: ok, falhas }, null, 1));
  return falhas.length ? 1 : 0;
}

main().then((c) => { process.exitCode = c; }).catch((e) => {
  if (VIVO.abortando) return;
  if (e instanceof MotorErro) { console.error('erro: ' + e.toString()); process.exitCode = e.codigo || 1; }
  else { console.error('erro interno: ' + (e && e.stack || e)); process.exitCode = 1; }
});
