from datetime import timedelta
from unittest.mock import Mock, patch
import pytest
import requests
from app.extensions import db
from app.models import (Assinatura, WebhookEntrega, SolicitacaoCadastro, NotificacaoAcesso,
                        TentativaNotificacaoAcesso)
from app.models.base import now
from app.services import assinatura_service as service
from app.services.notificacao_acesso_service import process_one
from app.services.email_service import send_access_email


def create(app):
    app.config.update(ACCESS_EMAIL_ENABLED=True, BREVO_API_KEY='test-only', BREVO_SENDER_EMAIL='sender@example.com')
    obj = service.create(app.test_ids)
    db.session.commit()
    return obj


def delivered():
    for row in db.session.scalars(db.select(WebhookEntrega)):
        row.status = 'ENTREGUE'
    db.session.commit()


def test_disabled_no_backfill(app):
    service.create(app.test_ids); db.session.commit()
    assert db.session.query(NotificacaoAcesso).count() == 0
    app.config['ACCESS_EMAIL_ENABLED'] = True
    assert not process_one()


def test_creation_sends_once_after_delivery(app):
    obj = create(app)
    assert not process_one()
    delivered()
    notice = db.session.query(NotificacaoAcesso).one(); notice.proxima_tentativa = now()
    db.session.commit()
    with patch('app.services.notificacao_acesso_service.send_access_email', return_value=('ACEITA_BREVO', None)) as mail:
        assert process_one()
        assert not process_one()
        mail.assert_called_once()
        html = mail.call_args.args[2]
        assert 'TRIAL' in html and 'PROPOSTAS' in html
        assert obj.trial_ate.strftime('%d/%m/%Y') in html
        assert '/auth/login' in html and 'test-only' not in html
    assert db.session.query(TentativaNotificacaoAcesso).one().resultado == 'ACEITA_BREVO'


def test_new_registration_waits_for_link(app):
    obj = create(app); delivered()
    row = SolicitacaoCadastro(produto_id=obj.produto_id, empresa_origem='100', evento_origem='cad_'+'a'*32,
        razao_social='Teste', cnpj_cpf='52998224725', email='test@example.com', responsavel='Teste',
        assinatura_id=obj.id, cliente_id=obj.cliente_id, status='VINCULO_PENDENTE')
    db.session.add(row); db.session.commit()
    with patch('app.services.notificacao_acesso_service.send_access_email', return_value=('ACEITA_BREVO', None)) as mail:
        assert not process_one(); mail.assert_not_called()
        row.status = 'VINCULADA'
        db.session.query(NotificacaoAcesso).one().proxima_tentativa = now()
        db.session.commit()
        assert process_one(); mail.assert_called_once()


def test_activation_reactivation_only_approved_events(app):
    obj = create(app)
    service.change_status(obj, 'ATIVA', 'Ativar teste'); db.session.commit()
    service.change_status(obj, 'SUSPENSA', 'Suspender teste'); db.session.commit()
    service.change_status(obj, 'ATIVA', 'Reativar teste'); db.session.commit()
    assert db.session.query(NotificacaoAcesso).count() == 3
    delivered()
    with patch('app.services.notificacao_acesso_service.send_access_email', return_value=('ACEITA_BREVO', None)) as mail:
        for _ in range(4): process_one()
        assert mail.call_count == 1  # notificações de liberação ultrapassadas canceladas


def test_revoked_event_cancelled_and_uncertain_never_retried(app):
    obj = create(app); delivered()
    with patch('app.services.notificacao_acesso_service.send_access_email', return_value=('INCERTO', 'COMUNICACAO')) as mail:
        assert process_one(); assert not process_one(); mail.assert_called_once()
    assert db.session.query(NotificacaoAcesso).one().status == 'INCERTO'


def test_expired_sending_lease_is_uncertain(app):
    create(app)
    item = db.session.query(NotificacaoAcesso).one()
    item.status, item.lease_ate, item.tentativas = 'ENVIANDO', now()-timedelta(seconds=1), 1
    db.session.add(TentativaNotificacaoAcesso(notificacao_id=item.id, numero=1))
    db.session.commit()
    with patch('app.services.notificacao_acesso_service.send_access_email') as mail:
        assert not process_one(); mail.assert_not_called()
    assert item.status == 'INCERTO'


@pytest.mark.parametrize('code,result', [(201,'ACEITA_BREVO'),(400,'FALHA'),(429,'FALHA_TEMPORARIA'),(500,'INCERTO')])
def test_brevo_results(app, code, result):
    app.config.update(BREVO_API_KEY='test-only', BREVO_SENDER_EMAIL='sender@example.com')
    with patch('app.services.email_service.requests.Session') as factory:
        http = factory.return_value.__enter__.return_value
        http.post.return_value = Mock(status_code=code)
        assert send_access_email('test@example.com', 'Teste', '<p>Teste</p>')[0] == result
        assert http.trust_env is False


def test_brevo_timeout_no_leak(app, caplog):
    app.config.update(BREVO_API_KEY='test-only', BREVO_SENDER_EMAIL='sender@example.com')
    with patch('app.services.email_service.requests.Session') as factory:
        factory.return_value.__enter__.return_value.post.side_effect = requests.Timeout('SECRET')
        assert send_access_email('test@example.com', 'Teste', '<p>Teste</p>')[0] == 'INCERTO'
    assert 'SECRET' not in caplog.text


def test_revoked_before_worker_suppresses_email(app):
    obj = create(app); delivered()
    service.change_status(obj, 'SUSPENSA', 'Acesso revogado'); db.session.commit()
    with patch('app.services.notificacao_acesso_service.send_access_email') as mail:
        assert process_one(); mail.assert_not_called()
    assert db.session.query(NotificacaoAcesso).one().status == 'CANCELADA'


def test_safe_temporary_failure_retry_limited(app):
    create(app); delivered()
    with patch('app.services.notificacao_acesso_service.send_access_email', return_value=('FALHA_TEMPORARIA', 'LIMITE_PROVEDOR')) as mail:
        for _ in range(3):
            item = db.session.query(NotificacaoAcesso).one()
            item.proxima_tentativa = now(); db.session.commit()
            assert process_one()
        assert not process_one()
        assert mail.call_count == 3
    assert db.session.query(NotificacaoAcesso).one().status == 'FALHA_TEMPORARIA'
    assert db.session.query(TentativaNotificacaoAcesso).count() == 3


def test_bad_product_url_does_not_send(app):
    obj = create(app); delivered()
    obj.produto.url_producao = 'javascript:alert(1)'; db.session.commit()
    with patch('app.services.notificacao_acesso_service.send_access_email') as mail:
        assert process_one(); mail.assert_not_called()
    assert db.session.query(TentativaNotificacaoAcesso).one().categoria == 'URL_PRODUTO_INVALIDA'