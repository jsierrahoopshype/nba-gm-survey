"""Short, human labels for GM Survey questions (used on share images and in page
descriptions, where the full question text is too long). Stdlib only."""
import re

OVERRIDES = {
    'If you were starting a franchise today and could sign any player in the NBA, who would it be?': 'Franchise player',
    'Which player would you want taking the final shot?': 'Final shot',
    'Which player is most likely to have a breakout season?': 'Breakout player',
    'Which team will win the NBA Finals?': 'NBA title pick',
    'Who will win MVP?': 'MVP pick',
    'Who will win Rookie of the Year?': 'Rookie of the Year pick',
    'Who will win Defensive Player of the Year?': 'Defensive Player of the Year pick',
    'Which active player will make the best head coach someday?': 'Future head coach',
    'Which player acquisition will make the biggest impact?': 'Biggest-impact acquisition',
    'Which rookie will be the best player in five years?': 'Best rookie in five years',
    'Which team made the best overall offseason moves?': 'Best offseason moves',
    'What was the most underrated player acquisition?': 'Most underrated acquisition',
    'Which head coach is the best manager/motivator of people?': 'Best motivator (coach)',
    'Which head coach makes the best in-game adjustments?': 'Best in-game adjustments (coach)',
    'Which player forces coaches to make the most adjustments?': 'Forces most adjustments',
    'Which team will be most improved?': 'Most improved team',
    'Who is the best defensive player in the NBA?': 'Best defender',
    'Who is the best international player not in the NBA?': 'Best international outside the NBA',
    'Who is the best international player in the NBA?': 'Best international player',
    'Which head coach has the best defensive schemes?': 'Best defensive schemes (coach)',
    'Which head coach runs the best offense?': 'Best offense (coach)',
    'Which rookie was the biggest steal at where he was selected in the Draft?': 'Biggest draft steal',
    'Which international player is most likely to have a breakout season?': 'International breakout player',
    'Which new or relocated head coach will make the biggest impact?': 'New coach with the biggest impact',
    'What bench player makes the biggest impact when he enters the game?': 'Best bench player',
    'Which team will have the league’s most efficient offense this season?': 'Most efficient offense',
    'Which team’s level of success this season is toughest to predict?': 'Toughest team to predict',
    'Which head coach is the best in the last two minutes of a close game?': 'Best coach in close games',
    'Who is the player most likely to get a rebound if a game depended on it?': 'Clutch rebounder',
    'What NBA rule most needs to change?': 'Rule that most needs to change',
}

PREFIXES = [
    'Which team will win the ', 'Who will win ', 'Who is the NBA’s ', 'Who is the ', 'Who has the ',
    'Which player is the ', 'Which player is ', 'Which player has the ', 'Which player ',
    'Which team is the ', 'Which team has the ', 'Which team will be the ', 'Which team ',
    'Which head coach is the ', 'Which head coach ', 'Which rookie is the ', 'Which rookie is ',
    'Which rookie ', 'Which is the ', 'What was the ', 'Which ', 'What ', 'Who is ', 'Who ',
]

def short_label(q):
    if q in OVERRIDES:
        return OVERRIDES[q]
    s = q.rstrip('?').strip()
    m = re.match(r'Which team will win the (.+)$', s)
    if m:
        return m.group(1) + ' pick'
    for p in PREFIXES:
        if s.startswith(p):
            s = s[len(p):]
            break
    s = re.sub(r'\s+in the NBA$', '', s)
    s = s.replace('NBA’s ', '')
    return s[:1].upper() + s[1:]
