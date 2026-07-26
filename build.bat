@echo off
python scripts\build_site_data.py
python scripts\generate_entity_pages.py
echo Done. Review, then git add/commit/push.
