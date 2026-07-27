#!/usr/bin/env python3
"""NBA GM Survey Tracker — data pipeline.

Reads  data/gm_survey.csv (+ data/player_ids.csv, data/aliases.json)
Writes docs/data/*.json  (entities index, highlights, per-question,
       per-season and per-entity JSON files)

Stdlib only. Run from the repo root:  python scripts/build_site_data.py
When a new survey year is added to the CSV, rerun this, then
scripts/generate_entity_pages.py. If brand-new player names appear,
run scripts/update_player_ids.py first (needs nba_api).
"""
import csv, json, os, re, sys, shutil, unicodedata, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'docs', 'data')

# ---------------------------------------------------------------- helpers

def slugify(s, maxlen=70):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
    if len(s) > maxlen:
        s = s[:maxlen].rsplit('-', 1)[0]
    return s

def norm_name(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower().replace('-', ' ').replace("'", '').replace('.', '')
    s = re.sub(r'[^a-z ]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

def parse_pct(s):
    s = s.strip().rstrip('%')
    if not s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None

# ---------------------------------------------------------------- teams

TEAM_IDS = {'ATL': 1610612737, 'BOS': 1610612738, 'CLE': 1610612739, 'NOP': 1610612740,
            'CHI': 1610612741, 'DAL': 1610612742, 'DEN': 1610612743, 'GSW': 1610612744,
            'HOU': 1610612745, 'LAC': 1610612746, 'LAL': 1610612747, 'MIA': 1610612748,
            'MIL': 1610612749, 'MIN': 1610612750, 'BKN': 1610612751, 'NYK': 1610612752,
            'ORL': 1610612753, 'IND': 1610612754, 'PHI': 1610612755, 'PHX': 1610612756,
            'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'OKC': 1610612760,
            'TOR': 1610612761, 'UTA': 1610612762, 'MEM': 1610612763, 'WAS': 1610612764,
            'DET': 1610612765, 'CHA': 1610612766}

TEAM_NAMES = {'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
              'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
              'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
              'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
              'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
              'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
              'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
              'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
              'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
              'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'}

TEAM_SHORT = {'Atlanta': 'ATL', 'Boston': 'BOS', 'Brooklyn': 'BKN', 'Charlotte': 'CHA',
              'Chicago': 'CHI', 'Cleveland': 'CLE', 'Dallas': 'DAL', 'Denver': 'DEN',
              'Detroit': 'DET', 'Golden State': 'GSW', 'Houston': 'HOU', 'Indiana': 'IND',
              'LA Clippers': 'LAC', 'LA Lakers': 'LAL', 'L.A. Clippers': 'LAC', 'L.A. Lakers': 'LAL',
              'Memphis': 'MEM', 'Miami': 'MIA', 'Milwaukee': 'MIL', 'Minnesota': 'MIN',
              'New Jersey': 'BKN', 'N.J.': 'BKN', 'New Orleans': 'NOP',
              'New Orleans/Oklahoma City': 'NOP', 'New York': 'NYK', 'Oklahoma City': 'OKC',
              'Orlando': 'ORL', 'Philadelphia': 'PHI', 'Phoenix': 'PHX', 'Portland': 'POR',
              'Portland Trail': 'POR', 'Sacramento': 'SAC', 'San Antonio': 'SAS',
              'Seattle': 'OKC', 'Seattle Sonics': 'OKC', 'Toronto': 'TOR', 'Utah': 'UTA',
              'Washington': 'WAS'}

TEAM_FULL = {'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
             'New Jersey Nets': 'BKN', 'Charlotte Hornets': 'CHA', 'Charlotte Bobcats': 'CHA',
             'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE', 'Dallas Mavericks': 'DAL',
             'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET', 'Golden State Warriors': 'GSW',
             'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND', 'Los Angeles Clippers': 'LAC',
             'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA',
             'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
             'New Orleans Pelicans': 'NOP', 'New Orleans Hornets': 'NOP',
             'New Orleans/Oklahoma City Hornets': 'NOP', 'New York Knicks': 'NYK',
             'Oklahoma City Thunder': 'OKC', 'Seattle SuperSonics': 'OKC', 'Orlando Magic': 'ORL',
             'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX', 'Portland Trail Blazers': 'POR',
             'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR',
             'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'}

def team_abbr(raw):
    a = raw.strip().lstrip('. ').strip()
    return TEAM_SHORT.get(a) or TEAM_FULL.get(a)

def era_label(abbr, end_year):
    """Franchise name as it was called in that season (end_year = season_end_year)."""
    if abbr == 'BKN':
        return 'New Jersey Nets' if end_year <= 2012 else 'Brooklyn Nets'
    if abbr == 'OKC':
        return 'Seattle SuperSonics' if end_year <= 2008 else 'Oklahoma City Thunder'
    if abbr == 'NOP':
        if end_year in (2006, 2007):
            return 'New Orleans/Oklahoma City Hornets'
        return 'New Orleans Hornets' if end_year <= 2013 else 'New Orleans Pelicans'
    if abbr == 'CHA':
        return 'Charlotte Bobcats' if 2005 <= end_year <= 2014 else 'Charlotte Hornets'
    return TEAM_NAMES[abbr]

# ---------------------------------------------------------------- question typing

def question_type(q, answers, overrides):
    if q in overrides:
        return overrides[q]
    ql = q.lower()
    if re.search(r'surprising move|rule|country|countries|continent|duo|pandemic|which change|challenge facing', ql):
        return 'other'
    if 'coach' in ql and not ql.startswith(('which player', 'which active player')):
        return 'coach'
    tm = sum(1 for a in answers if team_abbr(a))
    if tm / len(answers) > 0.5:
        return 'team'
    return 'player'

# ---------------------------------------------------------------- main

def main():
    rows = list(csv.DictReader(open(os.path.join(DATA, 'gm_survey.csv'), encoding='utf-8-sig')))

    # optional support files
    def load_json(name, default):
        p = os.path.join(DATA, name)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default
    aliases = load_json('aliases.json', {})           # answer spelling -> canonical display
    overrides = load_json('question_overrides.json', {})  # question text -> forced type
    pid_by_name = {}
    pid_file = os.path.join(DATA, 'player_ids.csv')
    if os.path.exists(pid_file):
        for r in csv.DictReader(open(pid_file, encoding='utf-8')):
            pid_by_name[r['answer_name']] = (int(r['nba_person_id']), r['nba_name'])

    # -------- question typing
    qans = collections.defaultdict(list)
    for r in rows:
        qans[r['question']].append(r['answer'])
    qtype = {q: question_type(q, a, overrides) for q, a in qans.items()}
    json.dump(qtype, open(os.path.join(DATA, 'question_types.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)

    # -------- question registry (stable slugs)
    seasons_all = sorted(set(r['season'] for r in rows))
    qmeta = {}
    used_slugs = set()
    for q in sorted(qans):
        group = next((r['question_unification_group'] for r in rows
                      if r['question'] == q and r['question_unification_group']), None)
        base = slugify(group) if group else slugify(q)
        slug = base
        n = 2
        while slug in used_slugs:
            slug = f'{base}-{n}'; n += 1
        used_slugs.add(slug)
        qmeta[q] = {'slug': slug, 'group': group, 'type': qtype[q]}

    # -------- entity resolution per row
    def clean_answer(ans):
        a = ans.strip().lstrip('. ').strip()
        a = re.sub(r'\s*\(.*?\)\s*$', '', a)
        return a

    ent_names = {}                       # key -> display name candidates counter
    ent_kind = {}                        # key -> player/coach/team
    ent_extra = {}                       # key -> dict (nba id / abbr / affiliations)
    row_ent = []                         # per row: (key or None, display, affiliation)

    for r in rows:
        t = qtype[r['question']]
        raw = clean_answer(r['answer'])
        affil = None
        key = disp = None
        text_out = raw                      # what pages display for this row
        if t == 'team':
            ab = team_abbr(raw)
            if ab:
                key = 't-' + ab
                disp = era_label(ab, int(r['season_end_year']))
                ent_kind[key] = 'team'
                ent_extra.setdefault(key, {'abbr': ab, 'nbaTeamId': TEAM_IDS[ab]})
        elif t in ('player', 'coach'):
            name = raw
            if t == 'player' and ',' in name:      # "Sergio Llull, Real Madrid"
                name, affil = [x.strip() for x in name.split(',', 1)]
                if affil.count(',') >= 1:          # messy multi-name rows stay as text
                    name, affil = raw, None
            text_out = name                        # affiliation shown separately
            name = aliases.get(name, name)
            if t == 'player' and name in pid_by_name:
                pid, nba_name = pid_by_name[name]
                key = f'p{pid}'
                disp = nba_name
                ent_kind[key] = 'player'
                ent_extra.setdefault(key, {'nbaId': pid})
            elif ' ' in name or t == 'coach':      # named person without NBA id
                key = ('c-' if t == 'coach' else 'x-') + slugify(name)
                disp = name
                ent_kind[key] = t
                ent_extra.setdefault(key, {})
            # single-word oddities ("Sefolosha" already aliased) stay unlinked
        if key:
            ent_names.setdefault(key, collections.Counter())[disp] += 1
            if affil:
                ent_extra[key].setdefault('affiliations', set()).add(affil)
        row_ent.append((key, text_out, affil))

    # display name = most frequent spelling (teams use current franchise name)
    ent_disp = {}
    for k, c in ent_names.items():
        if k.startswith('t-'):
            ent_disp[k] = TEAM_NAMES[k[2:]]
        else:
            ent_disp[k] = c.most_common(1)[0][0]

    # entity slugs (players/coaches); ensure uniqueness across kinds via folders
    ent_slug = {}
    used = collections.defaultdict(set)
    for k in ent_names:
        kind = ent_kind[k]
        base = k[2:] if k.startswith('t-') else slugify(ent_disp[k])
        if k.startswith('t-'):
            base = slugify(TEAM_NAMES[k[2:]])
        s = base
        n = 2
        while s in used[kind]:
            s = f'{base}-{n}'; n += 1
        used[kind].add(s)
        ent_slug[k] = s

    # -------- assemble per-question season blocks
    def section_label(sec):
        if sec.startswith('> '):
            return sec[2:]
        if 'Kia Season Preview' in sec:
            return 'Kia Season Preview'
        return ''

    q_seasons = collections.defaultdict(dict)   # q -> season -> block
    for i, r in enumerate(rows):
        q = r['question']
        s = r['season']
        blk = q_seasons[q].setdefault(s, {
            'season': s, 'endYear': int(r['season_end_year']),
            'section': section_label(r['section']),
            'original': r['original_question'] if r['original_question'] != q else None,
            'source': r['source_url'],
            'totalPct': r['question_total_percentage'],
            'totalStatus': r['question_total_status'],
            'answers': []})
        key, raw, affil = row_ent[i]
        blk['answers'].append({
            't': raw,
            'e': key,
            'affil': affil,
            'pct': parse_pct(r['percentage']),
            'rank': int(r['rank']),
            'rt': 'r' if r['response_type'] == 'ranked' else 'v',   # ranked / also receiving votes
            'ps': r['percentage_status'],
            'teamRaw': r['team'],
            'teamAbbr': team_abbr(r['team']) if r['team'] else None,
        })

    for q in q_seasons:
        for s in q_seasons[q]:
            q_seasons[q][s]['answers'].sort(key=lambda a: (a['rank'], -(a['pct'] or 0)))

    # -------- write per-question files
    for d in ('q', 's', 'e'):
        p = os.path.join(OUT, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
        os.makedirs(p)

    q_index = []
    for q in sorted(qans):
        m = qmeta[q]
        blocks = [q_seasons[q][s] for s in sorted(q_seasons[q])]
        obj = {'text': q, 'slug': m['slug'], 'type': m['type'], 'group': m['group'],
               'seasons': blocks}
        json.dump(obj, open(os.path.join(OUT, 'q', m['slug'] + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
        winners = []
        win_counts = collections.Counter()
        win_names = {}
        for b in blocks:
            top = [a for a in b['answers'] if a['rank'] == 1]
            winners.append({'season': b['season'],
                            'top': [{'t': a['t'], 'e': a['e'], 'pct': a['pct']} for a in top]})
            for a in top:
                wk = a['e'] or a['t']
                win_counts[wk] += 1
                win_names[wk] = ent_disp.get(a['e'], a['t']) if a['e'] else a['t']
        top_winner = None
        if win_counts:
            wk, n = win_counts.most_common(1)[0]
            top_winner = {'t': win_names[wk], 'e': wk if wk in ent_disp else None, 'wins': n}
        q_index.append({'text': q, 'slug': m['slug'], 'type': m['type'], 'group': m['group'],
                        'nSeasons': len(blocks), 'first': blocks[0]['season'],
                        'last': blocks[-1]['season'], 'latestTop': winners[-1]['top'],
                        'topWinner': top_winner})

    # -------- per-season files
    season_qs = collections.defaultdict(list)
    for q in sorted(qans):
        for s, blk in q_seasons[q].items():
            season_qs[s].append({'text': q, 'slug': qmeta[q]['slug'], 'type': qmeta[q]['type'],
                                 'section': blk['section'], 'original': blk['original'],
                                 'source': blk['source'], 'totalPct': blk['totalPct'],
                                 'totalStatus': blk['totalStatus'], 'answers': blk['answers']})
    sec_order = ['Players', 'Defense', 'Coaches', 'Rookies & International Players',
                 'Offseason Moves', 'Predictions', 'Miscellaneous', 'Kia Season Preview', '']
    for s, qs in season_qs.items():
        qs.sort(key=lambda x: (sec_order.index(x['section']) if x['section'] in sec_order else 99,
                               x['text']))
        json.dump({'season': s, 'questions': qs},
                  open(os.path.join(OUT, 's', s + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))

    # -------- per-entity files + entity index
    ent_rows = collections.defaultdict(list)     # key -> appearance rows
    for i, r in enumerate(rows):
        key, raw, affil = row_ent[i]
        if not key:
            continue
        q = r['question']
        ent_rows[key].append({
            'q': q, 'slug': qmeta[q]['slug'], 'season': r['season'],
            'endYear': int(r['season_end_year']),
            'pct': parse_pct(r['percentage']), 'rank': int(r['rank']),
            'rt': 'r' if r['response_type'] == 'ranked' else 'v',
            'teamRaw': r['team'], 'teamAbbr': team_abbr(r['team']) if r['team'] else None,
            'source': r['source_url'], 't': raw, 'affil': affil,
        })

    # team pages: votes received by players/coaches while on that team
    team_member_rows = collections.defaultdict(list)
    for i, r in enumerate(rows):
        key, raw, affil = row_ent[i]
        if not key or key.startswith('t-'):
            continue
        ab = team_abbr(r['team']) if r['team'] else None
        if ab:
            q = r['question']
            team_member_rows['t-' + ab].append({
                'name': ent_disp[key], 'e': key, 'kind': ent_kind[key],
                'slug': ent_slug[key],
                'q': q, 'qslug': qmeta[q]['slug'], 'season': r['season'],
                'pct': parse_pct(r['percentage']), 'rank': int(r['rank']),
                'rt': 'r' if r['response_type'] == 'ranked' else 'v'})

    entities = {'players': [], 'coaches': [], 'teams': []}
    for k in sorted(ent_rows):
        rws = sorted(ent_rows[k], key=lambda x: (x['endYear'], x['q']))
        wins = sum(1 for x in rws if x['rank'] == 1)
        firsts = rws[0]['season']; lasts = rws[-1]['season']
        info = {'k': k, 'name': ent_disp[k], 'slug': ent_slug[k],
                'mentions': len(rws), 'wins': wins,
                'nQ': len(set(x['q'] for x in rws)), 'first': firsts, 'last': lasts}
        kind = ent_kind[k]
        if kind == 'player':
            if k.startswith('p'):
                info['nbaId'] = ent_extra[k]['nbaId']
            entities['players'].append(info)
        elif kind == 'coach':
            entities['coaches'].append(info)
        else:
            info['abbr'] = k[2:]
            info['nbaTeamId'] = TEAM_IDS[k[2:]]
            entities['teams'].append(info)

        # entity detail file
        detail = dict(info)
        detail['rows'] = rws
        if kind == 'team':
            detail['memberVotes'] = sorted(team_member_rows.get(k, []),
                                           key=lambda x: (-x['pct'] if x['pct'] else 0, x['season']))
            hist = sorted(set(era_label(k[2:], y) for y in
                              set(x['endYear'] for x in rws)) |
                          set(era_label(k[2:], x['endYear'])
                              for x in team_member_rows.get(k, []) if False) )
            detail['eraNames'] = hist
        folder = {'player': 'e', 'coach': 'e', 'team': 'e'}[kind]
        json.dump(detail, open(os.path.join(OUT, folder, k + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))

    for lst in entities.values():
        lst.sort(key=lambda x: -x['mentions'])

    # teams that never were an answer but have member votes still deserve pages
    for k, mv in team_member_rows.items():
        if k not in ent_rows:
            ab = k[2:]
            info = {'k': k, 'name': TEAM_NAMES[ab], 'slug': slugify(TEAM_NAMES[ab]),
                    'mentions': 0, 'wins': 0, 'nQ': 0, 'first': None, 'last': None,
                    'abbr': ab, 'nbaTeamId': TEAM_IDS[ab]}
            entities['teams'].append(info)
            detail = dict(info); detail['rows'] = []
            detail['memberVotes'] = sorted(mv, key=lambda x: (-(x['pct'] or 0), x['season']))
            json.dump(detail, open(os.path.join(OUT, 'e', k + '.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
            ent_slug[k] = info['slug']; ent_kind[k] = 'team'; ent_disp[k] = info['name']

    # season cards for the seasons index page (marquee winners per year)
    season_cards = []
    for s in seasons_all:
        qs = season_qs[s]
        marquee = []
        def add_marquee(label, pred):
            for qq in qs:
                if pred(qq['text']):
                    tops = [a for a in qq['answers'] if a['rank'] == 1]
                    if tops:
                        a = tops[0]
                        nm = ent_disp.get(a['e']) if a['e'] else None
                        marquee.append({'label': label, 'name': nm or a['t'],
                                        'e': a['e'], 'pct': a['pct'], 'qslug': qq['slug']})
                    return
        add_marquee('Franchise player', lambda t: 'starting a franchise' in t.lower())
        add_marquee('MVP pick', lambda t: t.lower().startswith('who will win') and 'mvp' in t.lower())
        add_marquee('Finals pick', lambda t: 'win the nba finals' in t.lower())
        if not marquee:      # very early years: just take the first winners
            for qq in qs[:3]:
                tops = [a for a in qq['answers'] if a['rank'] == 1]
                if tops:
                    a = tops[0]
                    nm = ent_disp.get(a['e']) if a['e'] else None
                    marquee.append({'label': qq['text'][:40], 'name': nm or a['t'],
                                    'e': a['e'], 'pct': a['pct'], 'qslug': qq['slug']})
        season_cards.append({'season': s, 'nQ': len(qs), 'marquee': marquee})

    # team cards for the teams index page (top vote-getters while on each team)
    team_cards = []
    for e in sorted(entities['teams'], key=lambda x: x['name']):
        k = e['k']
        counts = collections.Counter()
        winc = collections.Counter()
        meta = {}
        for m in team_member_rows.get(k, []):
            counts[m['e']] += 1
            if m['rank'] == 1 and m['rt'] == 'r':
                winc[m['e']] += 1
            meta[m['e']] = m
        top_members = []
        for mk, n in counts.most_common(3):
            m = meta[mk]
            top_members.append({'name': m['name'], 'e': mk, 'kind': m['kind'],
                                'slug': m['slug'], 'n': n, 'wins': winc.get(mk, 0)})
        team_cards.append({'k': k, 'name': e['name'], 'abbr': e['abbr'],
                           'teamId': e['nbaTeamId'], 'mentions': e['mentions'],
                           'wins': e['wins'], 'slug': e['slug'], 'topMembers': top_members})

    json.dump({'seasons': seasons_all, 'seasonCards': season_cards, 'teamCards': team_cards,
               'questions': q_index, 'entities': entities},
              open(os.path.join(OUT, 'entities.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))

    # -------- highlights
    latest = seasons_all[-1]
    latest_winners = []
    for qi in q_index:
        if qi['last'] == latest:
            blkq = q_seasons[qi['text']][latest]
            top = [a for a in blkq['answers'] if a['rank'] == 1]
            latest_winners.append({'q': qi['text'], 'slug': qi['slug'], 'type': qi['type'],
                                   'section': blkq['section'],
                                   'top': [{'t': a['t'], 'e': a['e'], 'pct': a['pct']} for a in top]})

    def top_entities(kind, n=10):
        return [e for e in entities[kind][:n]]

    # longest same-question winning streaks
    streaks = []
    for q in sorted(qans):
        seasons_q = sorted(q_seasons[q], key=lambda s: q_seasons[q][s]['endYear'])
        prev = {}
        run = collections.defaultdict(int)
        best = {}
        for s in seasons_q:
            tops = set(a['e'] or a['t'] for a in q_seasons[q][s]['answers'] if a['rank'] == 1)
            for t in tops:
                run[t] = run.get(t, 0) + 1 if t in prev else 1
                cur = best.get(t, (0, None))
                if run[t] > cur[0]:
                    best[t] = (run[t], s)
            for t in list(run):
                if t not in tops:
                    run[t] = 0
            prev = tops
        for t, (n, endseason) in best.items():
            if n >= 4:
                name = ent_disp.get(t, t)
                streaks.append({'who': name, 'e': t if t in ent_disp else None,
                                'slug': ent_slug.get(t), 'kind': ent_kind.get(t),
                                'q': q, 'qslug': qmeta[q]['slug'], 'len': n, 'end': endseason})
    streaks.sort(key=lambda x: -x['len'])

    # biggest landslides (reported #1 shares)
    lands = []
    for q in sorted(qans):
        for s, blk in q_seasons[q].items():
            for a in blk['answers']:
                if a['rank'] == 1 and a['pct'] and a['ps'] == 'reported by NBA.com':
                    lands.append({'who': a['t'], 'e': a['e'], 'slug': ent_slug.get(a['e']),
                                  'kind': ent_kind.get(a['e']), 'pct': a['pct'],
                                  'q': q, 'qslug': qmeta[q]['slug'], 'season': s})
    lands.sort(key=lambda x: -x['pct'])

    highlights = {
        'latestSeason': latest,
        'latestWinners': latest_winners,
        'topPlayers': top_entities('players'),
        'topCoaches': top_entities('coaches', 6),
        'topTeams': top_entities('teams', 6),
        'streaks': streaks[:12],
        'landslides': lands[:12],
        'stats': {'rows': len(rows), 'seasons': len(seasons_all),
                  'questions': len(qans), 'players': len(entities['players']),
                  'coaches': len(entities['coaches'])},
    }
    json.dump(highlights, open(os.path.join(OUT, 'highlights.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))

    # slug map for the page generator
    json.dump({'entSlug': ent_slug, 'entKind': ent_kind, 'entDisp': ent_disp},
              open(os.path.join(OUT, 'slugmap.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))

    print(f'rows {len(rows)} | questions {len(qans)} | players {len(entities["players"])} '
          f'| coaches {len(entities["coaches"])} | teams {len(entities["teams"])}')
    print('wrote docs/data/: entities.json, highlights.json, slugmap.json, '
          f'q/*.json ({len(q_index)}), s/*.json ({len(season_qs)}), e/*.json ({len(ent_rows)})')

if __name__ == '__main__':
    main()
