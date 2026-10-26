// comum.mjs — caminhos, descobertas (Chromium, python, ffmpeg) e a ponte com o da.py.
// Tudo é localizado pela posição deste arquivo (import.meta.url): a pasta do kit pode ser copiada inteira.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const MOTOR = path.dirname(fileURLToPath(import.meta.url));
export const KIT = path.dirname(MOTOR);
export const KIT_FINAL = '"$CRIABR_SKILLS"/video-direcao-de-arte/kit';
export const DA_PY = path.join(KIT, 'da.py');
export const TRAVA_PY = path.join(KIT, 'trava.py');
export const PALCO_HTML = path.join(MOTOR, 'palco.html');
export const CENAS_DIR = path.join(MOTOR, 'cenas');
export const ARGS_CHROME = ['--allow-file-access-from-files', '--disable-gpu', '--hide-scrollbars', '--font-render-hinting=none',
  '--disable-dev-shm-usage', '--no-first-run', '--no-default-browser-check'];

export let KIT_VERSAO = '0.0.0';
try { KIT_VERSAO = fs.readFileSync(path.join(KIT, 'VERSAO'), 'utf8').trim() || KIT_VERSAO; } catch { /* sem VERSAO */ }

export class MotorErro extends Error {
  constructor(mensagem, { dica = null, codigo = 1 } = {}) { super(mensagem); this.dica = dica; this.codigo = codigo; }
  toString() { return this.dica ? `${this.message}\n${this.dica}` : this.message; }
}

export const url = (p) => pathToFileURL(path.resolve(p)).href;   // caminho → file:// (espaços e acentos codificados)

// ───────────────────────────────────────────────────────────────── binários ──
function existe(p) { try { return fs.statSync(p).isFile(); } catch { return false; } }

function noPath(nome) {
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    const c = path.join(dir, process.platform === 'win32' ? nome + '.exe' : nome);   // adaptação Windows (local)
    if (dir && existe(c)) return c;
  }
  return null;
}

export function acharPython() {
  const env = process.env.VIDEO_OPS_PYTHON;
  if (env && existe(env)) return env;
  for (const c of ['/opt/homebrew/bin/python3', noPath('python3'), '/usr/local/bin/python3', '/usr/bin/python3']) {
    if (c && existe(c)) return c;
  }
  throw new MotorErro('python3 não encontrado.', { dica: 'Instale o Python 3 (brew install python) ou aponte VIDEO_OPS_PYTHON para o executável.' });
}

export function acharFfmpeg(nome = 'ffmpeg') {
  const env = process.env['VIDEO_OPS_' + nome.toUpperCase()];
  if (env && existe(env)) return env;
  for (const c of [noPath(nome), `/opt/homebrew/bin/${nome}`, `/usr/local/bin/${nome}`]) {
    if (c && existe(c)) return c;
  }
  throw new MotorErro(`${nome} não encontrado.`, { dica: `Instale com \`brew install ffmpeg\` ou aponte VIDEO_OPS_${nome.toUpperCase()}.` });
}

