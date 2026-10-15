#!/usr/bin/env python3
"""Generate all static HTML shells (SEO: baked titles/meta/canonical).

Run AFTER scripts/build_site_data.py:  python scripts/generate_entity_pages.py
Regenerates docs/index.html, list pages, and every season/question/player/
team/coach page from docs/data/*.json. Stdlib only.
"""
import json, os, html, shutil, collections, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qlabels import short_label

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
BASE = 'https://hoopsmatic.com/nba-gm-survey'
SITE = 'NBA GM Survey Tracker'
N_YEARS = 24   # overwritten in main() from the data, so the strap never goes stale

def og_image_tags(og_key, alt):
    """og:image/twitter tags for docs/og/<og_key>.jpg -- only if the image exists
    (scripts/generate_og_images.py makes them; without it pages just lack an image)."""
    if not og_key or not os.path.exists(os.path.join(DOCS, 'og', og_key + '.jpg')):
        return '<meta name="twitter:card" content="summary">'
    url = f'{BASE}/og/{og_key}.jpg'
    a = html.escape(alt)
    return (f'<meta property="og:image" content="{url}">\n'
            f'<meta property="og:image:width" content="1200">\n'
            f'<meta property="og:image:height" content="630">\n'
            f'<meta property="og:image:alt" content="{a}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:image" content="{url}">\n'
            f'<meta name="twitter:image:alt" content="{a}">')

