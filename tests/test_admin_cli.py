from pydantic import ValidationError
import pytest
from app.extensions import db
from app.models import UsuarioCentral
from app.schemas import UserInput
from app.security import passwords


@pytest.mark.parametrize('password', ['x', 'suporte', 'short-pass'])
def test_short_password_is_accepted_without_exposing_input(app, password):
    result = app.test_cli_runner().invoke(args=['create-admin'],
        input=f'admin@example.com\nAdministrador\n{password}\n{password}\n')
    assert result.exit_code == 0, result.output
    assert 'Superadmin criado.' in result.output
    password_prompts = result.output.split('Senha:', 1)[1]
    assert password not in password_prompts
    assert 'Traceback' not in result.output
    user = db.session.scalar(db.select(UsuarioCentral).filter_by(email='admin@example.com'))
    assert user.perfil == 'superadmin'
    assert passwords.verify(user.senha_hash, password)
    response = app.test_client().post('/login', data={'email': user.email, 'senha': password})
    assert response.status_code == 302


def test_invalid_email_does_not_dump_password(app):
    result = app.test_cli_runner().invoke(args=['create-admin'],
        input='invalid-email\nAdministrador\nvalid-test-password-123\nvalid-test-password-123\n')
    assert result.exit_code == 1
    assert 'Confira os campos: email' in result.output
    assert 'Traceback' not in result.output
    assert 'valid-test-password-123' not in result.output
    assert db.session.scalar(db.select(db.func.count()).select_from(UsuarioCentral)) == 0


def test_duplicate_admin_email_is_handled(app):
    runner = app.test_cli_runner()
    data = 'admin@example.com\nAdministrador\nvalid-test-password-123\nvalid-test-password-123\n'
    assert runner.invoke(args=['create-admin'], input=data).exit_code == 0
    result = runner.invoke(args=['create-admin'], input=data)
    assert result.exit_code == 1
    assert 'Já existe um operador' in result.output
    assert 'Traceback' not in result.output
    assert 'valid-test-password-123' not in result.output
    assert db.session.scalar(db.select(db.func.count()).select_from(UsuarioCentral)) == 1


def test_schema_error_string_hides_password():
    invalid_password = 'private-test-' * 12
    with pytest.raises(ValidationError) as captured:
        UserInput.model_validate({'nome': 'Teste', 'email': 'test@example.com',
                                  'perfil': 'superadmin', 'senha': invalid_password})
    assert invalid_password not in str(captured.value)


def test_empty_password_is_rejected():
    with pytest.raises(ValidationError):
        UserInput.model_validate({'nome': 'Teste', 'email': 'test@example.com',
                                  'perfil': 'superadmin', 'senha': ''})


def test_cloud_bootstrap_is_one_time_and_never_exposes_password(app,monkeypatch):
    from app.cli import bootstrap_admin
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL','cloud@example.com')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','private-bootstrap')
    bootstrap_admin()
    first=db.session.scalar(db.select(UsuarioCentral))
    original=first.senha_hash
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','do-not-replace')
    bootstrap_admin()
    assert db.session.scalar(db.select(db.func.count()).select_from(UsuarioCentral))==1
    assert first.senha_hash==original