/** Chromium headless shell: VIDEO_OPS_CHROME, senão a revisão mais nova em ~/Library/Caches/ms-playwright. */
export function acharChromium() {
  const env = process.env.VIDEO_OPS_CHROME;
  if (env) {
    if (existe(env)) return env;
    throw new MotorErro(`VIDEO_OPS_CHROME aponta para ${env}, que não existe.`);
  }
  const bases = [path.join(os.homedir(), 'Library', 'Caches', 'ms-playwright'),
    path.join(os.homedir(), '.cache', 'ms-playwright'),
    path.join(process.env.LOCALAPPDATA || '', 'ms-playwright')];               // adaptação Windows (local)
  const achados = [];
  for (const base of bases) {
    let pastas = [];
    try { pastas = fs.readdirSync(base); } catch { continue; }
    for (const p of pastas) {
      const m = /^chromium_headless_shell-(\d+)$/.exec(p) || /^chromium-(\d+)$/.exec(p);
      if (!m) continue;
      const candidatos = [
        path.join(base, p, 'chrome-headless-shell-mac-arm64', 'chrome-headless-shell'),
        path.join(base, p, 'chrome-headless-shell-mac-x64', 'chrome-headless-shell'),
        path.join(base, p, 'chrome-headless-shell-linux64', 'chrome-headless-shell'),
        path.join(base, p, 'chrome-headless-shell-win64', 'chrome-headless-shell.exe'),
        path.join(base, p, 'chrome-mac-arm64', 'Google Chrome for Testing.app', 'Contents', 'MacOS', 'Google Chrome for Testing'),
        path.join(base, p, 'chrome-mac', 'Chromium.app', 'Contents', 'MacOS', 'Chromium'),
        path.join(base, p, 'chrome-linux', 'chrome'),
      ];
      for (const c of candidatos) if (existe(c)) achados.push({ rev: parseInt(m[1], 10), shell: p.startsWith('chromium_headless_shell'), exe: c });
    }
  }
  if (!achados.length) {
    throw new MotorErro('Chromium headless não encontrado.', {
      dica: `Procurei em ${bases.join(' e ')} (chromium_headless_shell-*/chrome-headless-shell-mac-arm64/chrome-headless-shell).\n` +
            `Instale com: cd ${KIT_FINAL} && npx playwright-core install chromium-headless-shell\n` +
            'ou aponte VIDEO_OPS_CHROME para um chrome-headless-shell/Chromium existente.',
    });
  }
  achados.sort((a, b) => (b.shell - a.shell) || (b.rev - a.rev));   // prefere o headless shell e a revisão mais nova
  return achados[0].exe;
}

// ──────────────────────────────────────────────────────────────────── trava ──
/** Mesma regra do trava.py: variável VIDEO_OPS_TRAVA, dono vivo e pid registrado no arquivo da trava. */
export function sobTrava() {
  const v = (process.env.VIDEO_OPS_TRAVA || '').trim();
  if (!/^\d+$/.test(v)) return false;
  const pid = parseInt(v, 10);
  if (pid <= 1) return false;
  try { process.kill(pid, 0); } catch (e) { if (e.code !== 'EPERM') return false; }
  const arq = process.env.VIDEO_OPS_TRAVA_ARQUIVO
    || (process.platform === 'win32' ? path.join(os.tmpdir(), 'video-ops-render.lock') : '/tmp/video-ops-render.lock');
  try {
    const reg = JSON.parse(fs.readFileSync(arq, 'utf8').slice(0, 4096) || '{}');
    return reg.pid === pid;
  } catch { return false; }
}

/** pid do dono da trava sob a qual este processo roda (VIDEO_OPS_TRAVA), ou null. */
export function donoDaTrava() {
  const v = (process.env.VIDEO_OPS_TRAVA || '').trim();
  return /^\d+$/.test(v) && parseInt(v, 10) > 1 ? parseInt(v, 10) : null;
}

/**
 * Reexecuta este processo sob `trava.py -- node …` e devolve (Promise) o código de saída do filho.
 * Assíncrono de propósito: SIGINT/SIGTERM recebidos aqui são repassados ao trava.py, que mata o grupo
 * inteiro (node, Chromium, ffmpeg) antes de soltar a trava. Com spawnSync o sinal mataria só este processo.
 */
export function reexecutarSobTrava(rotulo) {
  return new Promise((ok, falha) => {
    const filho = spawn(acharPython(), [TRAVA_PY, '--rotulo', rotulo || 'render', '--', process.execPath, ...process.argv.slice(1)],
      { stdio: 'inherit', env: { ...process.env, VIDEO_OPS_MOTOR_AVISADO: '1' } });
    const repassar = (sinal) => { try { filho.kill(sinal); } catch { /* já saiu */ } };
    // SIGHUP fica de fora de propósito: registrar um tratador desfaria o `nohup`; no fechamento do terminal o trava.py
    // (mesma sessão) recebe o SIGHUP direto do sistema e encerra a árvore.
    const sinais = ['SIGINT', 'SIGTERM'];
    const tratadores = sinais.map((s) => { const f = () => repassar(s); process.on(s, f); return [s, f]; });
    const soltar = () => { for (const [s, f] of tratadores) process.removeListener(s, f); };
    filho.once('error', (e) => { soltar(); falha(new MotorErro(`não consegui reexecutar sob a trava: ${e.message}`)); });
    filho.once('close', (codigo, sinal) => {
      soltar();
      ok(codigo == null ? 128 + ({ SIGHUP: 1, SIGINT: 2, SIGKILL: 9, SIGTERM: 15 }[sinal] || 1) : codigo);
    });
  });
}

