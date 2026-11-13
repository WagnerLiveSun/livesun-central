import json
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import pytest
from app.extensions import db
from app.models import Produto, Plano, Assinatura, WebhookEntrega, Auditoria
from app.schemas import PlanoInput
from app.services import assinatura_service as service
from app.services.catalogo_service import save
from app.services.reconciliacao_service import reconcile_all
from app.services.webhook_service import validate_destination
from app.services.entitlement_service import effective
from app.security import service_token, SafeJSONFormatter


def make(app):
    obj = service.create(app.test_ids)
    db.session.commit()
    return obj


def test_plan_limit_changes_notify_existing(app):
    obj = make(app)
    plan = obj.plano
    save(Plano, PlanoInput, {'produto_id': plan.produto_id, 'codigo': plan.codigo, 'nome': plan.nome,
        'limite_usuarios': 8, 'limite_personalizado_json': {'propostas_mes': 200}}, plan.id)
    db.session.commit()
    assert effective(obj)['limites'] == {'usuarios': 8, 'propostas_mes': 200}
    assert db.session.scalar(db.select(db.func.count()).select_from(WebhookEntrega)) == 2


def test_reconciliation_repairs_snapshot(app):
    obj = make(app)
    response = Mock(status_code=200, content=b'{}')
    response.json.return_value = {'entitlements': {}}
    with patch('app.services.reconciliacao_service.validate_destination'), patch('requests.Session.get', return_value=response):
        result = reconcile_all(True)
    assert result == {'verificadas': 1, 'divergentes': 1, 'indisponiveis': 0}
    delivery = db.session.scalar(db.select(WebhookEntrega).order_by(WebhookEntrega.id.desc()))
    assert delivery.payload['reconciliacao'] is True
    assert delivery.payload['entitlements']['status'] == obj.status


@pytest.mark.parametrize('url', ['http://propostas.livesun.com.br/hook', 'https://localhost/hook',
    'https://propostas.livesun.com.br:444/hook', 'https://user:password@propostas.livesun.com.br/hook',
    'https://evil.example/hook'])
def test_ssrf_rejects_untrusted_urls(app, url):
    with pytest.raises(service.BusinessError):
        validate_destination(url)


def test_ssrf_rejects_private_dns(app):
    with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
        with pytest.raises(service.BusinessError):
            validate_destination('https://propostas.livesun.com.br/hook')


def test_token_rotation_and_expiry(app, client):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    expired = service_token(product, hours=-1)
    assert client.get('/api/v1/produtos', headers={'Authorization': 'Bearer '+expired}).status_code == 401
    product.token_version += 1
    db.session.commit()
    assert client.get('/api/v1/produtos', headers=app.test_headers).status_code == 401


def test_transaction_rollback_does_not_queue(app):
    service.create(app.test_ids)
    db.session.rollback()
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura)) == 0
    assert db.session.scalar(db.select(db.func.count()).select_from(WebhookEntrega)) == 0


def test_terminal_state_and_old_subscription_selection(app, client):
    old = make(app)
    service.change_status(old, 'CANCELADA', 'Cancelamento solicitado')
    db.session.commit()
    new = make(app)
    response = client.get(f"/api/v1/entitlements/{new.cliente_id}/PROPOSTAS", headers=app.test_headers)
    assert response.json['assinatura_id'] == new.id
    with pytest.raises(Exception):
        service.change_status(old, 'ATIVA', 'Tentativa concorrente com outra assinatura')
        db.session.commit()
    db.session.rollback()
    service.change_status(new, 'EXCLUIDA', 'Exclusão lógica')
    with pytest.raises(service.BusinessError):
        service.change_status(new, 'ATIVA', 'Não pode reativar excluída')


def test_structured_logs_ignore_sensitive_args():
    import logging
    record = logging.LogRecord('app', logging.ERROR, '', 1, 'password=%s', ('SECRET',), None)
    assert 'SECRET' not in SafeJSONFormatter().format(record)


def test_missing_webhook_secret_is_observable_failure(app):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    product.webhook_secret = None
    db.session.commit()
    make(app)
    from app.services.webhook_service import dispatch_one
    assert dispatch_one()
    entry = db.session.scalar(db.select(WebhookEntrega))
    assert entry.status == 'CONFIGURACAO'
    assert entry.tentativas == 1


def test_local_webhook_requires_development_opt_in_and_allowlist(app):
    local = 'http://127.0.0.1:5000/webhooks/assinatura'
    with pytest.raises(service.BusinessError):
        validate_destination(local)
    app.config.update(WEBHOOK_ALLOW_LOCAL_HTTP=True, WEBHOOK_ALLOWED_HOSTS=['127.0.0.1'])
    validate_destination(local)
    for url in ['http://localhost:5000/webhooks/assinatura', 'http://192.168.1.1:5000/hook',
                'http://127.0.0.1.evil.example/hook', 'http://user:secret@127.0.0.1/hook',
                'http://127.0.0.1/hook?secret=value']:
        with pytest.raises(service.BusinessError):
            validate_destination(url)
    app.config['APP_ENV'] = 'production'
    with pytest.raises(service.BusinessError):
        validate_destination(local)