#!/usr/bin/env python3
"""NBA GM Survey Tracker — per-page share images (1200x630 JPEG).

Run AFTER scripts/build_site_data.py and BEFORE scripts/generate_entity_pages.py
(the page generator only adds og:image tags for images that exist).

    pip install pillow
    python scripts/generate_og_images.py                 # faces fetched from the nba-headshots site
    python scripts/generate_og_images.py --faces DIR     # or from a local nba-headshots clone

Writes docs/og/<folder>/<slug>.jpg plus docs/og/hashes.json. Incremental: a
card is redrawn only when the data it shows (or the design version) changes,
so a new survey season rewrites the cards that actually moved, not all 1,200.
The GitHub Action in .github/workflows/rebuild.yml runs this for you.
"""
import argparse, collections, hashlib, io, json, os, random, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qlabels import short_label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')
OUT = os.path.join(ROOT, 'docs', 'og')
ASSETS = os.path.join(ROOT, 'scripts', 'og_assets')
FACES_URL = 'https://jsierrahoopshype.github.io/nba-headshots/'

DESIGN_VERSION = 3     # bump to force every card to redraw after a design change

W, H = 1200, 630
# Trade Card palette (jsierrahoopshype.github.io/nba-trade-card)
BG_TOP, BG_BOT = (13, 10, 34), (36, 31, 77)          # #0d0a22 -> #241f4d
BRAND_A, BRAND_B = (139, 124, 255), (255, 92, 168)   # #8B7CFF -> #FF5CA8
WHITE = (255, 255, 255)
PANEL_FALLBACK = (58, 63, 92)                        # #3a3f5c

def wa(alpha):
    """white at an opacity, as an RGBA tuple"""
    return (255, 255, 255, int(255 * alpha))

# ---------------------------------------------------------------- fonts

_font_cache = {}
_POPPINS = {500: 'Medium', 600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold'}
def font(size, weight=700):
    key = (size, weight)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(
            os.path.join(ASSETS, 'fonts', f'Poppins-{_POPPINS[weight]}.ttf'), size)
    return _font_cache[key]

def text_w(f, s):
    return f.getlength(s)

def wrap(s, f, maxw, max_lines):
    """Greedy word wrap. Returns lines or None if it needs more than max_lines."""
    words, lines, cur = s.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if text_w(f, t) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    if any(text_w(f, ln) > maxw for ln in lines):     # one word wider than the column
        return None
    return lines if len(lines) <= max_lines else None

def ellipsize(s, f, maxw):
    if text_w(f, s) <= maxw:
        return s
    while s and text_w(f, s + '…') > maxw:
        s = s[:-1]
    return s.rstrip(' ,') + '…'

# ---------------------------------------------------------------- images

class Faces:
    """nba id -> face image, from a local nba-headshots clone or its Pages site."""
    def __init__(self, local):
        self.local = local
        self.cache = {}
        if local:
            folder = os.path.join(local, 'players', 'headshots', 'face2')
            names = os.listdir(folder) if os.path.isdir(folder) else []
        else:
            try:
                meta = json.load(urllib.request.urlopen(FACES_URL + 'players/metadata/players_all.json', timeout=60))
                rows = meta['players'] if isinstance(meta, dict) and 'players' in meta else meta
                names = [p['headshot']['filename'] for p in rows
                         if isinstance(p, dict) and p.get('headshot', {}).get('filename')]
            except Exception as e:
                print('WARNING: could not load headshot index, cards will use logos:', e)
                names = []
        self.files = {}
        for n in names:
            head = n.split('-', 1)[0]
            if head.isdigit():
                self.files[int(head)] = n

    def has(self, pid):
        return pid in self.files

    def get(self, pid):
        if pid in self.cache:
            return self.cache[pid]
        img = None
        name = self.files.get(pid)
        if name:
            try:
                if self.local:
                    img = Image.open(os.path.join(self.local, 'players', 'headshots', 'face2', name))
                else:
                    raw = urllib.request.urlopen(FACES_URL + 'players/headshots/face2/' + name, timeout=60).read()
                    img = Image.open(io.BytesIO(raw))
                img = img.convert('RGB')
            except Exception as e:
                print('  face fetch failed', pid, e)
                img = None
        self.cache[pid] = img
        return img

def logo(abbr):
    p = os.path.join(ASSETS, 'logos', f'{abbr}.png')
    return Image.open(p).convert('RGBA') if os.path.exists(p) else None

def visual_ok(vis, faces):
    if not vis:
        return False
    if vis[0] == 'face':
        return faces.has(vis[1])
    return os.path.exists(os.path.join(ASSETS, 'logos', f'{vis[1]}.png'))

# ---------------------------------------------------------------- drawing helpers

SS = 3   # supersampling for anti-aliased masks

def rr_mask(w, h, r):
    big = Image.new('L', (w * SS, h * SS), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=255)
    return big.resize((w, h), Image.LANCZOS)

def circle_mask(d):
    big = Image.new('L', (d * SS, d * SS), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * SS - 1, d * SS - 1), fill=255)
    return big.resize((d, d), Image.LANCZOS)