// ────────────────────────────────────────────────────────────────── da.py ──
/** Roda `da.py <args>`; devolve {codigo, stdout, stderr}. */
export function daPy(args, { entrada = null } = {}) {
  const r = spawnSync(acharPython(), [DA_PY, ...args], { encoding: 'utf8', input: entrada ?? undefined, env: process.env,
    maxBuffer: 64 * 1024 * 1024, timeout: 120000, killSignal: 'SIGKILL' });
  if (r.error) throw new MotorErro(`não consegui rodar da.py ${args[0]}: ${r.error.code === 'ETIMEDOUT' ? 'sem resposta em 120 s' : r.error.message}`);
  return { codigo: r.status == null ? 1 : r.status, stdout: r.stdout || '', stderr: r.stderr || '' };
}

/**
 * C1: acha a DA (--da > DA_JSON > sobe as pastas a partir de `de`), recompila se o lock estiver velho
 * e devolve {da_json, raiz, build, DA (resolvida), recompilou, avisos}. Sem DA: MotorErro com código 2.
 */
export function carregarDA({ da = null, de = null } = {}) {
  const alvo = [];
  if (da) alvo.push('--da', da);
  else if (de) alvo.push('--de', de);
  const achar = daPy(['achar', '--json', ...alvo]);
  const limpo = (t) => String(t || '').trim().replace(/^erro:\s*/, '');      // o chamador já prefixa "erro: "
  if (achar.codigo !== 0) {
    throw new MotorErro(limpo(achar.stderr || achar.stdout) || 'nenhuma direção de arte encontrada', { codigo: achar.codigo === 2 ? 2 : 1 });
  }
  const info = JSON.parse(achar.stdout);
  const comp = daPy(['compilar', '--se-preciso', '--json', '--da', info.da_json]);
  if (comp.codigo !== 0) {
    throw new MotorErro(limpo(comp.stderr || comp.stdout) || 'a DA não compilou', { codigo: comp.codigo });
  }
  let compJson = {};
  try { compJson = JSON.parse(comp.stdout); } catch { /* sem json */ }
  const resolvida = path.join(info.build, 'da.resolvida.json');
  let DA;
  try { DA = JSON.parse(fs.readFileSync(resolvida, 'utf8')); } catch (e) {
    throw new MotorErro(`não consegui ler ${resolvida}: ${e.message}`, { dica: 'Rode `da.py compilar` e tente de novo.' });
  }
  return { da_json: info.da_json, raiz: info.raiz, build: info.build, DA, recompilou: !!compJson.compilou,
    avisos: compJson.avisos || [] };
}

/**
 * C4: grava o carimbo <saida>.da.json pelo próprio da.py (uma implementação só).
 * sha_esperado: identidade da DA lida no início do render — se a DA atual for outra, o da.py recusa (nada é gravado).
 * origem: arquivo ainda com nome provisório (o .parcial) que vai virar `saida`: a impressão digital sai dele.
 */
