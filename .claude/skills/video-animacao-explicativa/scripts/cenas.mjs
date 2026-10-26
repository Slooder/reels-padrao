#!/usr/bin/env node
// cenas.mjs — lê o que as cenas declaram SEM abrir o navegador (quem chama é o storyboard.py).
//
//   node cenas.mjs meta <cena.js> [<cena.js> …]      → [{ arquivo, nome, meta, tem_roteiro } | { arquivo, erro }]
//   node cenas.mjs roteiro <movimento.json>           (stdin: [{ arquivo, params }])
//        → [{ passos: [{ nome, tipo, anim }], minima, recomendada } | { passos: null } | { erro }]
//
// `meta` é o export de toda cena do motor; `roteiro(params, movimento)` é o export das cenas desta biblioteca que
// diz quais passos a cena terá com aqueles parâmetros e quanto dura a animação de cada um — é com ele que o
// storyboard confere o ritmo e casa as marcas da narração antes do render. Cenas do kit não têm roteiro: passos = null.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const IA = pathToFileURL(path.join(AQUI, '..', 'cenas', '_ia.js')).href;

async function importar(arquivo) {
  const mod = await import(pathToFileURL(path.resolve(arquivo)).href);
  if (typeof mod.build !== 'function' || typeof mod.seek !== 'function') throw new Error('não é uma cena do motor: faltam os exports build(palco, params, ctx) e seek(t)');
  return mod;
}

/** Aplica os padrões de meta.params (só o primeiro nível, como o validador do motor faz antes de conferir). */
function comPadroes(meta, params) {
  const p = {};
  for (const [k, def] of Object.entries((meta && meta.params) || {})) {
    p[k] = params && k in params && params[k] != null ? params[k] : (def.padrao === undefined ? null : JSON.parse(JSON.stringify(def.padrao)));
  }
  return p;
}

async function main() {
  const [modo, ...resto] = process.argv.slice(2);
  if (modo === 'meta') {
    const saida = [];
    for (const arquivo of resto) {
      try {
        const mod = await importar(arquivo);
        saida.push({ arquivo, nome: (mod.meta && mod.meta.nome) || path.basename(arquivo, '.js'), meta: mod.meta || {}, tem_roteiro: typeof mod.roteiro === 'function' });
      } catch (e) { saida.push({ arquivo, erro: String(e && e.message || e).split('\n')[0] }); }
    }
    process.stdout.write(JSON.stringify(saida));
    return 0;
  }
  if (modo === 'roteiro') {
    const movimento = JSON.parse(fs.readFileSync(resto[0], 'utf8'));
    const pedidos = JSON.parse(fs.readFileSync(0, 'utf8'));
    const { duracoes } = await import(IA);
    const saida = [];
    for (const ped of pedidos) {
      try {
        const mod = await importar(ped.arquivo);
        if (typeof mod.roteiro !== 'function') { saida.push({ passos: null }); continue; }
        const passos = mod.roteiro(comPadroes(mod.meta, ped.params || {}), movimento).map((r) => ({ nome: r.nome, tipo: r.tipo || 'enfase', anim: +(+r.anim).toFixed(3) }));
        saida.push({ passos, ...duracoes(passos, movimento) });
      } catch (e) { saida.push({ erro: String(e && e.message || e).split('\n')[0] }); }
    }
    process.stdout.write(JSON.stringify(saida));
    return 0;
  }
  process.stderr.write('uso: node cenas.mjs meta <cena.js>… | node cenas.mjs roteiro <movimento.json> < pedidos.json\n');
  return 64;
}

main().then((c) => { process.exitCode = c; }).catch((e) => { process.stderr.write('erro: ' + (e && e.message || e) + '\n'); process.exitCode = 1; });
