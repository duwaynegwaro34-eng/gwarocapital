import os
import sys
sys.path.insert(0, os.getcwd())

print('CWD:', os.getcwd())
print('.env exists:', os.path.exists('.env'))

from config import settings
print('Loaded DEVELOPER_MT5_ACCOUNTS:', settings.developer_mt5_accounts)
assert '1200088332' in settings.developer_mt5_accounts, 'Developer MT5 account not loaded from .env'

import app as app_module
print('App settings DEVELOPER_MT5_ACCOUNTS:', app_module.app_settings.developer_mt5_accounts)
assert '1200088332' in app_module.app_settings.developer_mt5_accounts, 'App did not load developer MT5 accounts'

app_module.app.config.update(TESTING=True, SECRET_KEY='test-secret')
client = app_module.app.test_client()
with app_module.app.app_context():
    app_module.db.drop_all()
    app_module.db.create_all()
    user = app_module.User(
        username='dev-user',
        email='dev@example.com',
        password=app_module.bcrypt.generate_password_hash('secret123').decode('utf-8'),
        mt5_account='1200088332',
    )
    app_module.db.session.add(user)
    app_module.db.session.commit()

login_resp = client.post('/login', data={'email': 'dev@example.com', 'password': 'secret123'}, follow_redirects=True)
print('Login status:', login_resp.status_code)
print('Login dashboard content found:', b'Dashboard' in login_resp.data)

start_resp = client.post('/api/bot/start', json={'bot_id': 'hybrid_bot'}, headers={'X-CSRF-Token': 'ignored-in-testing'})
print('Start bot status:', start_resp.status_code)
print('Start bot response:', start_resp.get_json())

if start_resp.is_json:
    payload = start_resp.get_json()
    assert payload.get('ok') is True, f"Bot did not start: {payload}"
    assert payload.get('message') == 'Developer Mode: License check bypassed.' or 'Developer Mode: License check bypassed.' in payload.get('message', ''), f"Unexpected message: {payload.get('message')}"
else:
    raise AssertionError('Start bot response not JSON')

print('Developer bypass verification succeeded.')
