#!/usr/bin/env python3
"""Regenerate data/player_ids.csv (answer name -> NBA person id).

Requires: pip install nba_api  (only needed when NEW player names appear in the CSV;
the committed player_ids.csv is used by build_site_data.py, which is stdlib-only).
Run: python scripts/update_player_ids.py
"""
import csv, re, unicodedata, collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = s.lower().replace('-', ' ').replace("'", '')
    s = s.replace('.', '')                      # J.J. -> JJ (not "j j")
    s = re.sub(r'[^a-z ]', '', s)
    return re.sub(r'\s+', ' ', s).strip()

SUFFIXES = (' jr', ' sr', ' ii', ' iii', ' iv')
def strip_suffix(n):
    for suf in SUFFIXES:
        if n.endswith(suf):
            return n[: -len(suf)].strip()
    return n

# Manual aliases: survey spelling -> canonical NBA list spelling
ALIASES = {
    'Ron Artest': 'Metta World Peace',
    'Jimmy Butler': 'Jimmy Butler III',
    'Lu Dort': 'Luguentz Dort',
    'Enes Kanter': 'Enes Freedom',
    'Herb Jones': 'Herbert Jones',
    'Cam Johnson': 'Cameron Johnson',
    'Louis Williams': 'Lou Williams',
    'Paul Gasol': 'Pau Gasol',
    'Shabazz Muhammed': 'Shabazz Muhammad',
    'JJ Reddick': 'JJ Redick',
    'J. Redick': 'JJ Redick',
    'Ronald Murray': 'Flip Murray',
    'Mackael Gelabale': 'Mickael Gelabale',
    'Jan Veseley': 'Jan Vesely',
    'Cameron Reddish': 'Cam Reddish',
    'Ron Holland II': 'Ronald Holland II',
    'Andre Bynum': 'Andrew Bynum',
    'Andres Biedrins': 'Andris Biedrins',
    'Marquese Chris': 'Marquese Chriss',
    'Mike Sweetney': 'Michael Sweetney',
    'Nasir Little': 'Nassir Little',
    'Nicolas Claxton': 'Nic Claxton',
    'Sefolosha': 'Thabo Sefolosha',
}
# Ambiguous names: survey era makes the right guy unambiguous
FORCED_IDS = {
    'Mike Dunleavy': 2399,      # Mike Dunleavy Jr. (player; Sr. only shows up as a coach answer)
    'Mike Dunleavy Jr.': 2399,
    'Mike James': 2229,         # 2000s journeyman guard, not the 2017 two-way
    'Steve Smith': 120,         # listed as "Steven Smith" in the NBA index
}

def main():
    try:
        from nba_api.stats.static import players
    except ImportError:
        sys.exit('nba_api not installed. Run: pip install nba_api')

    byname = collections.defaultdict(list)
    for p in players.get_players():
        byname[norm(p['full_name'])].append(p)
    # suffix-stripped secondary index (only where unambiguous)
    nosuf = collections.defaultdict(list)
    for key, ps in byname.items():
        nosuf[strip_suffix(key)].extend(ps)

    qtypes = json.load(open(os.path.join(ROOT, 'data', 'question_types.json'), encoding='utf-8'))
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'gm_survey.csv'), encoding='utf-8-sig')))

    names = set()
    for r in rows:
        if qtypes.get(r['question']) != 'player':
            continue
        ans = r['answer'].strip()
        ans = re.sub(r'\s*\(.*?\)\s*$', '', ans)     # "Kevin Durant (re-signed)"
        ans = ans.split(',')[0].strip()              # "Sergio Llull, Real Madrid"
        names.add(ans)

    out, unmatched = [], []
    for name in sorted(names):
        target = ALIASES.get(name, name)
        if name in FORCED_IDS:
            out.append((name, FORCED_IDS[name], target)); continue
        n = norm(target)
        cands = byname.get(n, [])
        if not cands:
            cands = [p for p in nosuf.get(strip_suffix(n), []) ]
        if len(cands) == 1:
            out.append((name, cands[0]['id'], cands[0]['full_name']))
        elif len(cands) > 1:
            unmatched.append((name, 'AMBIGUOUS: ' + ', '.join(str(c['id']) for c in cands)))
        else:
            unmatched.append((name, ''))

    with open(os.path.join(ROOT, 'data', 'player_ids.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['answer_name', 'nba_person_id', 'nba_name'])
        for row in out: w.writerow(row)
    print(f'matched {len(out)} names, unmatched {len(unmatched)}')
    for n, note in unmatched: print('  UNMATCHED', n, note)

if __name__ == '__main__':
    main()
