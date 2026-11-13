import re

import pytest
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db
from app.models import UsuarioCentral
from app.security import passwords


@pytest.mark.parametrize('origin', ['same-origin', 'missing', 'foreign', 'invalid-token'])
def test_https_login_behind_proxy_preserves_csrf(origin):
    app = create_app({'APP_ENV': 'production', 'TESTING': True,
        'DB_ENGINE': 'sqlite', 'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 's'*48, 'JWT_SECRET': 'j'*48,
        'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'TRUST_PROXY': True, 'WEBHOOK_ALLOW_LOCAL_HTTP': False,
        'WTF_CSRF_ENABLED': True, 'RATELIMIT_ENABLED': False})
    browser = app.test_client()
    headers = {'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'central.example'}
    with app.app_context():
        db.create_all()
        db.session.add(UsuarioCentral(nome='Teste HTTPS', email='https@example.com',
            perfil='superadmin', ativo=True, senha_hash=passwords.hash('test-password')))
        db.session.commit()
    try:
        page = browser.get('/login', base_url='http://central.example', headers=headers)
        assert page.status_code == 200
        assert 'Secure;' in page.headers['Set-Cookie']
        # O navegador só envia Referer de mesmo site se a política permitir.
        policy = page.headers['Referrer-Policy']
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        if origin in ('same-origin', 'invalid-token') and policy == 'same-origin':
            headers['Referer'] = 'https://central.example/login'
        elif origin == 'foreign':
            headers['Referer'] = 'https://foreign.example/login'
        response = browser.post('/login', base_url='http://central.example', headers=headers,
            data={'email': 'https@example.com', 'senha': 'test-password',
                  'csrf_token': 'invalid' if origin == 'invalid-token' else token})
        assert response.status_code == (302 if origin == 'same-origin' else 400)
        assert app.config['WTF_CSRF_SSL_STRICT'] is True
    finally:
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()