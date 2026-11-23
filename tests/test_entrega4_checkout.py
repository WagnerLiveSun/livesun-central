import base64
import hashlib
import hmac
import json
import time
from datetime import date
from unittest.mock import patch
import pytest
from app.extensions import db
from app.models import Assinatura, Cobranca, NotificacaoAcesso, EventoAssinatura, Cliente
from app.services import assinatura_service
from app.services.asaas_service import (AsaasClient, apply_payment, start_propostas_contratacao,
                                       configure_subscription, receive_public, BusinessError)
from app.services.notificacao_acesso_service import process_one
from test_comercial_phase import subscription
from test_central import login


def token(customer, stamp=None):
    data = {'cliente_id': customer, 'produto': 'PROPOSTAS', 'iat': int(time.time()) if stamp is None else stamp}
    encoded = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    signature = hmac.new(('h'*40).encode(), ('checkout-propostas:'+encoded).encode(), hashlib.sha256).hexdigest()
    return encoded+'.'+signature


def payment(status='CONFIRMED'):
    return {'id':'pay_checkout', 'subscription':'sub_test', 'dueDate':date.today().isoformat(),
            'value':80, 'status':status, 'invoiceUrl':'https://sandbox.asaas.com/i/pay_checkout'}


def test_signed_checkout_rejects_id_only_tampering_and_expired(app, client):
    assert client.get('/contratar/propostas?cliente=1').status_code == 401
    assert client.get('/contratar/propostas?token='+token(app.test_ids['cliente_id'], 1)).status_code == 401
    assert client.get('/contratar/propostas?token='+token(app.test_ids['cliente_id'])+'a').status_code == 401
    response = client.get('/contratar/propostas?token='+token(app.test_ids['cliente_id']))
    assert response.status_code == 302 and 'token' not in response.location
    assert client.get(response.location).status_code == 200


def test_checkout_cannot_change_customer_with_url_or_form(app, client):
    obj = subscription(app)
    other = Cliente(codigo_externo='other', razao_social='Outro', email_principal='other@example.com')
    db.session.add(other)
    db.session.commit()
    client.get('/contratar/propostas?token='+token(obj.cliente_id))
    response = client.post('/contratar/propostas?cliente_id='+str(other.id), data={
        'cliente_id': other.id, 'periodicidade':'mensal', 'valor':'0.01'})
    assert response.status_code == 302
    assert db.session.query(Assinatura).filter_by(cliente_id=other.id).count() == 0


@pytest.mark.parametrize('period,value', [('mensal',80), ('anual',600)])
def test_new_contract_monthly_annual_and_repeated_request(app, period, value):
    configured = subscription(app)
    customer = Cliente(codigo_externo='new-contract', razao_social='Novo', email_principal='new@example.com')
    db.session.add(customer)
    db.session.commit()
    obj, created = start_propostas_contratacao(customer.id, period)
    db.session.commit()
    assert created and obj.plano.valor_mensal == value and obj.status == 'TRIAL'
    assert obj.asaas_ambiente == configured.asaas_ambiente
    repeated, created = start_propostas_contratacao(customer.id, period)
    assert not created and repeated.id == obj.id


@pytest.mark.parametrize('period', ['mensal','anual'])
def test_existing_trial_reused_without_reset_and_repeated_checkout(app, period):
    obj = subscription(app)
    obj.asaas_habilitado = False
    obj.asaas_subscription_id = None
    before = (obj.id, obj.status, obj.trial_ate, obj.data_inicio)
    db.session.commit()
    result, created = start_propostas_contratacao(obj.cliente_id, period)
    db.session.commit()
    assert not created and (result.id, result.status, result.trial_ate, result.data_inicio) == before
    assert result.plano.periodicidade == period
    again, created = start_propostas_contratacao(obj.cliente_id, period)
    assert not created and again.id == result.id
    assert db.session.query(Assinatura).count() == 1


def test_environment_url_and_customer_id_cannot_cross(app):
    obj = subscription(app)
    app.config['ASAAS_API_URL'] = 'https://api.asaas.com/v3'
    assert AsaasClient(obj.produto.config_asaas).base == 'https://api-sandbox.asaas.com/v3'
    assert AsaasClient(obj.produto.config_asaas).key == 'fake'
    obj.asaas_subscription_id = None
    obj.asaas_customer_id = 'cus_sandbox'
    obj.produto.config_asaas.ambiente = 'producao'
    with pytest.raises(BusinessError):
        configure_subscription(obj, 'producao', 'UNDEFINED')


