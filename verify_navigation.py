import os
import sys

sys.path.insert(0, os.getcwd())

import app as app_module

app_module.app.config.update(
    TESTING=True,
    SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    SECRET_KEY="test-secret",
)

client = app_module.app.test_client()

with app_module.app.app_context():
    app_module.db.drop_all()
    app_module.db.create_all()
    user = app_module.User(
        username="navtester",
        email="navtester@example.com",
        password=app_module.bcrypt.generate_password_hash("secret123").decode("utf-8"),
    )
    app_module.db.session.add(user)
    app_module.db.session.commit()

client.post(
    "/login",
    data={"email": "navtester@example.com", "password": "secret123"},
    follow_redirects=True,
)

routes = [
    "/dashboard",
    "/bot-control",
    "/markets",
    "/ai-signals",
    "/mt5",
    "/history",
    "/settings",
]

for path in routes:
    response = client.get(path)
    print(f"{path} -> {response.status_code}")

logout_response = client.get("/logout", follow_redirects=True)
print(f"/logout -> {logout_response.status_code}")
