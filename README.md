# NBA GM Survey Tracker

Every answer to every question in the NBA.com annual GM Survey (2002-03 to 2025-26),
browsable by season, question, player, team and coach. Static site, no framework,
served from `/docs` via GitHub Pages.

Live (once deployed): https://jsierrahoopshype.github.io/nba-gm-survey/

## Repo layout

```
data/
  gm_survey.csv           <- THE source of truth. Add new survey rows here.
  player_ids.csv          <- answer name -> NBA person id (for headshots). Committed.
  aliases.json            <- spelling variants -> canonical name (merges entities)
  question_types.json     <- generated; per-question player/team/coach/other typing
scripts/
  build_site_data.py      <- CSV -> docs/data/*.json  (stdlib only)
  generate_entity_pages.py<- JSONs -> all HTML pages + sitemap (stdlib only)
  update_player_ids.py    <- regenerates player_ids.csv (needs: pip install nba_api)
docs/                     <- the published site (GitHub Pages root)
  assets/style.css, app.js
  data/                   <- prebuilt JSON (entities, highlights, per q/season/entity)
  index.html, seasons/, questions/, players/, teams/, coaches/
build.bat                 <- runs both build scripts on Windows
```

## First deploy (Windows Command Prompt)

1. Create the empty repo `nba-gm-survey` on github.com under `jsierrahoopshype`
   (Public, no README).
2. If you ever want Claude cloud sessions to push here later: add the repo to the
   Claude GitHub App installation (Settings > GitHub Apps), same as nba-attendance.
3. Unzip this folder, then:

```
cd nba-gm-survey
git init
git add .
git commit -m "NBA GM Survey Tracker v1"
git branch -M main
git remote add origin https://github.com/jsierrahoopshype/nba-gm-survey.git
git push -u origin main
```

4. On GitHub: Settings > Pages > Deploy from a branch > `main` / `/docs` > Save.
5. Site appears at `https://jsierrahoopshype.github.io/nba-gm-survey/` in a minute or two.

## Updating when a new survey drops (e.g. 2026-27)

1. Append the new rows to `data/gm_survey.csv` (same columns as today).
2. Run `build.bat` (or the two python commands it contains).
3. If the build warns about brand-new player names, run
   `pip install nba_api` once, then `python scripts/update_player_ids.py`,
   then `build.bat` again. Genuinely non-NBA names (Euro players) staying
   unmatched is normal; they get initials avatars.
4. Commit and push. Done — every page, chart and highlight regenerates.

## Notes

- Headshots come straight off `cdn.nba.com/headshots/nba/latest/260x190/{id}.png`,
  team logos off `cdn.nba.com/logos/nba/{teamId}/global/L/logo.svg`, loaded
  client-side by the visitor's browser (no proxy needed; these are public CDN
  images, not the blocked stats API). To switch to the nba-headshots pipeline,
  change `headshotURL()` at the top of `docs/assets/app.js`.
- `≈` before a percentage marks NBA.com's "others receiving votes" shares that
  were inferred as one-vote fractions in the source CSV.
- Franchise history is unified: Seattle -> OKC, New Jersey -> Brooklyn,
  Bobcats -> Hornets, NO/OKC Hornets -> Pelicans. Season rows show the era name.
- To point the site at a custom domain later, update `BASE` in
  `scripts/generate_entity_pages.py` and rerun it (canonicals + sitemap).