def brand_gradient(w, h):
    """horizontal BRAND_A -> BRAND_B strip, RGBA"""
    row = Image.new('RGBA', (w, 1))
    px = row.load()
    for x in range(w):
        t = x / max(1, w - 1)
        px[x, 0] = tuple(int(BRAND_A[i] + (BRAND_B[i] - BRAND_A[i]) * t) for i in range(3)) + (255,)
    return row.resize((w, h))

def overlay(im, layer, xy=(0, 0), mask=None):
    """alpha-composite an RGBA layer onto the RGBA canvas at xy (layer keeps its own alpha;
    an optional mask scales it further)"""
    if mask is not None:
        layer = layer.copy()
        layer.putalpha(Image.composite(layer.getchannel('A'), Image.new('L', layer.size, 0), mask))
    tmp = Image.new('RGBA', im.size, (0, 0, 0, 0))
    tmp.paste(layer, xy)          # straight copy: no mask, so alpha is not applied twice
    im.alpha_composite(tmp)

def fill_shape(im, box, mask, color):
    """paint an RGBA color (or a gradient image) through a mask at box (x, y)"""
    w, h = mask.size
    layer = color if isinstance(color, Image.Image) else Image.new('RGBA', (w, h), color)
    if layer.mode != 'RGBA':
        layer = layer.convert('RGBA')
    layer = layer.copy()
    # mask blends the layer's own alpha down to 0 outside the shape
    layer.putalpha(Image.composite(layer.getchannel('A'), Image.new('L', (w, h), 0), mask))
    overlay(im, layer, (int(box[0]), int(box[1])))

def stroke_rr(im, x, y, w, h, r, color, width=2):
    layer = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS,
                                            outline=color, width=width * SS)
    overlay(im, layer.resize((w, h), Image.LANCZOS), (int(x), int(y)))

def glow(im, cx, cy, radius, color, alpha):
    """soft radial glow (like the Trade Card's pink glow behind the hero)"""
    size = radius * 2
    g = Image.new('L', (size, size), 0)
    px = g.load()
    for yy in range(size):
        for xx in range(size):
            dd = ((xx - radius) ** 2 + (yy - radius) ** 2) ** 0.5 / radius
            if dd < 1:
                px[xx, yy] = int(255 * alpha * (1 - dd) ** 1.6)
    layer = Image.new('RGBA', (size, size), color + (0,))
    layer.putalpha(g)
    overlay(im, layer, (cx - radius, cy - radius))

def gradient_text(im, xy, text, f, anchor='la'):
    """text filled with the brand gradient"""
    l, t, r, b = ImageDraw.Draw(im).textbbox(xy, text, font=f, anchor=anchor)
    w, h = int(r - l) + 2, int(b - t) + 2
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).text((xy[0] - l, xy[1] - t), text, font=f, fill=255, anchor=anchor)
    fill_shape(im, (l, t), m, brand_gradient(w, h))

