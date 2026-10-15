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
import argparse, collections, hashlib, io, json, os, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qlabels import short_label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'data')
OUT = os.path.join(ROOT, 'docs', 'og')
ASSETS = os.path.join(ROOT, 'scripts', 'og_assets')
FACES_URL = 'https://jsierrahoopshype.github.io/nba-headshots/'

DESIGN_VERSION = 1     # bump to force every card to redraw after a design change

W, H = 1200, 630
BG, CARD, LINE = (245, 245, 247), (255, 255, 255), (209, 209, 214)
INK, MUTED, ACCENT = (29, 29, 31), (110, 110, 115), (59, 130, 246)

# ---------------------------------------------------------------- fonts

_font_cache = {}
def font(kind, size, weight):
    key = (kind, size, weight)
    if key not in _font_cache:
        path = os.path.join(ASSETS, 'fonts', 'DMSans.ttf' if kind == 'sans' else 'JetBrainsMono.ttf')
        f = ImageFont.truetype(path, size)
        f.set_variation_by_axes([min(40, size), weight] if kind == 'sans' else [weight])
        _font_cache[key] = f
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

def circle_face(img, d):
    """Square face photo -> anti-aliased circle of diameter d. face2 crops can carry a
    dark band at the bottom, so take a top-anchored 1/1.2 window (same overscan the
    comparison video generator uses)."""
    s = min(img.size)
    win = int(s / 1.2)
    x0 = (img.size[0] - win) // 2
    crop = img.crop((x0, 0, x0 + win, win)).resize((d, d), Image.LANCZOS)
    return crop, circle_mask(d)

def circle_mask(d):
    big = Image.new('L', (d * 4, d * 4), 0)
    ImageDraw.Draw(big).ellipse((0, 0, d * 4 - 1, d * 4 - 1), fill=255)
    return big.resize((d, d), Image.LANCZOS)

