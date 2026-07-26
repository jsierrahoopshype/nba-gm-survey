/* NBA GM Survey Tracker — page renderer (vanilla JS, no dependencies) */
(function () {
  'use strict';
  var P = window.PAGE || { kind: 'home', root: '' };
  var R = P.root || '';
  var $app = document.getElementById('app');
  var cache = {};

  function fetchJSON(path) {
    if (cache[path]) return cache[path];
    cache[path] = fetch(R + 'data/' + path).then(function (r) {
      if (!r.ok) throw new Error(path + ' -> ' + r.status);
      return r.json();
    });
    return cache[path];
  }

  // ---------------------------------------------------------------- utils
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function el(html) {
    var d = document.createElement('div');
    d.innerHTML = html.trim();
    return d.firstChild;
  }
  function initials(name) {
    var p = name.replace(/[^A-Za-zÀ-ɏ ]/g, '').split(/\s+/).filter(Boolean);
    if (!p.length) return '?';
    return (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase();
  }
  function fmtPct(pct, ps) {
    if (pct == null) return '<span class="est">—</span>';
    var v = (Math.round(pct * 10) / 10) + '%';
    return ps === 'inferred one-vote share' ? '<span class="est">≈</span>' + v : v;
  }
  var KIND_DIR = { player: 'players', coach: 'coaches', team: 'teams' };
  function entURL(kind, slug) { return R + KIND_DIR[kind] + '/' + slug + '.html'; }
  function qURL(slug) { return R + 'questions/' + slug + '.html'; }
  function sURL(season) { return R + 'seasons/' + season + '.html'; }

  var slugmapPromise = null;
  function slugmap() {
    if (!slugmapPromise) slugmapPromise = fetchJSON('slugmap.json');
    return slugmapPromise;
  }

  function headshotURL(nbaId) {
    return 'https://cdn.nba.com/headshots/nba/latest/260x190/' + nbaId + '.png';
  }
  function logoURL(teamId) {
    return 'https://cdn.nba.com/logos/nba/' + teamId + '/global/L/logo.svg';
  }
  // avatar for an entity key using slugmap extras baked into page data
  function avatarHTML(kind, name, opts) {
    opts = opts || {};
    var cls = 'avatar' + (opts.lg ? ' lg' : '') + (kind === 'team' ? ' team' : '');
    var inner = esc(initials(name));
    if (kind === 'player' && opts.nbaId) {
      inner = '<img loading="lazy" src="' + headshotURL(opts.nbaId) + '" alt="" ' +
        'onerror="this.parentNode.textContent=\'' + esc(initials(name)).replace(/'/g, '') + '\'">';
    } else if (kind === 'team' && opts.teamId) {
      inner = '<img loading="lazy" src="' + logoURL(opts.teamId) + '" alt="" ' +
        'onerror="this.parentNode.textContent=\'' + esc(initials(name)).replace(/'/g, '') + '\'">';
    }
    return '<span class="' + cls + '">' + inner + '</span>';
  }

  // entity key -> kind
  function kindOf(key) {
    if (!key) return null;
    if (key[0] === 'p' && key[1] >= '0' && key[1] <= '9') return 'player';
    if (key.slice(0, 2) === 'x-') return 'player';
    if (key.slice(0, 2) === 'c-') return 'coach';
    if (key.slice(0, 2) === 't-') return 'team';
    return null;
  }
  function nbaIdOf(key) {
    return key && key[0] === 'p' && key[1] >= '0' && key[1] <= '9' ? +key.slice(1) : null;
  }

  // link + avatar for an answer, resolved through slugmap (sm)
  function whoHTML(sm, key, text, affil) {
    var kind = kindOf(key);
    var name = key && sm.entDisp[key] ? sm.entDisp[key] : text;
    var av, nm;
    if (kind && sm.entSlug[key]) {
      var extra = {};
      if (kind === 'player') extra.nbaId = nbaIdOf(key);
      if (kind === 'team') extra.teamId = TEAM_IDS[key.slice(2)];
      av = avatarHTML(kind, name, extra);
      nm = '<a class="nm" href="' + entURL(kind, sm.entSlug[key]) + '">' + esc(text) + '</a>';
    } else {
      av = '<span class="avatar">' + esc(initials(text)) + '</span>';
      nm = '<span class="nm">' + esc(text) + '</span>';
    }
    var sub = affil ? ' <span class="sub">' + esc(affil) + '</span>' : '';
    return '<span class="who">' + av + '<span>' + nm + sub + '</span></span>';
  }

  var TEAM_IDS = { ATL: 1610612737, BOS: 1610612738, CLE: 1610612739, NOP: 1610612740, CHI: 1610612741, DAL: 1610612742, DEN: 1610612743, GSW: 1610612744, HOU: 1610612745, LAC: 1610612746, LAL: 1610612747, MIA: 1610612748, MIL: 1610612749, MIN: 1610612750, BKN: 1610612751, NYK: 1610612752, ORL: 1610612753, IND: 1610612754, PHI: 1610612755, PHX: 1610612756, POR: 1610612757, SAC: 1610612758, SAS: 1610612759, OKC: 1610612760, TOR: 1610612761, UTA: 1610612762, MEM: 1610612763, WAS: 1610612764, DET: 1610612765, CHA: 1610612766 };

  var CROWN = '<svg class="crown" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-label="winner"><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-1.5 11h-15L3 8z"/></svg>';

  // one answer row with pct bar; maxPct scales bars within a question block
  function ansRow(sm, a, maxPct) {
    var w = a.pct != null && maxPct ? Math.max(2, a.pct / maxPct * 100) : 0;
    var cls = 'ans' + (a.rank === 1 && a.rt === 'r' ? ' w1' : '') + (a.rt === 'v' ? ' arv' : '');
    return '<div class="' + cls + '">' +
      whoHTML(sm, a.e, a.t, a.affil) +
      (a.rank === 1 && a.rt === 'r' ? CROWN : '') +
      '<span class="barwrap"><span class="bar" style="width:' + w + '%"></span></span>' +
      '<span class="pct">' + fmtPct(a.pct, a.ps) + '</span></div>';
  }

  // question block (list of answers, collapsed past `showN`)
  function answersBlock(sm, answers, showN) {
    showN = showN || 5;
    var maxPct = 0;
    answers.forEach(function (a) { if (a.pct > maxPct) maxPct = a.pct; });
    var head = answers.slice(0, showN).map(function (a) { return ansRow(sm, a, maxPct); }).join('');
    var rest = answers.slice(showN);
    if (!rest.length) return '<div>' + head + '</div>';
    var restHTML = rest.map(function (a) { return ansRow(sm, a, maxPct); }).join('');
    return '<div>' + head +
      '<div class="restwrap" hidden>' + restHTML + '</div>' +
      '<button class="more-btn" onclick="var w=this.previousElementSibling;w.hidden=!w.hidden;' +
      "this.textContent=w.hidden?'Show all " + answers.length + " answers':'Show fewer';\">" +
      'Show all ' + answers.length + ' answers</button></div>';
  }

  function setTitleBits(t) { if (t) document.title = t + ' | NBA GM Survey Tracker'; }

  // ---------------------------------------------------------------- charts
  var SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'];

  function trendChart(container, qdata, sm) {
    // pick top 5 entities by summed share across seasons
    var totals = {}, names = {};
    qdata.seasons.forEach(function (b) {
      b.answers.forEach(function (a) {
        var k = a.e || ('txt:' + a.t);
        totals[k] = (totals[k] || 0) + (a.pct || 0);
        names[k] = a.e && sm.entDisp[a.e] ? sm.entDisp[a.e] : a.t;
      });
    });
    var keys = Object.keys(totals).sort(function (a, b) { return totals[b] - totals[a]; }).slice(0, 5);
    // make sure the latest season's winner is charted even if new on the scene
    var lastBlk = qdata.seasons[qdata.seasons.length - 1];
    lastBlk.answers.forEach(function (a) {
      if (a.rank === 1) {
        var k = a.e || ('txt:' + a.t);
        if (keys.indexOf(k) < 0) { if (keys.length >= 5) keys.pop(); keys.push(k); }
      }
    });
    if (qdata.seasons.length < 3 || !keys.length) return;

    var seasons = qdata.seasons.map(function (b) { return b.season; });
    var series = keys.map(function (k, i) {
      var pts = qdata.seasons.map(function (b) {
        var hit = null;
        b.answers.forEach(function (a) { if ((a.e || ('txt:' + a.t)) === k && a.pct != null) hit = a.pct; });
        return hit;
      });
      return { key: k, name: names[k], color: SERIES[i], pts: pts };
    });

    var W = 720, H = 300, ML = 44, MR = 118, MT = 14, MB = 30;
    var iw = W - ML - MR, ih = H - MT - MB;
    var maxY = 0;
    series.forEach(function (s) { s.pts.forEach(function (v) { if (v > maxY) maxY = v; }); });
    maxY = Math.min(100, Math.ceil(maxY / 20) * 20 + (maxY > 90 ? 0 : 0)) || 20;
    function X(i) { return ML + (seasons.length === 1 ? iw / 2 : i * iw / (seasons.length - 1)); }
    function Y(v) { return MT + ih - v / maxY * ih; }

    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Vote share by season">'];
    // gridlines + y ticks
    for (var g = 0; g <= maxY; g += maxY / 4) {
      svg.push('<line x1="' + ML + '" x2="' + (W - MR) + '" y1="' + Y(g) + '" y2="' + Y(g) + '" stroke="#e1e0d9" stroke-width="1"/>');
      svg.push('<text x="' + (ML - 8) + '" y="' + (Y(g) + 4) + '" text-anchor="end" font-size="11" fill="#898781">' + Math.round(g) + '%</text>');
    }
    // x labels (sparse)
    var step = Math.max(1, Math.ceil(seasons.length / 8));
    seasons.forEach(function (s, i) {
      if (i % step === 0 || i === seasons.length - 1) {
        svg.push('<text x="' + X(i) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="#898781">' + s.slice(2) + '</text>');
      }
    });
    // lines & points
    series.forEach(function (s) {
      var d = '', started = false;
      s.pts.forEach(function (v, i) {
        if (v == null) { started = false; return; }
        d += (started ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1);
        started = true;
      });
      svg.push('<path d="' + d + '" fill="none" stroke="' + s.color + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>');
      s.pts.forEach(function (v, i) {
        if (v != null) svg.push('<circle cx="' + X(i) + '" cy="' + Y(v) + '" r="3" fill="' + s.color + '" stroke="#fcfcfb" stroke-width="2"/>');
      });
    });
    // direct labels at each line's actual end; right-margin group gets collision nudge
    var lastPts = series.map(function (s) {
      for (var i = s.pts.length - 1; i >= 0; i--) if (s.pts[i] != null) return { i: i, y: Y(s.pts[i]), s: s };
      return null;
    }).filter(Boolean);
    var edge = lastPts.filter(function (lp) { return lp.i >= seasons.length - 2; })
                      .sort(function (a, b) { return a.y - b.y; });
    var prevY = -99;
    edge.forEach(function (lp) { lp.ly = Math.max(lp.y, prevY + 14); prevY = lp.ly; });
    lastPts.forEach(function (lp) {
      var nm = lp.s.name.length > 17 ? lp.s.name.slice(0, 16) + '…' : lp.s.name;
      var atEdge = lp.i >= seasons.length - 2;
      var x = atEdge ? W - MR + 8 : Math.min(X(lp.i) + 7, W - MR - 40);
      var y = (atEdge ? lp.ly : Math.max(MT + 10, lp.y - 9)) + 4;
      svg.push('<text x="' + x + '" y="' + y + '" font-size="11.5" font-weight="600" fill="#52514e">' + esc(nm) + '</text>');
    });
    // hover columns
    seasons.forEach(function (s, i) {
      var x0 = i === 0 ? ML : (X(i - 1) + X(i)) / 2;
      var x1 = i === seasons.length - 1 ? W - MR : (X(i) + X(i + 1)) / 2;
      svg.push('<rect class="hcol" data-i="' + i + '" x="' + x0 + '" y="' + MT + '" width="' + (x1 - x0) + '" height="' + ih + '" fill="transparent"/>');
    });
    svg.push('<line class="xhair" x1="0" x2="0" y1="' + MT + '" y2="' + (MT + ih) + '" stroke="#c3c2b7" stroke-width="1" visibility="hidden"/>');
    svg.push('</svg>');

    var legend = '<div class="chart-legend">' + series.map(function (s) {
      return '<span class="li"><span class="sw" style="background:' + s.color + '"></span>' + esc(s.name) + '</span>';
    }).join('') + '</div>';

    var card = el('<div class="card chart-card">' + legend + svg.join('') + '<div class="tooltip"></div></div>');
    container.appendChild(card);

    var tip = card.querySelector('.tooltip');
    var hair = card.querySelector('.xhair');
    var svgEl = card.querySelector('svg');
    card.querySelectorAll('.hcol').forEach(function (rc) {
      rc.addEventListener('mousemove', function (ev) {
        var i = +rc.getAttribute('data-i');
        hair.setAttribute('x1', X(i)); hair.setAttribute('x2', X(i));
        hair.setAttribute('visibility', 'visible');
        var rows = series.map(function (s) {
          if (s.pts[i] == null) return '';
          return '<div class="tt-row"><span class="sw" style="background:' + s.color + '"></span>' +
            esc(s.name) + '<span class="v">' + s.pts[i] + '%</span></div>';
        }).join('');
        tip.innerHTML = '<div class="tt-hed">' + seasons[i] + '</div>' + (rows || '<div class="tt-row">no listed votes</div>');
        tip.style.display = 'block';
        var box = svgEl.getBoundingClientRect();
        var px = X(i) / W * box.width;
        var left = px + 14;
        if (left + 170 > box.width) left = px - 180;
        tip.style.left = left + 'px';
        tip.style.top = (ev.clientY - box.top - 20) + 'px';
      });
      rc.addEventListener('mouseleave', function () {
        tip.style.display = 'none'; hair.setAttribute('visibility', 'hidden');
      });
    });
  }

  function winnerTimeline(qdata, sm) {
    var cells = qdata.seasons.map(function (b) {
      var tops = b.answers.filter(function (a) { return a.rank === 1; });
      if (!tops.length) return '';
      var a = tops[0];
      var kind = kindOf(a.e);
      var name = a.e && sm.entDisp[a.e] ? sm.entDisp[a.e] : a.t;
      var extra = {};
      if (kind === 'player') extra.nbaId = nbaIdOf(a.e);
      if (kind === 'team') extra.teamId = TEAM_IDS[(a.e || '').slice(2)];
      var av = avatarHTML(kind || 'player', name, extra);
      var label = tops.length > 1 ? esc(a.t) + ' +' + (tops.length - 1) : esc(a.t);
      var inner = '<div class="cell">' + av + '<div class="s">' + b.season + '</div>' +
        '<div class="n">' + label + '</div>' +
        '<div class="p">' + (a.pct != null ? a.pct + '%' : '') + '</div></div>';
      var href = kind && sm.entSlug[a.e] ? entURL(kind, sm.entSlug[a.e]) : sURL(b.season);
      return '<a class="yr" href="' + href + '">' + inner + '</a>';
    }).join('');
    return '<div class="timeline">' + cells + '</div>';
  }

  // ---------------------------------------------------------------- pages
  var PAGES = {};

  PAGES.home = function () {
    return Promise.all([fetchJSON('highlights.json'), fetchJSON('entities.json'), slugmap()])
      .then(function (res) {
        var h = res[0], ix = res[1], sm = res[2];
        var st = h.stats;

        var tiles = '<div class="tiles">' +
          [['Seasons', st.seasons], ['Questions', st.questions], ['Results', st.rows.toLocaleString('en-US')],
           ['Players', st.players], ['Coaches', st.coaches]].map(function (t) {
            return '<div class="tile"><div class="v">' + t[1] + '</div><div class="l">' + t[0] + '</div></div>';
          }).join('') + '</div>';

        // ranking box: attendance-tracker style mini table
        function box(title, kicker, headCols, rowsHTML, moreHref, moreLabel) {
          return '<div class="box"><div class="box-head"><span class="t">' + title + '</span>' +
            '<span class="kicker">' + kicker + '</span></div>' +
            '<table class="mtab"><thead><tr>' + headCols + '</tr></thead><tbody>' + rowsHTML + '</tbody></table>' +
            (moreHref ? '<a class="see-all" href="' + moreHref + '">' + (moreLabel || 'See full ranking →') + '</a>' : '') +
            '</div>';
        }
        function whoCell(kind, name, slug, extra, sub) {
          return '<td><a class="who-cell" href="' + entURL(kind, slug) + '">' + avatarHTML(kind, name, extra || {}) +
            '<span>' + esc(name) + (sub ? '<span class="sub">' + esc(sub) + '</span>' : '') + '</span></a></td>';
        }

        var boxes = [];
        boxes.push(box('Most survey mentions', 'ALL QUESTIONS, 2002-03 → ' + h.latestSeason,
          '<th></th><th>Player</th><th class="num">Wins</th><th class="num hi">Mentions ▾</th>',
          h.topPlayers.slice(0, 10).map(function (e, i) {
            return '<tr><td class="rk">' + (i + 1) + '</td>' + whoCell('player', e.name, e.slug, { nbaId: e.nbaId }) +
              '<td class="num">' + e.wins + '</td><td class="num hi">' + e.mentions + '</td></tr>';
          }).join(''), R + 'players.html'));

        var byWins = ix.entities.players.slice().sort(function (a, b) { return b.wins - a.wins; });
        boxes.push(box('No. 1 finish kings', 'TIMES PICKED FIRST IN ANY QUESTION',
          '<th></th><th>Player</th><th class="num">Mentions</th><th class="num hi">Wins ▾</th>',
          byWins.slice(0, 10).map(function (e, i) {
            return '<tr><td class="rk">' + (i + 1) + '</td>' + whoCell('player', e.name, e.slug, { nbaId: e.nbaId }) +
              '<td class="num">' + e.mentions + '</td><td class="num hi">' + e.wins + '</td></tr>';
          }).join(''), R + 'players.html'));

        boxes.push(box('Longest winning streaks', 'SAME QUESTION, CONSECUTIVE SEASONS',
          '<th></th><th>Who</th><th class="num hi">Years ▾</th>',
          h.streaks.slice(0, 10).map(function (s, i) {
            var href = s.kind && s.slug ? entURL(s.kind, s.slug) : qURL(s.qslug);
            return '<tr><td class="rk">' + (i + 1) + '</td><td><a href="' + href + '">' + esc(s.who) +
              '<span class="sub">' + esc(s.q) + '</span></a></td><td class="num hi">' + s.len + '</td></tr>';
          }).join(''), R + 'questions.html', 'Browse all questions →'));

        boxes.push(box('Biggest landslides', 'HIGHEST REPORTED WINNING SHARE',
          '<th></th><th>Who</th><th class="num hi">Share ▾</th>',
          h.landslides.slice(0, 10).map(function (l, i) {
            var name = l.e && sm.entDisp[l.e] ? sm.entDisp[l.e] : l.who;
            var href = l.kind && l.slug ? entURL(l.kind, l.slug) : qURL(l.qslug);
            return '<tr><td class="rk">' + (i + 1) + '</td><td><a href="' + href + '">' + esc(name) +
              '<span class="sub">' + esc(l.q) + ' · ' + l.season + '</span></a></td><td class="num hi">' + l.pct + '%</td></tr>';
          }).join(''), R + 'questions.html', 'Browse all questions →'));

        boxes.push(box('Coach mention kings', 'ALL COACH QUESTIONS',
          '<th></th><th>Coach</th><th class="num">Wins</th><th class="num hi">Mentions ▾</th>',
          h.topCoaches.slice(0, 10).map(function (e, i) {
            return '<tr><td class="rk">' + (i + 1) + '</td>' + whoCell('coach', e.name, e.slug, {}) +
              '<td class="num">' + e.wins + '</td><td class="num hi">' + e.mentions + '</td></tr>';
          }).join(''), R + 'coaches.html'));

        boxes.push(box('Team answer leaders', 'PREDICTIONS & TEAM QUESTIONS',
          '<th></th><th>Team</th><th class="num">Wins</th><th class="num hi">Mentions ▾</th>',
          ix.entities.teams.slice(0, 10).map(function (e, i) {
            return '<tr><td class="rk">' + (i + 1) + '</td>' + whoCell('team', e.name, e.slug, { teamId: e.nbaTeamId }) +
              '<td class="num">' + e.wins + '</td><td class="num hi">' + e.mentions + '</td></tr>';
          }).join(''), R + 'teams.html'));

        // latest winners grouped by section
        var bySec = {};
        h.latestWinners.forEach(function (w) { (bySec[w.section] = bySec[w.section] || []).push(w); });
        var secOrder = ['Players', 'Defense', 'Coaches', 'Rookies & International Players', 'Offseason Moves', 'Predictions', 'Miscellaneous', 'Kia Season Preview', ''];
        var winHTML = '';
        secOrder.forEach(function (sec) {
          if (!bySec[sec]) return;
          winHTML += '<div class="sec-tag">' + (sec || 'Survey') + '</div><div class="wins-grid">';
          winHTML += bySec[sec].map(function (w) {
            var a = w.top[0];
            var kind = kindOf(a.e);
            var name = a.e && sm.entDisp[a.e] ? sm.entDisp[a.e] : a.t;
            var extra = {};
            if (kind === 'player') extra.nbaId = nbaIdOf(a.e);
            if (kind === 'team') extra.teamId = TEAM_IDS[(a.e || '').slice(2)];
            var av = avatarHTML(kind || 'player', name, extra);
            var more = w.top.length > 1 ? ' <span class="note-flag">tie</span>' : '';
            return '<div class="card win-card">' + av +
              '<div><div class="q"><a href="' + qURL(w.slug) + '">' + esc(w.q) + '</a></div>' +
              '<a class="nm" href="' + qURL(w.slug) + '">' + esc(a.t) + more + '</a></div>' +
              '<div class="pc">' + (a.pct != null ? a.pct + '%' : '') + '</div></div>';
          }).join('');
          winHTML += '</div>';
        });

        $app.innerHTML = tiles +
          '<div class="box-grid" style="margin-top:10px">' + boxes.join('') + '</div>' +
          '<div class="section-hed">The ' + h.latestSeason + ' survey <span class="count">winners of all ' + h.latestWinners.length + ' questions</span></div>' + winHTML +
          '<p class="fineprint">Data: NBA.com annual GM Survey (2002-03 to ' + h.latestSeason + '). Percentages as reported by NBA.com; ≈ marks vote shares inferred from “others receiving votes”. GMs cannot vote for their own team or personnel in most categories.</p>';
      });
  };

  PAGES.seasons = function () {
    return fetchJSON('entities.json').then(function (ix) {
      setTitleBits('Seasons');
      $app.innerHTML = '<h1 class="page-title">Survey Seasons</h1>' +
        '<p class="page-sub">Every edition of the NBA.com GM Survey, from ' + ix.seasons[0] + ' to ' + ix.seasons[ix.seasons.length - 1] + '.</p>' +
        '<div class="season-grid">' + ix.seasons.slice().reverse().map(function (s) {
          return '<a href="' + sURL(s) + '">' + s + '<span class="sub">GM Survey</span></a>';
        }).join('') + '</div>';
    });
  };

  PAGES.season = function () {
    return Promise.all([fetchJSON('s/' + P.key + '.json'), slugmap()]).then(function (res) {
      var d = res[0], sm = res[1];
      setTitleBits(d.season + ' NBA GM Survey');
      var bySec = {};
      d.questions.forEach(function (q) { (bySec[q.section] = bySec[q.section] || []).push(q); });
      var secOrder = ['Players', 'Defense', 'Coaches', 'Rookies & International Players', 'Offseason Moves', 'Predictions', 'Miscellaneous', 'Kia Season Preview', ''];
      var html = '';
      secOrder.forEach(function (sec) {
        if (!bySec[sec]) return;
        if (sec) html += '<div class="section-hed">' + esc(sec) + ' <span class="count">' + bySec[sec].length + ' questions</span></div>';
        html += bySec[sec].map(function (q) {
          var src = q.source ? '<span class="src-link"> · <a href="' + esc(q.source) + '" target="_blank" rel="noopener">NBA.com</a></span>' : '';
          var orig = q.original ? '<span class="note-flag" title="Original wording">as asked: “' + esc(q.original) + '”</span>' : '';
          return '<div class="card q-card"><h3><a href="' + qURL(q.slug) + '">' + esc(q.text) + '</a></h3>' +
            '<div class="q-note">' + q.answers.length + ' answers' + src + ' ' + orig + '</div>' +
            answersBlock(sm, q.answers, 5) + '</div>';
        }).join('');
      });
      var seasons = null;
      $app.innerHTML = '<div class="crumbs"><a href="' + R + 'index.html">Home</a> › <a href="' + R + 'seasons.html">Seasons</a> › ' + d.season + '</div>' +
        '<h1 class="page-title">' + d.season + ' GM Survey</h1>' +
        '<p class="page-sub">' + d.questions.length + ' questions. Winners marked with a crown; ≈ marks inferred one-vote shares.</p>' + html;
    });
  };

  PAGES.questions = function () {
    return fetchJSON('entities.json').then(function (ix) {
      setTitleBits('Questions');
      var types = [['player', 'Player questions'], ['team', 'Team questions'], ['coach', 'Coach questions'], ['other', 'Everything else']];
      var html = '<h1 class="page-title">Every Question</h1>' +
        '<p class="page-sub">All ' + ix.questions.length + ' questions the GM Survey has asked since ' + ix.seasons[0] + '. Recurring questions include season-by-season trends.</p>';
      types.forEach(function (t) {
        var qs = ix.questions.filter(function (q) { return q.type === t[0]; })
          .sort(function (a, b) { return b.nSeasons - a.nSeasons || (a.text < b.text ? -1 : 1); });
        if (!qs.length) return;
        html += '<div class="section-hed">' + t[1] + ' <span class="count">' + qs.length + '</span></div><div class="card list-card">';
        html += qs.map(function (q) {
          var latest = q.latestTop && q.latestTop[0] ? esc(q.latestTop[0].t) : '';
          return '<a class="ent-row" href="' + qURL(q.slug) + '"><span style="min-width:0"><span class="nm">' + esc(q.text) + '</span><br>' +
            '<span class="meta">' + (q.nSeasons > 1 ? q.nSeasons + ' seasons · ' + q.first + ' – ' + q.last : 'asked once · ' + q.first) +
            (latest ? ' · last winner: ' + latest : '') + '</span></span>' +
            '<span class="right big">' + q.nSeasons + '×</span></a>';
        }).join('');
        html += '</div>';
      });
      $app.innerHTML = html;
    });
  };

  PAGES.question = function () {
    return Promise.all([fetchJSON('q/' + P.key + '.json'), slugmap()]).then(function (res) {
      var d = res[0], sm = res[1];
      setTitleBits(d.text);
      var span = d.seasons.length > 1 ? d.seasons[0].season + ' – ' + d.seasons[d.seasons.length - 1].season + ' · ' + d.seasons.length + ' seasons' : 'asked in ' + d.seasons[0].season;
      var html = '<div class="crumbs"><a href="' + R + 'index.html">Home</a> › <a href="' + R + 'questions.html">Questions</a></div>' +
        '<h1 class="page-title" style="font-size:clamp(24px,3.6vw,36px);text-transform:none;font-family:var(--body);font-weight:700">' + esc(d.text) + '</h1>' +
        '<p class="page-sub">' + span + '</p><div id="chartslot"></div>';
      if (d.seasons.length > 1) {
        html += '<div class="section-hed">Winner by season</div>' + winnerTimeline(d, sm);
      }
      html += '<div class="section-hed">Season by season</div>';
      html += d.seasons.slice().reverse().map(function (b) {
        var src = b.source ? '<span class="src-link"> · <a href="' + esc(b.source) + '" target="_blank" rel="noopener">NBA.com</a></span>' : '';
        var orig = b.original ? ' <span class="note-flag">as asked: “' + esc(b.original) + '”</span>' : '';
        return '<div class="card q-card"><h3><a href="' + sURL(b.season) + '">' + b.season + '</a></h3>' +
          '<div class="q-note">' + b.answers.length + ' answers' + src + orig + '</div>' +
          answersBlock(sm, b.answers, 5) + '</div>';
      }).join('');
      $app.innerHTML = html;
      var slot = document.getElementById('chartslot');
      if (d.type !== 'other') trendChart(slot, d, sm);
    });
  };

  function entityList(kind, title, sub) {
    return fetchJSON('entities.json').then(function (ix) {
      setTitleBits(title);
      var list = ix.entities[kind === 'player' ? 'players' : 'coaches'];
      var TOP = 50;
      function row(e, i) {
        var extra = kind === 'player' ? { nbaId: e.nbaId } : {};
        return '<a class="ent-row" href="' + entURL(kind, e.slug) + '">' +
          '<span class="rankn">' + (i + 1) + '</span>' + avatarHTML(kind, e.name, extra) +
          '<span><span class="nm">' + esc(e.name) + '</span><br><span class="meta">' + e.first + ' – ' + e.last + ' · ' + e.wins + ' wins · ' + e.nQ + ' questions</span></span>' +
          '<span class="right"><span class="big">' + e.mentions + '</span><br><span class="meta">mentions</span></span></a>';
      }
      var head = list.slice(0, TOP).map(row).join('');
      var rest = list.slice(TOP).map(function (e, i) { return row(e, i + TOP); }).join('');
      $app.innerHTML = '<h1 class="page-title">' + title + '</h1><p class="page-sub">' + sub.replace('{n}', list.length) + '</p>' +
        '<div class="card list-card">' + head + '<div class="restwrap" hidden>' + rest + '</div></div>' +
        (list.length > TOP ? '<button class="more-btn" style="margin-top:10px" onclick="var w=document.querySelector(\'.restwrap\');w.hidden=!w.hidden;this.textContent=w.hidden?\'Show all ' + list.length + '\':\'Show top 50\'">Show all ' + list.length + '</button>' : '');
    });
  }
  PAGES.players = function () { return entityList('player', 'Players', 'Every player GMs have ever voted for, ranked by total survey mentions. Top 50 shown — {n} in all.'); };
  PAGES.coaches = function () { return entityList('coach', 'Coaches', 'Head coaches, assistants and future-coach picks, ranked by total survey mentions. Top 50 shown — {n} in all.'); };

  PAGES.teams = function () {
    return fetchJSON('entities.json').then(function (ix) {
      setTitleBits('Teams');
      var list = ix.entities.teams.slice().sort(function (a, b) { return a.name < b.name ? -1 : 1; });
      $app.innerHTML = '<h1 class="page-title">Teams</h1>' +
        '<p class="page-sub">Every franchise: survey questions answered with the team, plus every vote its players and coaches received while there.</p>' +
        '<div class="team-grid">' + list.map(function (e) {
          return '<a href="' + entURL('team', e.slug) + '"><img loading="lazy" src="' + logoURL(e.nbaTeamId) + '" alt="">' +
            '<div class="nm">' + esc(e.name) + '</div><div class="meta" style="font-size:11.5px;color:var(--muted)">' + e.mentions + ' team answers</div></a>';
        }).join('') + '</div>';
    });
  };

  function histBlocks(sm, rows, openN) {
    var byQ = {};
    var order = [];
    rows.forEach(function (r) {
      if (!byQ[r.q]) { byQ[r.q] = []; order.push(r.q); }
      byQ[r.q].push(r);
    });
    order.sort(function (a, b) { return byQ[b].length - byQ[a].length; });
    return order.map(function (q, qi) {
      var rs = byQ[q].slice().sort(function (a, b) { return b.endYear - a.endYear; });
      var wins = rs.filter(function (r) { return r.rank === 1; }).length;
      var maxPct = 0;
      rs.forEach(function (r) { if (r.pct > maxPct) maxPct = r.pct; });
      var inner = rs.map(function (r) {
        var w = r.pct != null && maxPct ? Math.max(2, r.pct / maxPct * 100) : 0;
        return '<div class="hist-row"><a class="ssn" href="' + sURL(r.season) + '">' + r.season + '</a>' +
          '<span class="rk' + (r.rank === 1 && r.rt === 'r' ? ' r1' : '') + '">' + (r.rt === 'v' ? 'votes' : '#' + r.rank) + '</span>' +
          '<span class="barwrap"><span class="bar" style="width:' + w + '%"></span></span>' +
          '<span class="pv">' + fmtPct(r.pct, r.ps === undefined ? null : r.ps) + '</span></div>';
      }).join('');
      return '<details class="hist-block"' + (qi < openN ? ' open' : '') + '><summary>' +
        '<svg class="chev" width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5l8 7-8 7z"/></svg>' +
        '<a href="' + qURL(rs[0].slug) + '">' + esc(q) + '</a>' +
        '<span class="n">' + rs.length + ' seasons' + (wins ? ' · ' + wins + ' wins' : '') + '</span></summary>' +
        '<div class="rows">' + inner + '</div></details>';
    }).join('');
  }

  function entityPage(kind) {
    return Promise.all([fetchJSON('e/' + P.key + '.json'), slugmap()]).then(function (res) {
      var d = res[0], sm = res[1];
      setTitleBits(d.name);
      var extra = {};
      if (kind === 'player' && d.nbaId) extra.nbaId = d.nbaId;
      if (kind === 'team') extra.teamId = d.nbaTeamId;
      var av = avatarHTML(kind, d.name, Object.assign({ lg: true }, extra));
      var listName = { player: 'players', coach: 'coaches', team: 'teams' }[kind];
      var crumbs = '<div class="crumbs"><a href="' + R + 'index.html">Home</a> › <a href="' + R + listName + '.html">' +
        listName[0].toUpperCase() + listName.slice(1) + '</a> › ' + esc(d.name) + '</div>';
      var subBits = [];
      if (d.first) subBits.push('In GM Surveys ' + d.first + ' – ' + d.last);
      if (kind === 'team' && d.eraNames && d.eraNames.length > 1) subBits.push('as ' + d.eraNames.join(', '));
      var head = crumbs + '<div class="ent-head">' + av + '<div class="titles"><h1 class="page-title">' + esc(d.name) + '</h1>' +
        '<div class="sub">' + subBits.join(' · ') + '</div></div></div>';
      var tiles = '<div class="tiles">' +
        '<div class="tile"><div class="v">' + d.mentions + '</div><div class="l">Mentions</div></div>' +
        '<div class="tile"><div class="v">' + d.wins + '</div><div class="l">No. 1 finishes</div></div>' +
        '<div class="tile"><div class="v">' + d.nQ + '</div><div class="l">Questions</div></div>' +
        (d.first ? '<div class="tile"><div class="v">' + (parseInt(d.last) - parseInt(d.first) + 1) + '</div><div class="l">Year span</div></div>' : '') +
        '</div>';
      var html = head + tiles;
      if (d.rows && d.rows.length) {
        html += '<div class="section-hed">' + (kind === 'team' ? 'Team answers' : 'Survey history') + ' <span class="count">' + d.rows.length + ' results</span></div>';
        html += histBlocks(sm, d.rows, 3);
      }
      if (kind === 'team' && d.memberVotes && d.memberVotes.length) {
        var byWho = {};
        var order = [];
        d.memberVotes.forEach(function (m) {
          if (!byWho[m.e]) { byWho[m.e] = { name: m.name, kind: m.kind, slug: m.slug, rows: [] }; order.push(m.e); }
          byWho[m.e].rows.push(m);
        });
        order.sort(function (a, b) { return byWho[b].rows.length - byWho[a].rows.length; });
        html += '<div class="section-hed">Votes received while with the team <span class="count">' + d.memberVotes.length + ' results · ' + order.length + ' people</span></div><div class="card list-card">';
        var TOPM = 25;
        function mrow(k, i) {
          var e = byWho[k];
          var wins = e.rows.filter(function (r) { return r.rank === 1; }).length;
          var ex = e.kind === 'player' ? { nbaId: nbaIdOf(k) } : {};
          return '<a class="ent-row" href="' + entURL(e.kind, e.slug) + '">' +
            '<span class="rankn">' + (i + 1) + '</span>' + avatarHTML(e.kind, e.name, ex) +
            '<span><span class="nm">' + esc(e.name) + '</span><br><span class="meta">' + (e.kind === 'coach' ? 'coach · ' : '') + wins + ' wins while here</span></span>' +
            '<span class="right"><span class="big">' + e.rows.length + '</span><br><span class="meta">mentions</span></span></a>';
        }
        html += order.slice(0, TOPM).map(mrow).join('');
        if (order.length > TOPM) {
          html += '<div class="restwrap" hidden>' + order.slice(TOPM).map(function (k, i) { return mrow(k, i + TOPM); }).join('') + '</div>';
        }
        html += '</div>';
        if (order.length > TOPM) {
          html += '<button class="more-btn" style="margin-top:10px" onclick="var w=this.previousElementSibling.querySelector(\'.restwrap\');w.hidden=!w.hidden;this.textContent=w.hidden?\'Show all ' + order.length + '\':\'Show top 25\'">Show all ' + order.length + '</button>';
        }
      }
      $app.innerHTML = html;
    });
  }
  PAGES.player = function () { return entityPage('player'); };
  PAGES.coach = function () { return entityPage('coach'); };
  PAGES.team = function () { return entityPage('team'); };

  // ---------------------------------------------------------------- search
  function initSearch() {
    var input = document.getElementById('q');
    var out = document.getElementById('qresults');
    if (!input) return;
    var idx = null;
    function deacc(s) { return s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
    function build(ix) {
      var items = [];
      ix.entities.players.forEach(function (e) { items.push({ n: e.name, k: 'player', u: entURL('player', e.slug), m: e.mentions, id: e.nbaId }); });
      ix.entities.coaches.forEach(function (e) { items.push({ n: e.name, k: 'coach', u: entURL('coach', e.slug), m: e.mentions }); });
      ix.entities.teams.forEach(function (e) { items.push({ n: e.name, k: 'team', u: entURL('team', e.slug), m: e.mentions + 500, tid: e.nbaTeamId }); });
      ix.questions.forEach(function (q) { items.push({ n: q.text, k: 'question', u: qURL(q.slug), m: q.nSeasons }); });
      ix.seasons.forEach(function (s) { items.push({ n: s + ' GM Survey', k: 'season', u: sURL(s), m: 1 }); });
      items.forEach(function (it) { it.d = deacc(it.n); });
      return items;
    }
    input.addEventListener('focus', function () {
      if (!idx) idx = fetchJSON('entities.json').then(build);
    });
    input.addEventListener('input', function () {
      var v = deacc(input.value.trim());
      if (v.length < 2) { out.classList.remove('open'); return; }
      idx.then(function (items) {
        var hits = items.filter(function (it) { return it.d.indexOf(v) >= 0; });
        hits.sort(function (a, b) {
          var sa = (a.d.indexOf(v) === 0 || a.d.indexOf(' ' + v) > 0) ? 0 : 1;
          var sb = (b.d.indexOf(v) === 0 || b.d.indexOf(' ' + v) > 0) ? 0 : 1;
          return sa - sb || b.m - a.m;
        });
        out.innerHTML = hits.slice(0, 12).map(function (it) {
          var av = it.k === 'player' && it.id ? avatarHTML('player', it.n, { nbaId: it.id }) :
                   it.k === 'team' ? avatarHTML('team', it.n, { teamId: it.tid }) : '';
          return '<a href="' + it.u + '">' + av + '<span>' + esc(it.n) + '</span><span class="kind">' + it.k + '</span></a>';
        }).join('') || '<a>No matches</a>';
        out.classList.add('open');
      });
    });
    document.addEventListener('click', function (e) {
      if (!out.contains(e.target) && e.target !== input) out.classList.remove('open');
    });
  }

  // ---------------------------------------------------------------- boot
  initSearch();
  if (PAGES[P.kind]) {
    PAGES[P.kind]().catch(function (err) {
      $app.innerHTML = '<div class="card" style="margin-top:30px"><b>Could not load data.</b><br>' +
        '<span style="color:var(--muted);font-size:13px">' + esc(err.message) + '</span></div>';
    });
  }
})();
