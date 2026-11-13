import hashlib
import hmac
from datetime import date, timedelta
from unittest.mock import patch, Mock
import pytest
from app.extensions import db
from app.models import (Assinatura, EventoAssinatura, WebhookEntrega, Produto, Plano, Modulo,
                        PlanoModulo, UsuarioCentral, Cobranca, Auditoria, WebhookTentativa)
from app.schemas import PlanoInput, ProdutoInput
from app.security import passwords, service_token
from app.services import assinatura_service as service
from app.services.catalogo_service import save
from app.services.webhook_service import dispatch_one, signed_headers, resend
from app.services.entitlement_service import effective
from app.services.cobranca_service import create_charge, pay, maintenance


def create(client, app):
    response = client.post('/api/v1/assinaturas', json=app.test_ids, headers=app.test_headers)
    assert response.status_code == 201, response.json
    return response.json['id']


def test_health_auth_and_scope(client, app):
    assert client.get('/api/v1/health').status_code == 200
    assert client.get('/api/v1/produtos').status_code == 401
    response = client.get('/api/v1/produtos', headers=app.test_headers)
    assert response.status_code == 200
    assert 'webhook_secret' not in str(response.json)
    product = Produto(codigo='OUTRO', nome='Outro')
    db.session.add(product)
    db.session.commit()
    headers = {'Authorization': 'Bearer ' + service_token(product)}
    identifier = create(client, app)
    assert client.get(f'/api/v1/assinaturas/{identifier}', headers=headers).status_code == 404
    assert client.post('/api/v1/assinaturas', headers=headers, json=app.test_ids).status_code == 403


def test_lifecycle_and_logical_delete(client, app):
    identifier = create(client, app)
    endpoint = f"/api/v1/entitlements/{app.test_ids['cliente_id']}/PROPOSTAS"
    assert client.get(endpoint, headers=app.test_headers).json['acesso_produto'] is True
    for status in ['ATIVA', 'SUSPENSA', 'ATIVA', 'BLOQUEADA', 'ATIVA', 'CANCELADA', 'EXCLUIDA']:
        response = client.patch(f'/api/v1/assinaturas/{identifier}/status',
            headers=app.test_headers, json={'status': status, 'motivo': 'Teste de ciclo'})
        assert response.status_code == 200, response.json
        assert response.json['acesso_produto'] == (status == 'ATIVA')
    assert db.session.get(Assinatura, identifier) is not None
    assert len(list(db.session.scalars(db.select(EventoAssinatura)))) == 8
    assert len(list(db.session.scalars(db.select(WebhookEntrega)))) == 8


def test_single_plan_modules_and_duplicate(client, app):
    identifier = create(client, app)
    assert client.post('/api/v1/assinaturas', json=app.test_ids, headers=app.test_headers).status_code == 409
    for action, body in [('plano', {'plano_id': app.test_ids['plano_id']}),
                          ('modulos', {'modulo_id': 1, 'liberado': True})]:
        assert client.patch(f'/api/v1/assinaturas/{identifier}/{action}', json=body, headers=app.test_headers).status_code == 422
    with pytest.raises(service.BusinessError):
        save(Plano, PlanoInput, {'produto_id': app.test_ids['produto_id'], 'codigo': 'NOVO', 'nome': 'Novo'})
    db.session.rollback()
    product = db.session.get(Produto, app.test_ids['produto_id'])
    with pytest.raises(service.BusinessError):
        save(Produto, ProdutoInput, {'codigo': 'PROPOSTAS', 'nome': product.nome,
             'permite_multiplos_planos': True}, product.id)


def test_limits_schema(client, app):
    identifier = create(client, app)
    response = client.patch(f'/api/v1/assinaturas/{identifier}/limites',
        json={'limites': {'usuarios': 3, 'propostas_mes': 100}}, headers=app.test_headers)
    assert response.json['limites'] == {'usuarios': 3, 'propostas_mes': 100}
    assert client.patch(f'/api/v1/assinaturas/{identifier}/limites', json={'limites': {'usuarios': -1}}, headers=app.test_headers).status_code == 422
    assert client.post('/api/v1/assinaturas', json={**app.test_ids, 'intruso': 1}, headers=app.test_headers).status_code == 422