def paste_visual(canvas, vis, cx, cy, d, faces):
    """vis = ('face', nbaId) | ('logo', abbr). Draws a ringed circle at (cx, cy)."""
    draw = ImageDraw.Draw(canvas)
    r = d // 2
    ring = 6
    draw.ellipse((cx - r - ring, cy - r - ring, cx + r + ring, cy + r + ring), fill=CARD, outline=LINE, width=2)
    if vis[0] == 'face':
        img = faces.get(vis[1])
        if img is None:
            return False
        face, mask = circle_face(img, d)
        canvas.paste(face, (cx - r, cy - r), mask)
    else:
        lg = logo(vis[1])
        if lg is None:
            return False
        inner = int(d * 0.68)
        lg.thumbnail((inner, inner), Image.LANCZOS)
        canvas.paste(lg, (cx - lg.size[0] // 2, cy - lg.size[1] // 2), lg)
    return True

def visual_ok(vis, faces):
    if not vis:
        return False
    if vis[0] == 'face':
        return faces.has(vis[1])
    return os.path.exists(os.path.join(ASSETS, 'logos', f'{vis[1]}.png'))

# ---------------------------------------------------------------- card renderer

def render(spec, faces):
    """spec: title, tiles [(num, label)], lines [(text, vis|None)], visual, badge, collage"""
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)

    # footer bar
    d.rectangle((0, H - 70, W, H), fill=CARD)
    d.line((0, H - 70, W, H - 70), fill=LINE, width=2)
    d.ellipse((64, H - 44, 82, H - 26), fill=ACCENT)
    d.text((94, H - 35), 'NBA GM Survey Tracker', font=font('sans', 26, 700), fill=INK, anchor='lm')
    d.text((W - 64, H - 35), 'hoopsmatic.com/nba-gm-survey', font=font('mono', 21, 500), fill=MUTED, anchor='rm')

    main_top, main_bot = 40, H - 70 - 34
    vis = spec.get('visual') if visual_ok(spec.get('visual'), faces) else None
    collage = [v for v in spec.get('collage', []) if visual_ok(v, faces)][:4]
    has_right = bool(vis) or len(collage) >= 2
    left, right = 64, (730 if has_right else W - 64)
    maxw = right - left

    # right side
    if vis:
        dia = 340 if spec.get('badge') else 380
        cy = (main_top + main_bot) // 2 - (24 if spec.get('badge') else 0)
        paste_visual(im, vis, 960, cy, dia, faces)
        if spec.get('badge'):
            bf = font('mono', 26, 600)
            bt = spec['badge']
            bw = text_w(bf, bt) + 40
            by = cy + dia // 2 + 26
            d.rounded_rectangle((960 - bw / 2, by, 960 + bw / 2, by + 48), radius=24, fill=ACCENT)
            d.text((960, by + 24), bt, font=bf, fill=(255, 255, 255), anchor='mm')
    elif len(collage) >= 2:
        pos = [(870, 190), (1050, 190), (870, 370), (1050, 370)]
        for (cx, cy), v in zip(pos, collage):
            paste_visual(im, v, cx, cy, 150, faces)

    # left block: measure first, then center vertically
    title = spec['title']
    for size in (76, 68, 60, 54, 48, 44, 40, 36):
        tf = font('sans', size, 700)
        lines = wrap(title, tf, maxw, 3)
        if lines:
            break
    else:
        tf = font('sans', 36, 700)
        lines = (wrap(title, tf, maxw, 99) or [title])[:3]
        lines[-1] = ellipsize(lines[-1] + ' …', tf, maxw)
    lh = int(tf.size * 1.12)
    blocks = [('title', lines, lh)]
    if spec.get('subtitle'):
        blocks.append(('sub', spec['subtitle'], 44))
    tiles = spec.get('tiles', [])[:3]
    if tiles:
        blocks.append(('tiles', tiles, 112))
    for t, v in spec.get('lines', [])[:3]:
        blocks.append(('line', (t, v if visual_ok(v, faces) else None), 58))
    gaps = {'title': 26, 'sub': 24, 'tiles': 18, 'line': 4}
    def height(bl):
        return sum(len(b[1]) * b[2] if b[0] == 'title' else b[2] for b in bl) + \
            sum(gaps[b[0]] for b in bl[:-1])
    while height(blocks) > main_bot - main_top and blocks[-1][0] == 'line':
        blocks.pop()                     # never let detail lines run into the footer
    total = height(blocks)
    y = main_top + max(0, (main_bot - main_top - total) // 2)

    for kind, payload, bh in blocks:
        if kind == 'title':
            for ln in payload:
                d.text((left, y), ln, font=tf, fill=INK)
                y += bh
        elif kind == 'sub':
            sf = font('sans', 30, 500)
            d.text((left, y), ellipsize(payload, sf, maxw), font=sf, fill=MUTED)
            y += bh
        elif kind == 'tiles':
            n = len(payload)
            tw = (maxw - 16 * (n - 1)) / n
            for i, (num, lab) in enumerate(payload):
                x0 = left + i * (tw + 16)
                d.rounded_rectangle((x0, y, x0 + tw, y + bh - 8), radius=14, fill=CARD, outline=LINE, width=2)
                nf = font('mono', 46 if len(str(num)) <= 5 else 34, 600)
                d.text((x0 + 20, y + 16), str(num), font=nf, fill=ACCENT)
                lf = font('sans', 21, 500)
                d.text((x0 + 20, y + 70), ellipsize(lab, lf, tw - 30), font=lf, fill=MUTED)
            y += bh
        else:
            txt, v = payload
            lf = font('sans', 27, 500)
            x = left
            if v:
                paste_visual(im, v, left + 22, y + 26, 40, faces)
                x = left + 60
            d.text((x, y + 26), ellipsize(txt, lf, right - x), font=lf, fill=INK, anchor='lm')
            y += bh
        y += gaps[kind]
    return im

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
                tiles = [(e['mentions'], 'time named' if e['mentions'] == 1 else 'times named'),
                         (e['nQ'], 'question' if e['nQ'] == 1 else 'questions'),
                         (f'{e["first"][2:]}–{e["last"][2:]}' if e['first'] != e['last'] else e['first'],
                          'seasons named' if e['first'] != e['last'] else 'season named')]
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
