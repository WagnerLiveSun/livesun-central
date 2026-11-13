import importlib.util
from pathlib import Path
from dotenv import dotenv_values
from cryptography.fernet import Fernet
from app import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_environment_generation_is_private_and_idempotent(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('generate_render', ROOT/'scripts/gerar_environment_render.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    path = module.generate()
    before = path.read_bytes()
    module.generate()
    assert path.read_bytes() == before
    values = dotenv_values(path)
    assert values['APP_ENV'] == 'production'
    assert values['DB_ENGINE'] == 'postgresql'
    assert values['SECRET_KEY'] != values['JWT_SECRET']
    assert len(values['SECRET_KEY']) >= 32
    Fernet(values['ENCRYPTION_KEY'].encode())
    assert values['WEBHOOK_ALLOW_LOCAL_HTTP'] == 'false'
    assert '127.0.0.1' not in values['DATABASE_URL']
    assert 'RATELIMIT_STORAGE_URI' not in values


def test_render_manifest_uses_production_hosts_and_manual_deploy():
    source = (ROOT/'render.yaml').read_text(encoding='utf-8')
    assert "autoDeployTrigger: 'off'" in source
    assert source.count("autoDeployTrigger: 'off'") == 1
    assert 'propostas.livesun.com.br,app.livesun.com.br' in source
    assert 'value: postgresql' in source
    assert 'plan: free' in source
    assert 'preDeployCommand:' not in source
    assert 'type: worker' not in source
    assert 'plan: starter' not in source
    assert 'scripts/with_ssh_tunnel.py web' in source
    assert source.count('runtime: docker') == 1
    assert 'key: RATELIMIT_STORAGE_URI' not in source


def test_production_factory_boots_with_shared_rate_limit_configuration():
    # Constrói os componentes sem acessar um banco ou Redis real.
    app = create_app({'APP_ENV':'production', 'DB_ENGINE':'postgresql',
        'DATABASE_URL':'postgresql+psycopg://test:test@db.example/central?sslmode=require',
        'SECRET_KEY':'s'*48, 'JWT_SECRET':'j'*48, 'ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'RATELIMIT_STORAGE_URI':'redis://redis.example:6379/0',
        'WEBHOOK_ALLOW_LOCAL_HTTP':False, 'TRUST_PROXY':True})
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert not app.debug