def shell(*, title, desc, canonical, kind, key, root, nav_on='', og_key=None):
    t = html.escape(title)
    d = html.escape(desc)
    img = og_image_tags(og_key, title.replace(' | HoopsMatic', ''))
    navs = [('index.html', 'Home', 'home'), ('seasons.html', 'Seasons', 'seasons'),
            ('questions.html', 'Questions', 'questions'), ('players.html', 'Players', 'players'),
            ('teams.html', 'Teams', 'teams'), ('coaches.html', 'Coaches', 'coaches')]
    on_attr = ' class="on"'
    nav = ''.join(
        f'<a href="{root}{href}"{on_attr if on == nav_on else ""}>{label}</a>'
        for href, label, on in navs)
    page = json.dumps({'kind': kind, 'key': key, 'root': root})
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:url" content="{canonical}">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HoopsMatic">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
{img}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}assets/style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='46' fill='%233b82f6'/%3E%3Cpath d='M4 50h92M50 4v92M15 18a46 46 0 0 1 0 64M85 18a46 46 0 0 0 0 64' stroke='%23fff' stroke-width='5' fill='none'/%3E%3C/svg%3E">
</head>
<body>
<div class="wrap">
<div class="topbar"><input id="q" type="search" placeholder="Search players, teams, coaches, questions…" autocomplete="off">
<div class="search-results" id="qresults"></div></div>
<div class="masthead">
<h1><a href="{root}index.html">{SITE}</a></h1>
<p class="strap">{N_YEARS} years of the NBA.com GM Survey, <b>cross-referenced</b> by player, team, coach, question and season.</p>
</div>
<nav class="tabs">{nav}</nav>
<main id="app"><noscript>This site needs JavaScript to render the survey data.</noscript></main>
</div>
<footer class="site-foot"><div class="inner">
<span>{SITE}</span>
<span>Data: <a href="https://www.nba.com/news" target="_blank" rel="noopener">NBA.com annual GM Surveys</a></span>
<span>A <a href="https://hoopsmatic.com" target="_blank" rel="noopener">HoopsMatic</a> project</span>
</div></footer>
<script>window.PAGE={page};</script>
<script src="{root}assets/app.js"></script>
</body>
</html>
'''

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def main():
    data = os.path.join(DOCS, 'data')
    ix = json.load(open(os.path.join(data, 'entities.json'), encoding='utf-8'))
    global N_YEARS
    N_YEARS = len(ix['seasons'])
    latest = ix['seasons'][-1]
    first = ix['seasons'][0]

    # wipe generated page folders (never touches assets/ or data/)
    for d in ('seasons', 'questions', 'players', 'teams', 'coaches'):
        p = os.path.join(DOCS, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    n = 0
    SUF = ' | HoopsMatic'

    def load(*parts):
        return json.load(open(os.path.join(data, *parts), encoding='utf-8'))

    def pct(p):
        if p is None:
            return ''
        return f'{p:.0f}%' if abs(p - round(p)) < 0.05 else f'{p:.1f}%'

    def times(n, one='time', many='times'):
        return f'{n} {one if n == 1 else many}'

    ents = ix['entities']
    disp = {e['k']: e['name'] for kind in ('players', 'coaches', 'teams') for e in ents[kind]}

    # ---- top-level pages
    write(os.path.join(DOCS, 'index.html'), shell(
        title=f'NBA GM Survey history: every answer since {first}{SUF}',
        desc=f'Every answer to every question in the annual NBA.com GM Survey, {first} to {latest}: '
             'MVP and title picks, best players by position, coaches and more, searchable by '
             'player, team, coach, question and season.',
        canonical=f'{BASE}/', kind='home', key=None, root='', nav_on='home', og_key='home')); n += 1

    lists = [
        ('seasons', f'Every NBA GM Survey, {first} to {latest}',
         f'All {len(ix["seasons"])} editions of the NBA.com GM Survey, {first} to {latest}, with the '
         'franchise player, MVP and title picks from each year.'),
        ('questions', f'All {len(ix["questions"])} NBA GM Survey questions and results',
         f'All {len(ix["questions"])} questions NBA general managers have answered in the GM Survey, '
         'with season-by-season results, winners and trends.'),
        ('players', 'Players in the NBA GM Survey: most votes and No. 1 finishes',
         f'Every one of the {len(ents["players"])} players NBA general managers have voted for in the '
         'GM Survey, ranked by total votes and No. 1 finishes.'),
        ('teams', 'NBA teams in the GM Survey: every franchise’s votes',
         'Every NBA franchise in the GM Survey: title and conference picks, plus the votes its '
         'players and coaches received.'),
        ('coaches', 'Coaches in the NBA GM Survey: best head coach and assistant votes',
         f'Every one of the {len(ents["coaches"])} coaches NBA general managers have voted for in the '
         'GM Survey, from best head coach to best assistant.'),
    ]
    for kind, title, desc in lists:
        write(os.path.join(DOCS, f'{kind}.html'), shell(
            title=title + SUF, desc=desc, canonical=f'{BASE}/{kind}.html',
            kind=kind, key=None, root='', nav_on=kind, og_key=kind)); n += 1

    urls = [f'{BASE}/', *(f'{BASE}/{k}.html' for k, _, _ in lists)]

    # ---- seasons
    cards = {c['season']: c for c in ix['seasonCards']}
    for s in ix['seasons']:
        c = cards.get(s, {'nQ': 0, 'marquee': []})
        picks = ' '.join(f'{m["label"]}: {m["name"]} ({pct(m["pct"])}).'
                         for m in c['marquee'] if len(m['label']) < 30)
        write(os.path.join(DOCS, 'seasons', f'{s}.html'), shell(
            title=f'{s} NBA GM Survey results: all {c["nQ"]} questions and answers{SUF}',
            desc=f'Full results of the {s} NBA GM Survey, every question and every answer. {picks}'.strip(),
            canonical=f'{BASE}/seasons/{s}.html', kind='season', key=s, root='../',
            nav_on='seasons', og_key=f'seasons/{s}'))
        urls.append(f'{BASE}/seasons/{s}.html'); n += 1

    # ---- questions
    for q in ix['questions']:
        qd = load('q', q['slug'] + '.json')
        last = qd['seasons'][-1]
        tops = [a for a in last['answers'] if a['rank'] == 1]
        if q['nSeasons'] > 1:
            title = f'{q["text"]} NBA GM Survey picks, {q["first"]} to {q["last"]}'
            lead = (f'How NBA general managers answered “{q["text"]}” in '
                    f'{q["nSeasons"]} GM Surveys, {q["first"]} to {q["last"]}.')
        else:
            title = f'{q["text"]} {q["first"]} NBA GM Survey answers'
            lead = f'How NBA general managers answered “{q["text"]}” in the {q["first"]} GM Survey.'
        bits = [lead]
        if tops:
            names = ' and '.join(disp.get(a['e'], a['t']) for a in tops[:3])
            p = pct(tops[0]['pct'])
            bits.append(f'{last["season"]} No. 1: {names}' + (f' ({p}).' if p else '.'))
        tw = q.get('topWinner')
        if tw and q['nSeasons'] > 1 and tw['wins'] >= 2:
            bits.append(f'Most No. 1s: {tw["t"]} ({tw["wins"]}).')
        write(os.path.join(DOCS, 'questions', f'{q["slug"]}.html'), shell(
            title=title + SUF, desc=' '.join(bits),
            canonical=f'{BASE}/questions/{q["slug"]}.html', kind='question', key=q['slug'],
            root='../', nav_on='questions', og_key=f'questions/{q["slug"]}'))
        urls.append(f'{BASE}/questions/{q["slug"]}.html'); n += 1

    # ---- entities (page key = entity key; slug in filename)
    kinds = [('players', 'player', ents['players']),
             ('coaches', 'coach', ents['coaches']),
             ('teams', 'team', ents['teams'])]
    for folder, kind, elist in kinds:
        for e in elist:
            dd = load('e', e['k'] + '.json')
            span = (f'{e["first"]} to {e["last"]}' if e['first'] != e['last'] else e['first']) if e['first'] else ''
            if kind == 'team':
                mv = dd.get('memberVotes', [])
                cnt = collections.Counter(m['name'] for m in mv)
                top = cnt.most_common(1)[0] if cnt else None
                if e['first']:
                    title = f'{e["name"]} in the NBA GM Survey: every vote since {e["first"]}'
                    desc = (f'{e["name"]} in the NBA GM Survey: named {times(e["mentions"])} as a team '
                            f'({e["wins"]} No. 1 picks), plus {len(mv)} votes for its players and coaches.')
                else:
                    title = f'{e["name"]} in the NBA GM Survey: votes for its players and coaches'
                    desc = f'{e["name"]} in the NBA GM Survey: {len(mv)} votes for its players and coaches.'
                if top:
                    desc += f' Top vote-getter: {top[0]} ({times(top[1], "vote", "votes")}).'
            else:
                wins = [r for r in dd['rows'] if r['rank'] == 1 and r['rt'] == 'r']
                byq = collections.Counter(r['q'] for r in wins)
                if wins:
                    nw = len(wins)
                    title = (f'{e["name"]} in the NBA GM Survey: {nw} No. 1 '
                             f'{"finish" if nw == 1 else "finishes"}, every vote')
                    qq, k = byq.most_common(1)[0]
                    desc = (f'Every NBA GM Survey vote for {e["name"]}: named {times(e["mentions"])} '
                            f'across {e["nQ"]} {"question" if e["nQ"] == 1 else "questions"}, {span}, '
                            f'with {nw} No. 1 {"finish" if nw == 1 else "finishes"}. '
                            f'Most No. 1s: {short_label(qq)} ({k}).')
                else:
                    title = f'{e["name"]} in the NBA GM Survey: every vote, {span}'
                    best = min(dd['rows'], key=lambda r: (r['rank'], -(r['pct'] or 0)))
                    desc = (f'Every NBA GM Survey vote for {e["name"]}: named {times(e["mentions"])} '
                            f'across {e["nQ"]} {"question" if e["nQ"] == 1 else "questions"}, {span}. '
                            f'Best finish: No. {best["rank"]}, {short_label(best["q"])} '
                            f'({best["season"]}).')
            write(os.path.join(DOCS, folder, f'{e["slug"]}.html'), shell(
                title=title + SUF, desc=desc, canonical=f'{BASE}/{folder}/{e["slug"]}.html',
                kind=kind, key=e['k'], root='../', nav_on=folder, og_key=f'{folder}/{e["slug"]}'))
            urls.append(f'{BASE}/{folder}/{e["slug"]}.html'); n += 1

    # ---- sitemap + 404
    with open(os.path.join(DOCS, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write(f'  <url><loc>{u}</loc></url>\n')
        f.write('</urlset>\n')
    write(os.path.join(DOCS, 'robots.txt'), f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n')
    write(os.path.join(DOCS, '404.html'), shell(
        title=f'Not found | {SITE}', desc='Page not found.', canonical=f'{BASE}/',
        kind='home', key=None, root='/nba-gm-survey/', nav_on='', og_key='home'))

    print(f'wrote {n} pages + sitemap.xml ({len(urls)} urls) + robots.txt + 404.html')

if __name__ == '__main__':
    main()
