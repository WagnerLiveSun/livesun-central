from datetime import date
from unittest.mock import Mock, patch

import pytest

from app.extensions import db
from app.models import Cobranca, OperacaoAsaas
from app.security import encrypt
from app.services.asaas_service import AsaasClient, BusinessError, configure_subscription, process_one
from app.services.assinatura_service import create
from test_comercial_phase import subscription


def test_sandbox_worker_in_production_uses_sandbox_url_and_creates_charge(app):
    obj = subscription(app)
    obj.produto.codigo = 'COMERCIAL'
    obj.status = 'ATIVA'
    obj.asaas_subscription_id = None
    obj.asaas_customer_id = None
    obj.cliente.asaas_sandbox_customer_id = None
    obj.cliente.asaas_producao_customer_id = 'production-customer-must-not-be-used'
    obj.asaas_habilitado = False
    obj.plano.valor_mensal = 100
    configure_subscription(obj, 'sandbox', 'PIX')
    db.session.commit()
    operation_id = db.session.scalar(db.select(OperacaoAsaas.id))
    app.config['APP_ENV'] = 'production'
    requests_seen = []

    def request(_session, method, url, **kwargs):
        requests_seen.append((method, url, kwargs))
        response = Mock(status_code=200, content=b'{}')
        if method == 'GET' and url.endswith('/subscriptions'):
            response.json.return_value = {'data': [], 'hasMore': False}
        elif method == 'GET' and url.endswith('/customers'):
            response.json.return_value = {'data': [], 'hasMore': False}
        elif method == 'POST' and url.endswith('/customers'):
            response.json.return_value = {'id': 'sandbox-customer'}
        elif method == 'POST' and url.endswith('/subscriptions'):
            assert kwargs['json']['customer'] == 'sandbox-customer'
            assert kwargs['json']['value'] == 100
            response.json.return_value = {'id': 'sandbox-subscription'}
        elif method == 'GET' and url.endswith('/subscriptions/sandbox-subscription'):
            response.json.return_value = {'id': 'sandbox-subscription', 'customer': 'sandbox-customer', 'status': 'ACTIVE'}
        elif method == 'PUT' and url.endswith('/subscriptions/sandbox-subscription'):
            response.json.return_value = {'id': 'sandbox-subscription'}
        elif method == 'GET' and url.endswith('/subscriptions/sandbox-subscription/payments'):
            response.json.return_value = {'data': [{'id': 'sandbox-payment', 'subscription': 'sandbox-subscription',
                'dueDate': date.today().isoformat(), 'value': 100, 'status': 'PENDING'}], 'hasMore': False}
        else:
            raise AssertionError((method, url))
        return response

    with patch('requests.Session.request', autospec=True, side_effect=request):
        assert process_one()
    assert db.session.get(OperacaoAsaas, operation_id).status == 'CONCLUIDA'
    charge = db.session.scalar(db.select(Cobranca))
    assert charge.asaas_ambiente == 'sandbox' and charge.valor == 100
    assert requests_seen and all(url.startswith('https://api-sandbox.asaas.com/v3/') for _, url, _ in requests_seen)


def test_sandbox_does_not_use_production_global_credential(app):
    obj = subscription(app)
    app.config.update(APP_ENV='production', ASAAS_API_URL='https://api.asaas.com/v3', ASAAS_API_KEY='production-secret')
    with pytest.raises(BusinessError):
        AsaasClient(obj.produto.config_asaas)


def test_unknown_environment_and_cross_environment_binding_are_rejected(app):
    obj = subscription(app)
    obj.produto.config_asaas.ambiente = 'invalid'
    with pytest.raises(BusinessError):
        AsaasClient(obj.produto.config_asaas)