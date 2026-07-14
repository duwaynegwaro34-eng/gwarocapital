from app import app, db, User, bcrypt

app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:', SECRET_KEY='test-secret')

with app.app_context():
    db.drop_all()
    db.create_all()
    user = User(username='tester', email='tester@example.com', password=bcrypt.generate_password_hash('secret123').decode('utf-8'))
    db.session.add(user)
    db.session.commit()

client = app.test_client()
register_response = client.post('/register', data={'username': 'new', 'email': 'new@example.com', 'password': 'pass'}, follow_redirects=True)
login_response = client.post('/login', data={'email': 'tester@example.com', 'password': 'secret123'}, follow_redirects=True)
dashboard_response = client.get('/dashboard', follow_redirects=True)
logout_response = client.get('/logout', follow_redirects=True)

print('register', register_response.status_code)
print('login', login_response.status_code)
print('dashboard', dashboard_response.status_code)
print('logout', logout_response.status_code)
