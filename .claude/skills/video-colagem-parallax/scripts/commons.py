#!/usr/bin/env python3
"""Imagens de licença livre do Wikimedia Commons, com o crédito anotado.

uso (da raiz do projeto):
  audio/.venv/bin/python tools/commons.py buscar "Leontopithecus rosalia" [--n 16]
      → lista numerada + folha de contato em previews/commons.jpg (abra a imagem pra escolher)
  audio/.venv/bin/python tools/commons.py baixar 3 videos/<nome>/img/mico.jpg [--largura 1920]
      → baixa o item 3 da última busca (ou passe o título "File:....jpg") e grava img/creditos.json
  audio/.venv/bin/python tools/commons.py creditos videos/<nome>/img
      → linha de créditos pronta pro rodapé do vídeo

Só aceita CC0, domínio público, CC BY e CC BY-SA. BY e BY-SA EXIGEM o crédito no vídeo.
"""
import argparse, html, io, json, os, re, sys, urllib.parse, urllib.request

API = 'https://commons.wikimedia.org/w/api.php'
UA = 'video-colagem-parallax/1.0 (skill de video; https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia)'
CACHE = os.path.join('previews', 'commons-ultima.json')

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read()

def api(**p):
    p.update(action='query', format='json', formatversion=2)
    return json.loads(get(API + '?' + urllib.parse.urlencode(p)))

def limpa(s): return html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()

def licenca(meta):
    nome = limpa(meta.get('LicenseShortName', {}).get('value', ''))
    n = nome.lower()
    if re.search(r'\b(nc|nd)\b', n): return nome, None
    if n.startswith('cc0') or 'public domain' in n or n.startswith('pd') or 'no restrictions' in n: return nome, 'livre'
    if re.match(r'cc[ -]by(-sa)?\b', n): return nome, 'atribuir'
    return nome, None

def info(page):
    ii = (page.get('imageinfo') or [{}])[0]; meta = ii.get('extmetadata', {})
    nome, tipo = licenca(meta)
    return {'title': page['title'], 'license': nome, 'tipo': tipo,
            'artist': limpa(meta.get('Artist', {}).get('value', ''))[:120] or 'desconhecido',
            'w': ii.get('width'), 'h': ii.get('height'), 'mime': ii.get('mime'),
            'thumb': ii.get('thumburl') or ii.get('url'), 'page': ii.get('descriptionurl')}

def buscar(a):
    d = api(generator='search', gsrsearch=a.termo, gsrnamespace=6, gsrlimit=min(50, a.n * 3),
            prop='imageinfo', iiprop='url|extmetadata|size|mime', iiurlwidth=330)
    pages = sorted(d.get('query', {}).get('pages', []), key=lambda p: p.get('index', 0))
    res = [r for r in map(info, pages) if r['tipo'] and (r['mime'] or '').startswith('image/')][:a.n]
    if not res: sys.exit('nada com licença livre — tente o nome científico, termos em inglês ou "engraving"/"illustration"')
    os.makedirs('previews', exist_ok=True); json.dump(res, open(CACHE, 'w'), ensure_ascii=False, indent=1)
    for i, r in enumerate(res, 1):
        print(f"{i:2d}. {r['title'][5:][:70]:70s} {r['w']}×{r['h']}  {r['license']}{' (atribuir)' if r['tipo'] == 'atribuir' else ''}")
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return print('(sem Pillow: pulei a folha de contato)')
    cols, cw, ch = 4, 330, 300; rows = -(-len(res) // cols)
    sheet = Image.new('RGB', (cols * cw, rows * (ch + 34)), '#222'); dr = ImageDraw.Draw(sheet)
    try: fnt = ImageFont.load_default(size=20)
    except TypeError: fnt = ImageFont.load_default()
    for i, r in enumerate(res):
        x, y = (i % cols) * cw, (i // cols) * (ch + 34)
        try:
            im = Image.open(io.BytesIO(get(r['thumb']))).convert('RGB'); im.thumbnail((cw - 6, ch - 6))
            sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        except Exception as e: dr.text((x + 10, y + 10), f'erro: {e}'[:40], fill='#f66', font=fnt)
        dr.text((x + 8, y + ch + 6), f"{i + 1}. {r['license'][:26]}", fill='#fff', font=fnt)
    out = a.folha or os.path.join('previews', 'commons.jpg'); sheet.save(out, quality=88)
    print('folha de contato:', out)

def baixar(a):
    if a.item.isdigit():
        res = json.load(open(CACHE)); title = res[int(a.item) - 1]['title']
    else:
        title = a.item if a.item.startswith('File:') else 'File:' + a.item
    d = api(titles=title, prop='imageinfo', iiprop='url|extmetadata|size|mime', iiurlwidth=a.largura)
    r = info(d['query']['pages'][0])
    if not r['tipo']: sys.exit(f"licença não aceita: {r['license']}")
    url = r['thumb'] if (r['w'] or 0) > a.largura or not (r['mime'] or '').endswith(('jpeg', 'png')) else get_url_original(d)
    data = get(url); os.makedirs(os.path.dirname(os.path.abspath(a.destino)), exist_ok=True)
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)); im = im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') and a.destino.endswith('.png') else 'RGB')
        im.save(a.destino, quality=92) if a.destino.lower().endswith(('.jpg', '.jpeg')) else im.save(a.destino)
        tam = f'{im.width}×{im.height}'
    except ImportError:
        open(a.destino, 'wb').write(data); tam = '?'
    cj = os.path.join(os.path.dirname(a.destino) or '.', 'creditos.json')
    cred = json.load(open(cj)) if os.path.exists(cj) else []
    cred = [c for c in cred if c['file'] != os.path.basename(a.destino)]
    cred.append({'file': os.path.basename(a.destino), 'title': r['title'], 'license': r['license'], 'artist': r['artist'], 'page': r['page']})
    json.dump(cred, open(cj, 'w'), ensure_ascii=False, indent=1)
    print(f"{a.destino} {tam} · {r['license']} · {r['artist']}" + ('  → precisa de crédito no vídeo' if r['tipo'] == 'atribuir' else ''))

def get_url_original(d):
    return d['query']['pages'][0]['imageinfo'][0]['url']

def creditos(a):
    cred = json.load(open(os.path.join(a.pasta, 'creditos.json')))
    def lic(l): return 'domínio público' if 'public domain' in l.lower() or l.lower().startswith('pd') else l
    vistos, partes = set(), []
    for c in cred:
        k = (c['artist'], lic(c['license']))
        if k not in vistos: vistos.add(k); partes.append(f'{k[0]} ({k[1]})')
    print('Imagens via Wikimedia Commons: ' + ' · '.join(partes))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    b = sp.add_parser('buscar'); b.add_argument('termo'); b.add_argument('--n', type=int, default=16); b.add_argument('--folha')
    d = sp.add_parser('baixar'); d.add_argument('item'); d.add_argument('destino'); d.add_argument('--largura', type=int, default=1920)
    c = sp.add_parser('creditos'); c.add_argument('pasta')
    a = ap.parse_args(); {'buscar': buscar, 'baixar': baixar, 'creditos': creditos}[a.cmd](a)
