from app import app, db
from sqlalchemy import text

print('routes:', sorted(r.rule for r in app.url_map.iter_rules()))
with app.app_context():
    with db.engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"))
        tables = [r[0] for r in rows]
print('tables:', tables)
