import pytest
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db


@pytest.mark.parametrize('storage', [None, '', 'memory://'])
def test_production_without_redis_keeps_login_and_api_limits(monkeypatch, storage):
    if storage is None:
        monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)
    else:
        monkeypatch.setenv('RATELIMIT_STORAGE_URI', storage)
    app = create_app({'APP_ENV': 'production', 'TESTING': True,
        'DB_ENGINE': 'sqlite', 'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 's'*48, 'JWT_SECRET': 'j'*48,
        'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'WEBHOOK_ALLOW_LOCAL_HTTP': False, 'WTF_CSRF_ENABLED': False})
    assert app.config['RATELIMIT_STORAGE_URI'] == 'memory://'
    assert app.config.get('RATELIMIT_ENABLED', True)
    with app.app_context():
        db.create_all()
        try:
            client = app.test_client()
            login_url = next(rule.rule for rule in app.url_map.iter_rules()
                             if rule.endpoint == 'admin.login_view')
            for _ in range(5):
                assert client.post(login_url, base_url='https://central.example',
                                   data={'email': '', 'senha': ''}).status_code != 429
            assert client.post(login_url, base_url='https://central.example', data={}).status_code == 429
            for _ in range(120):
                assert client.get('/api/v1/health', base_url='https://central.example').status_code != 429
            assert client.get('/api/v1/health', base_url='https://central.example').status_code == 429
        finally:
            db.session.remove()
            db.drop_all()
            db.engine.dispose()