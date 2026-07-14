from app import app, db
print('app_type', type(app))
print('has_before_first_request', hasattr(app, 'before_first_request'))
print('has_app_context', hasattr(app, 'app_context'))
print('dir_subset', [n for n in dir(app) if 'before' in n or 'app_context' in n][:20])
with app.app_context():
    print('inside app context ok')
    print('engine', db.engine)
    try:
        rows = db.engine.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
        print('tables', [r[0] for r in rows])
    except Exception as e:
        print('db_err', type(e).__name__, e)
