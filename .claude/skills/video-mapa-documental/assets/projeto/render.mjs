// uso: node render.mjs [prefixos...] [--preview[=N]] [--at=t1,t2] [--fps=N] [--conc=N]
import { chromium } from 'playwright';
import { spawn } from 'child_process';
import http from 'http';
import { readdirSync, readFileSync, writeFileSync, mkdirSync, existsSync, statSync, rmSync } from 'fs';
import path from 'path';

const ROOT = process.cwd();
mkdirSync('out', { recursive: true }); mkdirSync('previews', { recursive: true });
const argv = process.argv.slice(2), flag = k => { const a = argv.find(x => x === '--' + k || x.startsWith('--' + k + '=')); return a === undefined ? undefined : (a.includes('=') ? a.split('=')[1] : true); };
const pre = argv.filter(a => !a.startsWith('--'));
const all = readdirSync('videos').filter(d => existsSync(`videos/${d}/index.html`)).sort();
const names = pre.length ? all.filter(n => pre.some(p => n.startsWith(p))) : all;
const CONC = +(flag('conc') ?? 4), PREVIEW = flag('preview'), AT = flag('at'), FPSO = flag('fps');

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.wav': 'audio/wav', '.webp': 'image/webp', '.geojson': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !existsSync(p) || statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream', 'Cache-Control': 'max-age=3600' }); res.end(readFileSync(p));
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ args: [...(process.platform === 'darwin' ? ['--use-angle=metal'] : []), '--enable-gpu', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', '--font-render-hinting=none', '--force-color-profile=srgb'] });

const DIMS = { '16x9': [1920, 1080], '1x1': [1080, 1080], '9x16': [1080, 1920], '4x5': [1080, 1350] };
function formatsOf(name) { const m = readFileSync(`videos/${name}/index.html`, 'utf8').match(/<meta name="formats" content="([^"]+)"/); return m ? m[1].split(',') : [null]; }
async function one(name, fmt) {
  const t0 = Date.now();
  const meta0 = readFileSync(`videos/${name}/index.html`, 'utf8').match(/VIDEO\s*=\s*(\{[^<]*?\})\s*<\/script>/);
  let V0 = {}; try { V0 = meta0 ? Function('return ' + meta0[1])() : {}; } catch (e) {}
  const [w, h] = fmt ? DIMS[fmt] : [V0.w || 1920, V0.h || 1080];
  const tag = fmt ? `${name}-${fmt}` : name;
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errs = new Set(); page.on('pageerror', e => errs.add(e.message)); page.on('console', m => { if (m.type() === 'error') errs.add(m.text()); });
  await page.addInitScript(() => { window.__render = true; });
  await page.goto(`${BASE}/videos/${name}/index.html${fmt ? '?fmt=' + fmt : ''}`);
  try { await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }); } catch (e) { console.log(name, 'NÃO INICIOU', [...errs].join(' | ')); await ctx.close(); return; }
  const V = await page.evaluate(() => ({ ...window.VIDEO, cues: window.__cues }));
  writeFileSync(`videos/${name}/cues.json`, JSON.stringify({ dur: V.dur, bpm: V.bpm, fps: V.fps, music: V.music || null, cues: V.cues }, null, 1));
  const fps = +(FPSO || V.fps);
  const shot = async t => { await page.evaluate(t => window.__seek(t), t); return page.screenshot({ type: 'jpeg', quality: 93, caret: 'hide' }); };
  if (PREVIEW || AT) {
    const n = PREVIEW === true ? 12 : +PREVIEW || 12;
    const times = AT ? String(AT).split(',').map(Number) : Array.from({ length: n }, (_, i) => +(V.dur * (i + 0.5) / n).toFixed(3));
    const dir = `previews/${tag}`; rmSync(dir, { recursive: true, force: true }); mkdirSync(dir, { recursive: true });
    for (const [i, t] of times.entries()) writeFileSync(`${dir}/${String(i).padStart(2, '0')}.jpg`, await shot(t));
    const cols = times.length <= 4 ? times.length : times.length <= 9 ? 3 : 4, rows = Math.ceil(times.length / cols), tw = 640, th = Math.round(tw * h / w);
    await run('ffmpeg', ['-y', '-loglevel', 'error', '-framerate', '1', '-i', `${dir}/%02d.jpg`, '-vf', `scale=${tw}:${th},tile=${cols}x${rows}:padding=4:color=gray`, '-frames:v', '1', `previews/${tag}.jpg`]);
    console.log(tag, 'preview', times.join(','), errs.size ? 'ERROS: ' + [...errs].join(' | ') : 'ok', ((Date.now() - t0) / 1000).toFixed(1) + 's');
    await ctx.close(); return;
  }
  const N = Math.round(V.dur * fps), tmp = `out/${tag}.video.mp4`;
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-', ...(process.platform === 'darwin' ? ['-c:v', 'h264_videotoolbox', '-b:v', (fps >= 50 ? 28 : fps >= 30 ? 20 : 16) + 'M', '-maxrate', (fps >= 50 ? 40 : 28) + 'M', '-bufsize', '60M'] : ['-c:v', 'libx264', '-preset', 'medium', '-crf', '15']), '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < N; i++) { const b = await shot(i / fps); if (!ff.stdin.write(b)) await new Promise(r => ff.stdin.once('drain', r)); }
  ff.stdin.end(); await new Promise(r => ff.on('close', r));
  const wav = `audio/${name}.wav`;
  if (existsSync(wav)) await run('ffmpeg', ['-y', '-loglevel', 'error', '-i', tmp, '-i', wav, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', `out/${tag}.mp4`]), rmSync(tmp);
  else await run('mv', [tmp, `out/${tag}.mp4`]);
  console.log(tag, `${N} quadros @${fps}fps`, existsSync(wav) ? '+ áudio' : '(sem áudio)', errs.size ? 'ERROS: ' + [...errs].join(' | ') : '', ((Date.now() - t0) / 1000).toFixed(0) + 's');
  await ctx.close();
}
function run(cmd, args) { return new Promise((res, rej) => { const p = spawn(cmd, args, { stdio: 'inherit' }); p.on('close', c => c ? rej(new Error(cmd + ' ' + c)) : res()); }); }
const FMT = flag('fmt');
const q = names.flatMap(n => { const f = formatsOf(n); const sel = FMT ? f.filter(x => x === FMT) : (PREVIEW || AT ? [f[0]] : f); return sel.map(x => [n, x]); });
await Promise.all(Array.from({ length: Math.min(CONC, q.length) }, async () => { while (q.length) await one(...q.shift()); }));
await browser.close(); server.close();