def test_financial_email_once_and_failure_never_rolls_back_payment(app):
    obj = subscription(app)
    app.config.update(ACCESS_EMAIL_ENABLED=True, EMAIL_TEST_RECIPIENTS=['test@example.com'])
    apply_payment(obj, payment())
    db.session.commit()
    apply_payment(obj, payment('RECEIVED'))
    db.session.commit()
    assert db.session.query(NotificacaoAcesso).count() == 1
    with patch('app.services.email_service.send_template_email', side_effect=RuntimeError) as mail:
        assert process_one()
        assert not process_one()
        mail.assert_called_once()
    assert db.session.query(Cobranca).one().status == 'PAGA'
    assert db.session.query(NotificacaoAcesso).one().status == 'INCERTO'
    assert obj.status == 'TRIAL'


def test_sandbox_email_real_recipient_blocked(app):
    obj = subscription(app)
    app.config['ACCESS_EMAIL_ENABLED'] = True
    apply_payment(obj, payment())
    db.session.commit()
    with patch('app.services.email_service.send_template_email') as mail:
        assert process_one()
        mail.assert_not_called()
    assert db.session.query(NotificacaoAcesso).one().status == 'CANCELADA'


def test_manual_release_trial_audited_once(app, client):
    obj = subscription(app)
    app.config.update(ACCESS_EMAIL_ENABLED=True, EMAIL_TEST_RECIPIENTS=['test@example.com'])
    apply_payment(obj, payment())
    db.session.commit()
    login(client)
    assert client.post(f'/assinaturas/{obj.id}/liberar').status_code == 302
    assert client.post(f'/assinaturas/{obj.id}/liberar').status_code == 302
    assert obj.status == 'ATIVA' and obj.liberado_por.nome and obj.liberado_em
    assert db.session.query(EventoAssinatura).filter_by(tipo_evento='ASSINATURA_ATIVADA').count() == 1
    assert db.session.query(NotificacaoAcesso).count() == 2  # pagamento + liberação, sem segundo fluxo


@pytest.mark.parametrize('remote_status', ['PENDING', 'OVERDUE'])
def test_created_and_overdue_email_outbox(app, remote_status):
    obj = subscription(app)
    app.config.update(ACCESS_EMAIL_ENABLED=True, EMAIL_TEST_RECIPIENTS=['test@example.com'])
    apply_payment(obj, payment(remote_status))
    db.session.commit()
    apply_payment(obj, payment(remote_status))
    db.session.commit()
    with patch('app.services.email_service.send_template_email', return_value=('ACEITA_BREVO', None)) as mail:
        assert process_one()
        assert not process_one()
        mail.assert_called_once()


def test_renewal_paid_keeps_active(app):
    obj = subscription(app)
    obj.status = 'ATIVA'
    apply_payment(obj, payment())
    db.session.commit()
    assert obj.status == 'ATIVA'


def test_production_sandbox_billing_does_not_release_real_access(app, client):
    obj = subscription(app)
    apply_payment(obj, payment())
    db.session.commit()
    login(client)
    app.config['APP_ENV'] = 'production'
    gateway = AsaasClient(obj.produto.config_asaas)
    assert gateway.base == 'https://api-sandbox.asaas.com/v3'
    assert start_propostas_contratacao(obj.cliente_id, 'mensal')[0].id == obj.id
    response = client.post(f'/assinaturas/{obj.id}/liberar', base_url='https://localhost')
    assert response.status_code == 422
    assert obj.status == 'TRIAL'


def test_worker_existing_command_processes_email(app):
    with patch('app.services.cobranca_service.maintenance'), \
         patch('app.services.webhook_service.recover_deliveries'), \
         patch('app.services.cadastro_service.pull_pending'), \
         patch('app.services.webhook_service.dispatch_one', return_value=False), \
         patch('app.services.asaas_service.process_one', return_value=False), \
         patch('app.services.purga_service.process_one', return_value=False), \
         patch('app.services.cadastro_service.deliver_one', return_value=False), \
         patch('app.services.notificacao_acesso_service.process_one', return_value=True) as email:
        result = app.test_cli_runner().invoke(args=['worker', '--once'])
        assert result.exit_code == 0
        email.assert_called_once()