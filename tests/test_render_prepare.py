import importlib.util
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_prepare', ROOT/'scripts/render_prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.fixture
def production_env(monkeypatch):
    values = {'SECRET_KEY': 's'*48, 'JWT_SECRET': 'j'*48,
              'ENCRYPTION_KEY': Fernet.generate_key().decode(),
              'APP_ENV': 'production', 'RATELIMIT_STORAGE_URI': 'redis://redis.example:6379/0',
              'WEBHOOK_ALLOW_LOCAL_HTTP': 'false'}
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_preparation_environment_valid(production_env):
    prepare.validate_environment()


def test_preparation_does_not_require_redis(production_env, monkeypatch):
    monkeypatch.delenv('RATELIMIT_STORAGE_URI', raising=False)
    prepare.validate_environment()


@pytest.mark.parametrize('key,value,expected', [
    ('SECRET_KEY', '', 'SECRET_KEY'),
    ('JWT_SECRET', '', 'JWT_SECRET'),
    ('ENCRYPTION_KEY', '', 'ENCRYPTION_KEY'),
    ('SECRET_KEY', 'short', 'app_configuration'),
    ('ENCRYPTION_KEY', 'not-a-real-key', 'encryption_key'),
])
def test_preparation_reports_safe_stage(production_env, monkeypatch, capsys, key, value, expected):
    monkeypatch.setenv(key, value)
    with pytest.raises(prepare.PreparationError):
        prepare.validate_environment()
    error = capsys.readouterr().err
    assert 'preparation_stage_failed' in error
    assert f'"stage": "{expected}"' in error
    assert 'not-a-real-key' not in error


@pytest.mark.parametrize('name', ['migrations', 'schema_validation', 'seed_propostas', 'bootstrap_admin'])
def test_stage_never_prints_exception_or_credentials(name, capsys):
    def fail():
        raise RuntimeError('postgresql://user:PRIVATE_PASSWORD@host/database PRIVATE_TOKEN')
    with pytest.raises(prepare.PreparationError):
        prepare.stage(name, fail, 'Mensagem fixa segura.')
    captured = capsys.readouterr()
    assert name in captured.err
    assert 'PRIVATE' not in captured.out + captured.err


def test_stage_returns_result():
    assert prepare.stage('example', lambda: 42, 'Mensagem fixa.') == 42