export function carimbar(saida, { da_json, formato, parametros, auditoria, sha_esperado = null, origem = null }) {
  const tmp = path.join(os.tmpdir(), `da-carimbo-${process.pid}-${Date.now()}.json`);
  fs.writeFileSync(tmp, JSON.stringify(parametros ?? {}, null, 1));
  try {
    const args = ['carimbar', saida, '--ferramenta', 'motor', '--parametros', '@' + tmp, '--auditoria', auditoria, '--da', da_json];
    if (formato) args.push('--formato', formato);
    if (sha_esperado) args.push('--sha-esperado', sha_esperado);
    if (origem) args.push('--origem', origem);
    if (auditoria === 'ok') args.push('--reauditada');     // este render acabou de passar pelo auditor: pode substituir um carimbo "pulada" do mesmo arquivo
    const r = daPy(args);
    if (r.codigo !== 0) throw new MotorErro(`carimbo recusado: ${(r.stderr || r.stdout).trim().replace(/^erro:\s*/, '')}`);
    return saida + '.da.json';
  } finally {
    try { fs.unlinkSync(tmp); } catch { /* já foi */ }
  }
}

// ─────────────────────────────────────────────────────────────── utilidades ──
export function ffprobe(arquivo, { contarQuadros = true, formato = null } = {}) {
  const args = ['-v', 'error'];
  if (formato === 'webm' || /\.webm$/i.test(arquivo)) args.push('-c:v', 'libvpx-vp9');   // o decoder nativo ignora o alfa e reporta yuv420p
  args.push('-select_streams', 'v:0');
  if (contarQuadros) args.push('-count_frames');
  args.push('-show_entries', 'stream=codec_name,profile,width,height,pix_fmt,r_frame_rate,avg_frame_rate,nb_read_frames,nb_frames,duration',
    '-of', 'json', arquivo);
  let out;
  try { out = execFileSync(acharFfmpeg('ffprobe'), args, { encoding: 'utf8', timeout: 300000, killSignal: 'SIGKILL', stdio: ['ignore', 'pipe', 'pipe'] }); } catch (e) {
    throw new MotorErro(`ffprobe não conseguiu ler ${arquivo}: ${String(e.stderr || e.message).trim().split('\n').slice(-2).join(' ')}`);
  }
  const s = (JSON.parse(out).streams || [])[0];
  if (!s) throw new MotorErro(`ffprobe não achou trilha de vídeo em ${arquivo}`);
  return s;
}

/** Dimensões de um PNG pelo cabeçalho IHDR (sem decodificar). */
export function dimensoesPng(arquivo) {
  const fd = fs.openSync(arquivo, 'r');
  try {
    const b = Buffer.alloc(24);
    fs.readSync(fd, b, 0, 24, 0);
    if (b.toString('ascii', 1, 4) !== 'PNG') throw new MotorErro(`${arquivo} não é um PNG`);
    return { largura: b.readUInt32BE(16), altura: b.readUInt32BE(20) };
  } finally { fs.closeSync(fd); }
}

export const num = (x, casas = 3) => {
  const s = Number(x).toFixed(casas).replace(/\.?0+$/, '');
  return s === '' || s === '-0' ? '0' : s;
};

export function fpsRacional(valor) {
  if (typeof valor === 'number') {
    for (const n of [24000, 30000, 48000, 60000, 120000]) if (Math.abs(valor - n / 1001) < 0.01) return { num: n, den: 1001 };
    if (Number.isInteger(valor)) return { num: valor, den: 1 };
    return { num: Math.round(valor * 1000), den: 1000 };
  }
  const m = /^\s*(\d+)\s*(?:\/\s*(\d+))?\s*$/.exec(String(valor));
  if (!m) {
    const f = parseFloat(valor);
    if (Number.isFinite(f)) return fpsRacional(f);
    throw new MotorErro(`fps ${JSON.stringify(valor)} inválido; use "30000/1001", "25", "60"…`, { codigo: 64 });
  }
  const r = { num: parseInt(m[1], 10), den: parseInt(m[2] || '1', 10) };
  if (!r.den || !r.num) throw new MotorErro(`fps ${valor} inválido (precisa ser maior que zero); use "30000/1001", "25", "60"…`, { codigo: 64 });
  return r;
}

export function mkdirp(p) { fs.mkdirSync(p, { recursive: true }); }

export function tamanhoMB(arquivo) { return (fs.statSync(arquivo).size / 1048576).toFixed(2); }