def test_future_product_upgrade_dependency_downgrade(app):
    product = Produto(codigo='FUTURO', nome='Futuro', permite_multiplos_planos=True, permite_modulos=True)
    db.session.add(product)
    db.session.flush()
    basic, full = Plano(produto_id=product.id, codigo='BASE', nome='Base'), Plano(produto_id=product.id, codigo='TOTAL', nome='Total')
    base = Modulo(produto_id=product.id, codigo='BASE', nome='Base')
    dependent = Modulo(produto_id=product.id, codigo='DEP', nome='Dependente', depende_de=['BASE'])
    db.session.add_all([basic, full, base, dependent])
    db.session.flush()
    db.session.add_all([PlanoModulo(plano_id=full.id, modulo_id=base.id), PlanoModulo(plano_id=full.id, modulo_id=dependent.id)])
    obj = service.create({'cliente_id': app.test_ids['cliente_id'], 'produto_id': product.id, 'plano_id': basic.id})
    service.change_plan(obj, full.id)
    assert len(effective(obj)['modulos']) == 2
    with pytest.raises(service.BusinessError):
        service.change_module(obj, base.id, False)
    service.change_plan(obj, basic.id)
    assert effective(obj)['modulos'] == []
    db.session.commit()


def test_signed_webhook_retry(app, client):
    create(client, app)
    with patch('app.services.webhook_service.validate_destination'), patch('requests.Session.post', return_value=Mock(status_code=503)):
        assert dispatch_one()
    entry = db.session.scalar(db.select(WebhookEntrega))
    assert entry.status == 'FALHA' and entry.tentativas == 1
    resend(entry)
    db.session.commit()
    with patch('app.services.webhook_service.validate_destination'), patch('requests.Session.post', return_value=Mock(status_code=200)) as send:
        assert dispatch_one()
        kwargs = send.call_args.kwargs
        stamp = kwargs['headers']['X-LiveSun-Timestamp']
        expected = hmac.new(('h' * 40).encode(), stamp.encode() + b'.' + kwargs['data'], hashlib.sha256).hexdigest()
        assert kwargs['headers']['X-LiveSun-Signature'] == 'sha256=' + expected
        assert kwargs['allow_redirects'] is False
    assert entry.status == 'ENTREGUE' and entry.tentativas == 2
    assert db.session.scalar(db.select(db.func.count()).select_from(WebhookTentativa)) == 2


def test_billing_and_expiry(app, client):
    identifier = create(client, app)
    charge = create_charge({'assinatura_id': identifier, 'competencia': '2026-11', 'valor': 50,
                            'vencimento': date.today() - timedelta(days=1)})
    db.session.commit()
    maintenance()
    assert charge.status == 'ATRASADA'
    pay(charge)
    db.session.commit()
    assert charge.status == 'PAGA' and charge.data_pagamento
    obj = db.session.get(Assinatura, identifier)
    obj.data_fim = date.today() - timedelta(days=1)
    db.session.commit()
    maintenance()
    assert obj.status == 'EXPIRADA'


def login(client, role='superadmin'):
    user = UsuarioCentral(nome=role, email=role+'@example.com', perfil=role, senha_hash=passwords.hash('secure-password-123'))
    db.session.add(user)
    db.session.commit()
    assert client.post('/login', data={'email': user.email, 'senha': 'secure-password-123'}).status_code == 302


def test_panel_pages(client, app):
    identifier = create(client, app)
    login(client)
    for path in ['/', '/cadastros/clientes', '/cadastros/produtos', '/cadastros/planos', '/cadastros/modulos',
                 '/cadastros/usuarios', '/assinaturas', '/assinaturas/nova', f'/assinaturas/{identifier}',
                 '/cobrancas', '/webhooks', '/auditoria', '/configuracoes', '/cadastros/clientes/novo',
                 f"/cadastros/planos/{app.test_ids['plano_id']}/editar"]:
        response = client.get(path)
        assert response.status_code == 200, (path, response.data[:200])
    html = client.get(f'/assinaturas/{identifier}').get_data(as_text=True)
    assert 'Alterar plano imediatamente' not in html
    assert 'Módulos comerciais' not in html


@pytest.mark.parametrize('role', ['auditor', 'suporte', 'financeiro'])
def test_rbac(client, app, role):
    identifier = create(client, app)
    login(client, role)
    assert client.get('/cadastros/clientes/novo').status_code == 403
    assert client.post(f'/assinaturas/{identifier}/status', data={'status': 'EXCLUIDA', 'motivo': 'Teste'}).status_code == 403
    assert client.get('/').status_code == 200


def test_csrf(client, app):
    app.config['WTF_CSRF_ENABLED'] = True
    assert client.post('/login', data={'email': 'x', 'senha': 'y'}).status_code == 400


def test_secret_redaction(app):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    from app.services.auditoria_service import audit
    audit(product, 'TESTE')
    db.session.commit()
    entry = db.session.scalar(db.select(Auditoria).where(Auditoria.acao == 'TESTE'))
    assert 'webhook_secret' not in entry.novo