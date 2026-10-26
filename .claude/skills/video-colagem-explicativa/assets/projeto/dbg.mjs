// uso: node dbg.mjs <video> <t> "<expressão JS>"   — inspeciona o estado do vídeo num instante
import { chromium } from 'playwright';
import http from 'http'; import { readFileSync, existsSync, statSync } from 'fs'; import path from 'path';
const [name, t, expr] = process.argv.slice(2); const ROOT = process.cwd();
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2' };
const s = http.createServer((q, r) => { const p = path.join(ROOT, decodeURIComponent(q.url.split('?')[0])); if (!existsSync(p) || statSync(p).isDirectory()) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' }); r.end(readFileSync(p)); });
await new Promise(r => s.listen(0, r));
const b = await chromium.launch({ args: [...(process.platform === 'darwin' ? ['--use-angle=metal'] : []), '--enable-gpu', '--ignore-gpu-blocklist'] });
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } }); p.on('pageerror', e => console.log('ERRO:', e.message));
await p.addInitScript(() => { window.__render = true; });
const dir = readFileSync('videos/' + name + '/index.html') ? name : name;
await p.goto(`http://127.0.0.1:${s.address().port}/videos/${dir}/index.html`); await p.waitForFunction(() => window.__ready);
await p.evaluate(t => window.__seek(+t), t);
console.log(JSON.stringify(await p.evaluate(e => eval(e), expr), null, 1));
await b.close(); s.close();
