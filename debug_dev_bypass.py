import os, sys
sys.path.insert(0, os.path.abspath('.'))
import app as app_module
from app import app, db

app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test-secret')
with app.app_context():
    db.drop_all()
    db.create_all()
    user = app_module.User(username='phase8-user', email='phase8@example.com', password=app_module.bcrypt.generate_password_hash('secret123').decode('utf-8'), mt5_account='12345678')
    db.session.add(user)
    db.session.commit()

    app_module.app_settings.developer_mt5_accounts = {'12345678'}
    user = db.session.get(app_module.User, user.id)
    ok, message = app_module.validate_license_for_bot_start(user)
    print('ok=', ok)
    print('message=', message)
