from app import app, db, User
from werkzeug.security import generate_password_hash

app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test-secret')

with app.app_context():
    db.drop_all()
    db.create_all()
    user = User(username='tester', email='tester@example.com', password=generate_password_hash('secret123'))
    db.session.add(user)
    db.session.commit()

client = app.test_client()
reg = client.post('/register', data={'username': 'new', 'email': 'new@example.com', 'password': 'pass'}, follow_redirects=True)
login = client.post('/login', data={'email': 'tester@example.com', 'password': 'secret123'}, follow_redirects=True)
dashboard = client.get('/dashboard', follow_redirects=True)
logout = client.get('/logout', follow_redirects=True)

print('register', reg.status_code, 'dashboard-in-register' if b'dashboard' in reg.data.lower() else 'no-dashboard')
print('login', login.status_code, 'dashboard-in-login' if b'dashboard' in login.data.lower() else 'no-dashboard')
print('dashboard', dashboard.status_code, 'login-in-dashboard' if b'login' in dashboard.data.lower() else 'no-login')
print('logout', logout.status_code, 'login-in-logout' if b'login' in logout.data.lower() else 'no-login')