_bg_cache = {}
def background():
    if 'bg' not in _bg_cache:
        im = Image.new('RGBA', (W, H))
        px = im.load()
        for y in range(H):
            t = y / (H - 1)
            c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)) + (255,)
            for x in range(W):
                px[x, y] = c
        # faint grain, fixed seed so a card's bytes don't change between runs
        rnd = random.Random(7)
        grain = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(grain)
        for _ in range(900):
            x, y = rnd.randrange(W), rnd.randrange(H)
            d.rectangle((x, y, x + 1, y + 1), fill=(255, 255, 255, 8) if rnd.random() > 0.5 else (0, 0, 0, 8))
        im.alpha_composite(grain)
        _bg_cache['bg'] = im
    return _bg_cache['bg'].copy()

def face_crop(img, w, h):
    """cover-crop a face2 photo into w x h. face2 crops can carry a dark band at the
    bottom, so work from a top-anchored 1/1.2 window (same overscan the comparison
    video generator uses)."""
    s = min(img.size)
    win = int(s / 1.2)
    x0 = (img.size[0] - win) // 2
    src = img.crop((x0, 0, x0 + win, win))
    scale = max(w / src.size[0], h / src.size[1])
    src = src.resize((int(src.size[0] * scale + 0.5), int(src.size[1] * scale + 0.5)), Image.LANCZOS)
    ox = (src.size[0] - w) // 2
    return src.crop((ox, 0, ox + w, h)).convert('RGBA')

