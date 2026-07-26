#!/usr/bin/env python3
"""Generate all static HTML shells (SEO: baked titles/meta/canonical).

Run AFTER scripts/build_site_data.py:  python scripts/generate_entity_pages.py
Regenerates docs/index.html, list pages, and every season/question/player/
team/coach page from docs/data/*.json. Stdlib only.
"""
import json, os, html, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
BASE = 'https://jsierrahoopshype.github.io/nba-gm-survey'
SITE = 'NBA GM Survey Tracker'

def shell(*, title, desc, canonical, kind, key, root, nav_on=''):
    t = html.escape(title)
    d = html.escape(desc)
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
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:type" content="website">
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
<p class="strap">24 years of the NBA.com GM Survey, <b>cross-referenced</b> by player, team, coach, question and season.</p>
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
    latest = ix['seasons'][-1]
    first = ix['seasons'][0]

    # wipe generated page folders (never touches assets/ or data/)
    for d in ('seasons', 'questions', 'players', 'teams', 'coaches'):
        p = os.path.join(DOCS, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    n = 0
    # ---- top-level pages
    write(os.path.join(DOCS, 'index.html'), shell(
        title=f'{SITE} — every NBA.com GM Survey answer since {first}',
        desc=f'Every answer to every question in the annual NBA.com GM Survey, {first} to {latest}: '
             'searchable by player, team, coach, question and season.',
        canonical=f'{BASE}/', kind='home', key=None, root='', nav_on='home')); n += 1

    lists = [
        ('seasons', 'GM Survey seasons', f'All {len(ix["seasons"])} editions of the NBA.com GM Survey, {first} to {latest}.'),
        ('questions', 'Every GM Survey question', f'All {len(ix["questions"])} questions asked in the NBA.com GM Survey, with season-by-season results and trends.'),
        ('players', 'Players in the GM Survey', 'Every player NBA general managers have voted for, ranked by total survey mentions.'),
        ('teams', 'Teams in the GM Survey', 'Every NBA franchise in the GM Survey: team answers plus votes their players and coaches received.'),
        ('coaches', 'Coaches in the GM Survey', 'Every coach NBA general managers have voted for in the annual GM Survey.'),
    ]
    for kind, title, desc in lists:
        write(os.path.join(DOCS, f'{kind}.html'), shell(
            title=f'{title} | {SITE}', desc=desc, canonical=f'{BASE}/{kind}.html',
            kind=kind, key=None, root='', nav_on=kind)); n += 1

    urls = [f'{BASE}/', *(f'{BASE}/{k}.html' for k, _, _ in lists)]

    # ---- seasons
    for s in ix['seasons']:
        write(os.path.join(DOCS, 'seasons', f'{s}.html'), shell(
            title=f'{s} NBA GM Survey — full results | {SITE}',
            desc=f'Complete results of the {s} NBA.com GM Survey: every question, every answer, every percentage.',
            canonical=f'{BASE}/seasons/{s}.html', kind='season', key=s, root='../', nav_on='seasons'))
        urls.append(f'{BASE}/seasons/{s}.html'); n += 1

    # ---- questions
    for q in ix['questions']:
        span = (f'{q["nSeasons"]} seasons of answers ({q["first"]} to {q["last"]})'
                if q['nSeasons'] > 1 else f'asked in the {q["first"]} survey')
        write(os.path.join(DOCS, 'questions', f'{q["slug"]}.html'), shell(
            title=f'{q["text"]} | {SITE}',
            desc=f'“{q["text"]}” — {span} in the NBA.com GM Survey.',
            canonical=f'{BASE}/questions/{q["slug"]}.html', kind='question', key=q['slug'],
            root='../', nav_on='questions'))
        urls.append(f'{BASE}/questions/{q["slug"]}.html'); n += 1

    # ---- entities (page key = entity key; slug in filename)
    kinds = [('players', 'player', ix['entities']['players']),
             ('coaches', 'coach', ix['entities']['coaches']),
             ('teams', 'team', ix['entities']['teams'])]
    for folder, kind, ents in kinds:
        for e in ents:
            if e['first']:
                span = f'{e["first"]} to {e["last"]}'
                desc = (f'{e["name"]} in the NBA GM Survey: {e["mentions"]} mentions, '
                        f'{e["wins"]} No. 1 finishes across {e["nQ"]} questions, {span}.')
            else:
                desc = f'{e["name"]} in the NBA GM Survey: votes received by its players and coaches.'
            write(os.path.join(DOCS, folder, f'{e["slug"]}.html'), shell(
                title=f'{e["name"]} — GM Survey history | {SITE}',
                desc=desc, canonical=f'{BASE}/{folder}/{e["slug"]}.html',
                kind=kind, key=e['k'], root='../', nav_on=folder))
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
        kind='home', key=None, root='/nba-gm-survey/', nav_on=''))

    print(f'wrote {n} pages + sitemap.xml ({len(urls)} urls) + robots.txt + 404.html')

if __name__ == '__main__':
    main()