def hero_panel(im, vis, x, y, w, h, faces, radius=28):
    """Trade Card hero: rounded photo panel, darkening at the bottom, gradient bar,
    thin white edge. Logos sit on a white panel instead."""
    mask = rr_mask(w, h, radius)
    if vis[0] == 'face':
        img = faces.get(vis[1])
        tile = face_crop(img, w, h) if img else Image.new('RGBA', (w, h), PANEL_FALLBACK + (255,))
        shade = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        for yy in range(int(h * 0.62), h):
            a = int(0.55 * 255 * (yy - h * 0.62) / (h * 0.38))
            sd.line((0, yy, w, yy), fill=(13, 10, 34, a))
        tile.alpha_composite(shade)
    else:
        # logos: white circular badge (Trade Card's drawContainBadge) on a glass panel
        tile = Image.new('RGBA', (w, h), (255, 255, 255, 28))
        dd = int(min(w, h) * 0.80)
        disc = Image.new('RGBA', (dd, dd), (255, 255, 255, 255))
        disc.putalpha(circle_mask(dd))
        tile.alpha_composite(disc, ((w - dd) // 2, (h - dd) // 2 - 4))
        lg = logo(vis[1])
        if lg:
            inner = int(dd * 0.70)
            lg.thumbnail((inner, inner), Image.LANCZOS)
            tile.alpha_composite(lg, ((w - lg.size[0]) // 2, (h - lg.size[1]) // 2 - 4))
    tile.putalpha(Image.composite(tile.getchannel('A'), Image.new('L', (w, h), 0), mask))
    overlay(im, tile, (x, y))
    bar_h = max(6, h // 42)
    fill_shape(im, (x, y + h - bar_h), rr_mask(w, bar_h, bar_h // 2), brand_gradient(w, bar_h))
    stroke_rr(im, x, y, w, h, radius, wa(0.22), 2)

def mini_visual(im, vis, cx, cy, d, faces):
    """small round picture for detail lines: face (cover) or logo on a white disc"""
    m = circle_mask(d)
    if vis[0] == 'face':
        img = faces.get(vis[1])
        if not img:
            return
        tile = face_crop(img, d, d)
    else:
        tile = Image.new('RGBA', (d, d), (255, 255, 255, 255))
        lg = logo(vis[1])
        if lg:
            inner = int(d * 0.72)
            lg.thumbnail((inner, inner), Image.LANCZOS)
            tile.alpha_composite(lg, ((d - lg.size[0]) // 2, (d - lg.size[1]) // 2))
    tile.putalpha(Image.composite(tile.getchannel('A'), Image.new('L', (d, d), 0), m))
    overlay(im, tile, (cx - d // 2, cy - d // 2))
    ring = Image.new('RGBA', (d * SS, d * SS), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, d * SS - 1, d * SS - 1), outline=BRAND_B + (150,), width=2 * SS)
    overlay(im, ring.resize((d, d), Image.LANCZOS), (cx - d // 2, cy - d // 2))

# ---------------------------------------------------------------- card renderer

def render(spec, faces):
    """spec: title, subtitle, tiles [(num, label)], lines [(text, vis|None)], visual, badge, collage"""
    im = background()
    # Text and other translucent strokes go on a transparent top layer that is
    # blended in at the end: drawing a translucent color straight onto the RGBA
    # canvas would overwrite its pixels instead of blending them.
    top = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(top)

    # footer: thin pink rule, dot + tracker name, site address
    fy = H - 58
    d.line((64, fy - 22, W - 64, fy - 22), fill=BRAND_B + (90,), width=2)
    d.ellipse((64, fy - 6, 76, fy + 6), fill=BRAND_B + (255,))
    d.text((88, fy), 'NBA GM SURVEY TRACKER', font=font(20, 800), fill=wa(0.75), anchor='lm')
    d.text((W - 64, fy), 'hoopsmatic.com/nba-gm-survey', font=font(19, 600), fill=wa(0.45), anchor='rm')

    main_top, main_bot = 40, fy - 44
    vis = spec.get('visual') if visual_ok(spec.get('visual'), faces) else None
    collage = [v for v in spec.get('collage', []) if visual_ok(v, faces)][:4]
    has_right = bool(vis) or len(collage) >= 2
    left, right = 64, (724 if has_right else W - 64)
    maxw = right - left

    # right side: hero panel (+ gradient pill badge) or a 2x2 collage
    if vis:
        badge = spec.get('badge')
        pw, ph = 340, (380 if badge else 432)
        px_, py_ = 1136 - pw, main_top + (8 if badge else 0)
        glow(im, px_ + pw // 2, py_ + int(ph * 0.45), 300, BRAND_B, 0.30)
        hero_panel(im, vis, px_, py_, pw, ph, faces)
        if badge:
            bf = font(28, 800)
            bw = int(text_w(bf, badge)) + 56
            bh = 56
            bx, by = px_ + (pw - bw) // 2, py_ + ph + 16
            fill_shape(im, (bx, by), rr_mask(bw, bh, bh // 2), brand_gradient(bw, bh))
            d.text((bx + bw / 2, by + bh / 2 + 1), badge, font=bf, fill=WHITE, anchor='mm')
    elif len(collage) >= 2:
        glow(im, 966, 260, 300, BRAND_B, 0.26)
        cs, gap = 164, 16
        for i, v in enumerate(collage):
            cx = 1136 - 2 * cs - gap + (i % 2) * (cs + gap)
            cy = main_top + 32 + (i // 2) * (cs + gap)
            hero_panel(im, v, cx, cy, cs, cs, faces, radius=20)

    # left block: measure, then center vertically
    title = spec['title']
    for size in (72, 64, 58, 52, 46, 42, 38, 34):
        tf = font(size, 800)
        lines = wrap(title, tf, maxw, 3)
        if lines:
            break
    else:
        tf = font(34, 800)
        lines = (wrap(title, tf, maxw, 99) or [title])[:3]
        lines[-1] = ellipsize(lines[-1] + ' …', tf, maxw)
    lh = int(tf.size * 1.14)
    blocks = [('title', lines, lh)]
    if spec.get('subtitle'):
        blocks.append(('sub', spec['subtitle'], 40))
    tiles = spec.get('tiles', [])[:3]
    if tiles:
        blocks.append(('tiles', tiles, 104))
    for t, v in spec.get('lines', [])[:3]:
        blocks.append(('line', (t, v if visual_ok(v, faces) else None), 54))
    gaps = {'title': 18, 'sub': 24, 'tiles': 16, 'line': 4}
    def height(bl):
        return sum(len(b[1]) * b[2] if b[0] == 'title' else b[2] for b in bl) + \
            sum(gaps[b[0]] for b in bl[:-1])
    while height(blocks) > main_bot - main_top and blocks[-1][0] == 'line':
        blocks.pop()                     # never let detail lines run into the footer
    y = main_top + max(0, (main_bot - main_top - height(blocks)) // 2)

    for kind, payload, bh in blocks:
        if kind == 'title':
            for ln in payload:
                d.text((left, y), ln, font=tf, fill=WHITE)
                y += bh
        elif kind == 'sub':
            sf = font(26, 600)
            d.text((left, y), ellipsize(payload, sf, maxw), font=sf, fill=wa(0.62))
            y += bh
        elif kind == 'tiles':
            n = len(payload)
            tw = int((maxw - 14 * (n - 1)) / n)
            th = bh - 8
            for i, (num, lab) in enumerate(payload):
                x0 = int(left + i * (tw + 14))
                fill_shape(im, (x0, y), rr_mask(tw, th, 18), wa(0.045))
                stroke_rr(im, x0, y, tw, th, 18, BRAND_A + (128,), 2)
                nf = font(42, 800)
                for fs in (42, 36, 30, 26):          # shrink long values to fit the tile
                    nf = font(fs, 800)
                    if text_w(nf, str(num)) <= tw - 36:
                        break
                gradient_text(im, (x0 + 20, y + 10), str(num), nf)
                lf = font(18, 600)
                d.text((x0 + 20, y + 64), ellipsize(lab.upper(), lf, tw - 32), font=lf, fill=wa(0.55))
            y += bh
        else:
            txt, v = payload
            lf = font(24, 600)
            x = left
            if v:
                mini_visual(im, v, left + 21, y + 25, 42, faces)
                x = left + 58
            else:
                d.ellipse((left, y + 20, left + 10, y + 30), fill=BRAND_B + (255,))
                x = left + 24
            d.text((x, y + 25), ellipsize(txt, lf, right - x), font=lf, fill=wa(0.88), anchor='lm')
            y += bh
        y += gaps[kind]
    im.alpha_composite(top)
    return im.convert('RGB')


# ---------------------------------------------------------------- specs from site data

def pct(p):
    if p is None:
        return ''
    return f'{p:.0f}%' if abs(p - round(p)) < 0.05 else f'{p:.1f}%'

def plural(n, one, many=None):
    return f'{n} {one if n == 1 else (many or one + "s")}'

def build_specs(faces):
    ix = json.load(open(os.path.join(DATA, 'entities.json'), encoding='utf-8'))
    ents = ix['entities']
    slugmap = json.load(open(os.path.join(DATA, 'slugmap.json'), encoding='utf-8'))
    ent_kind = slugmap['entKind']
    by_key = {}
    for kind in ('players', 'coaches', 'teams'):
        for e in ents[kind]:
            by_key[e['k']] = e

    def load_e(k):
        return json.load(open(os.path.join(DATA, 'e', k + '.json'), encoding='utf-8'))

    team_of_entity = {}            # most-voted-for team per person, for logo fallbacks
    def main_team(rows):
        c = collections.Counter(r['teamAbbr'] for r in rows if r.get('teamAbbr'))
        return c.most_common(1)[0][0] if c else None

    def vis_for(k):
        """Best picture for an entity key: face, else main team logo."""
        if not k:
            return None
        e = by_key.get(k)
        if k.startswith('t-'):
            return ('logo', k[2:])
        if e and e.get('nbaId') and faces.has(e['nbaId']):
            return ('face', e['nbaId'])
        t = team_of_entity.get(k)
        return ('logo', t) if t else None

    details = {}
    for k in by_key:
        dd = load_e(k)
        details[k] = dd
        if not k.startswith('t-'):
            t = main_team(dd['rows'])
            if t:
                team_of_entity[k] = t

    specs = {}
    seasons = ix['seasons']
    first, latest = seasons[0], seasons[-1]
    top_players = sorted(ents['players'], key=lambda e: (-e['wins'], -e['mentions']))
    player_collage = [('face', e['nbaId']) for e in top_players
                      if e.get('nbaId') and faces.has(e['nbaId'])][:8]
    top_teams = sorted(ents['teams'], key=lambda e: (-e['wins'], -e['mentions']))
    base_tiles = [(len(seasons), 'surveys'), (len(ix['questions']), 'questions'),
                  (len(ents['players']), 'players named')]

    specs['home'] = {'title': f'Every NBA GM Survey answer since {first}',
                     'tiles': base_tiles, 'collage': player_collage}
    specs['seasons'] = {'title': f'All {len(seasons)} NBA GM Surveys, {first} to {latest}',
                        'tiles': base_tiles, 'collage': player_collage}
    specs['questions'] = {'title': f'All {len(ix["questions"])} NBA GM Survey questions',
                          'tiles': base_tiles, 'collage': player_collage}
    specs['players'] = {'title': 'Every player NBA GMs have voted for',
                        'tiles': [(len(ents['players']), 'players named'),
                                  (top_players[0]['wins'], 'top player No. 1s'),
                                  (len(seasons), 'surveys')],
                        'collage': player_collage}
    specs['teams'] = {'title': 'Every NBA team in the GM Survey',
                      'tiles': [(len(ents['teams']), 'franchises'), (len(seasons), 'surveys'),
                                (len(ix['questions']), 'questions')],
                      'collage': [('logo', e['abbr']) for e in top_teams][:8]}
    top_coaches = sorted(ents['coaches'], key=lambda e: (-e['wins'], -e['mentions']))
    specs['coaches'] = {'title': 'Every coach NBA GMs have voted for',
                        'tiles': [(len(ents['coaches']), 'coaches named'),
                                  (top_coaches[0]['wins'], 'top coach No. 1s'),
                                  (len(seasons), 'surveys')],
                        'collage': [v for v in (vis_for(e['k']) for e in top_coaches) if v][:8]}

    # seasons
    for card in ix['seasonCards']:
        s = card['season']
        sq = json.load(open(os.path.join(DATA, 's', s + '.json'), encoding='utf-8'))['questions']
        n_ans = sum(len(q['answers']) for q in sq)
        lines = []
        for m in card['marquee'][:3]:
            lab = m['label'] if len(m['label']) < 30 else 'Top pick'
            lines.append((f'{lab}: {m["name"]} ({pct(m["pct"])})', vis_for(m.get('e'))))
        big = next((vis_for(m.get('e')) for m in card['marquee'] if m.get('e')), None)
        specs[f'seasons/{s}'] = {'title': f'{s} NBA GM Survey results',
                                 'tiles': [(card['nQ'], 'questions'), (n_ans, 'answers')],
                                 'lines': lines, 'visual': big}

    # questions
    for q in ix['questions']:
        qd = json.load(open(os.path.join(DATA, 'q', q['slug'] + '.json'), encoding='utf-8'))
        last = qd['seasons'][-1]
        tops = [a for a in last['answers'] if a['rank'] == 1]
        winners = set()
        for b in qd['seasons']:
            for a in b['answers']:
                if a['rank'] == 1:
                    winners.add(a['e'] or a['t'])
        lines = []
        top = tops[0] if tops else None
        if top:
            nm = by_key[top['e']]['name'] if top.get('e') in by_key else top['t']
            if len(tops) > 1:
                nm += f' (tied, {len(tops)} ways)'
            lines.append((f'{last["season"]} pick: {nm}', None))
        tw = q.get('topWinner')
        if tw and q['nSeasons'] > 1 and tw['wins'] >= 2:
            lines.append((f'Most No. 1s: {tw["t"]} ({tw["wins"]})', vis_for(tw.get('e'))))
        span = f'{q["first"]} to {q["last"]}' if q['nSeasons'] > 1 else q['first']
        tiles = [(q['nSeasons'], 'seasons asked' if q['nSeasons'] != 1 else 'season asked'),
                 (len(winners), 'different No. 1s' if len(winners) != 1 else 'No. 1 answer')]
        specs[f'questions/{q["slug"]}'] = {
            'title': q['text'], 'subtitle': f'NBA GM Survey, {span}', 'tiles': tiles, 'lines': lines,
            'visual': vis_for(top.get('e')) if top else None,
            'badge': f'{pct(top["pct"])} in {last["season"]}' if top and top.get('pct') else None}

    # people + teams
    for folder, kind in (('players', 'player'), ('coaches', 'coach'), ('teams', 'team')):
        for e in ents[folder]:
            k = e['k']
            dd = details[k]
            rows = dd['rows']
            if kind == 'team':
                mv = dd.get('memberVotes', [])
                c = collections.Counter(m['name'] for m in mv)
                lines = []
                if c:
                    nm, n = c.most_common(1)[0]
                    mk = next(m['e'] for m in mv if m['name'] == nm)
                    lines.append((f'Top vote-getter: {nm} ({plural(n, "vote")})', vis_for(mk)))
                tiles = [(e['wins'], 'team No. 1s'), (e['mentions'], 'times named'),
                         (len(mv), 'roster votes')]
                specs[f'teams/{e["slug"]}'] = {'title': e['name'], 'subtitle': 'in the NBA GM Survey',
                                               'tiles': tiles, 'lines': lines, 'visual': ('logo', k[2:])}
                continue
            wins = [r for r in rows if r['rank'] == 1 and r['rt'] == 'r']
            byq = collections.Counter(r['q'] for r in wins)
            lines = []
            if byq:
                qq, n = byq.most_common(1)[0]
                lines.append((f'Most No. 1s: {short_label(qq)} ({n})', None))
                tiles = [(len(wins), 'No. 1 finish' if len(wins) == 1 else 'No. 1 finishes'),
                         (len(byq), 'question led' if len(byq) == 1 else 'questions led'),
                         (e['mentions'], 'times named')]
            else:
                best = min(rows, key=lambda r: (r['rank'], -(r['pct'] or 0)))
                lines.append((f'Best finish: No. {best["rank"]}, {short_label(best["q"])} ({best["season"]})', None))
                n_seasons = len(set(r['season'] for r in rows))
                tiles = [(e['mentions'], 'time named' if e['mentions'] == 1 else 'times named'),
                         (e['nQ'], 'question' if e['nQ'] == 1 else 'questions'),
                         (n_seasons, 'season named' if n_seasons == 1 else 'seasons named')]
            span = f'{e["first"]} to {e["last"]}' if e['first'] != e['last'] else e['first']
            specs[f'{folder}/{e["slug"]}'] = {'title': e['name'], 'subtitle': f'in the NBA GM Survey, {span}',
                                              'tiles': tiles, 'lines': lines, 'visual': vis_for(k)}
    return specs

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--faces', help='local nba-headshots clone (default: fetch from its site)')
    ap.add_argument('--force', action='store_true', help='redraw every card')
    ap.add_argument('--only', help='comma-separated page keys to draw (testing)')
    args = ap.parse_args()

    faces = Faces(args.faces)
    specs = build_specs(faces)
    if args.only:
        keep = set(args.only.split(','))
        specs = {k: v for k, v in specs.items() if k in keep}

    hpath = os.path.join(OUT, 'hashes.json')
    hashes = json.load(open(hpath, encoding='utf-8')) if os.path.exists(hpath) else {}
    drawn = skipped = 0
    for key, spec in sorted(specs.items()):
        # hash what the card shows + whether its pictures are available
        vis_state = [visual_ok(spec.get('visual'), faces)] + \
            [visual_ok(v, faces) for _, v in spec.get('lines', [])] + \
            [visual_ok(v, faces) for v in spec.get('collage', [])]
        h = hashlib.sha1(json.dumps([DESIGN_VERSION, spec, vis_state], sort_keys=True,
                                    ensure_ascii=False, default=str).encode()).hexdigest()[:16]
        path = os.path.join(OUT, key + '.jpg')
        if not args.force and hashes.get(key) == h and os.path.exists(path):
            skipped += 1
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        render(spec, faces).save(path, 'JPEG', quality=86, optimize=True, progressive=True)
        hashes[key] = h
        drawn += 1
    if not args.only:
        # drop cards for pages that no longer exist
        for key in list(hashes):
            if key not in specs:
                p = os.path.join(OUT, key + '.jpg')
                if os.path.exists(p):
                    os.remove(p)
                del hashes[key]
    os.makedirs(OUT, exist_ok=True)
    json.dump(hashes, open(hpath, 'w', encoding='utf-8'), indent=0, sort_keys=True)
    print(f'share images: {drawn} drawn, {skipped} unchanged, {len(specs)} total')

if __name__ == '__main__':
    main()
