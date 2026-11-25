import pytest
from datetime import date, datetime, timezone
from app.extensions import db
from app.models import Produto, Plano, Modulo, Assinatura, SolicitacaoCadastro, CredencialServico, WebhookEntrega, GatewayAlternativo, Auditoria
from app.security import issue_product_credential
from app.services.cadastro_service import receive
from test_autocadastro import payload
from test_central import login


def product():
    obj = Produto(codigo='PRD_2BF8172', nome='Clínicas duplicado')
    db.session.add(obj)
    db.session.commit()
    return obj


def test_superadmin_can_delete_unused_product_with_exact_confirmation_and_audit(app, client):
    obj = product()
    identifier = obj.id
    login(client)
    assert f'/cadastros/produtos/{identifier}/excluir' in client.get('/cadastros/produtos').get_data(as_text=True)
    assert 'PRD_2BF8172' in client.get(f'/cadastros/produtos/{identifier}/excluir').get_data(as_text=True)
    assert client.post(f'/cadastros/produtos/{identifier}/excluir', data={'confirmacao': 'EXCLUIR'}).status_code == 422
    assert db.session.get(Produto, identifier) is not None
    assert client.post(f'/cadastros/produtos/{identifier}/excluir', data={'confirmacao': 'PRD_2BF8172'}).status_code == 302
    assert db.session.get(Produto, identifier) is None
    event = db.session.scalar(db.select(Auditoria).filter_by(entidade='produtos', entidade_id=identifier, acao='PRODUTO_EXCLUIDO'))
    assert event and event.anterior['codigo'] == 'PRD_2BF8172'


@pytest.mark.parametrize('dependency', ['plano', 'modulo', 'assinatura', 'solicitacao', 'credencial', 'webhook', 'gateway', 'url', 'secret', 'oficial'])
def test_product_with_dependencies_cannot_be_deleted(app, client, dependency):
    obj = product()
    if dependency == 'plano':
        db.session.add(Plano(produto_id=obj.id, codigo='TESTE', nome='Teste'))
    elif dependency == 'modulo':
        db.session.add(Modulo(produto_id=obj.id, codigo='TESTE', nome='Teste'))
    elif dependency == 'assinatura':
        db.session.add(Assinatura(produto_id=obj.id, cliente_id=app.test_ids['cliente_id'], plano_id=app.test_ids['plano_id'], data_inicio=date.today()))
    elif dependency == 'solicitacao':
        receive(obj, payload(123, 'cad_' + 'b' * 32))
    elif dependency == 'credencial':
        issue_product_credential(obj)
    elif dependency == 'webhook':
        db.session.add(WebhookEntrega(produto_id=obj.id, evento_id='cad_' + 'c' * 32, url_destino='https://example.com', payload={}, proxima_tentativa=datetime.now(timezone.utc).replace(tzinfo=None)))
    elif dependency == 'gateway':
        db.session.add(GatewayAlternativo(produto_id=obj.id, nome='Teste', ambiente='sandbox', url_api='https://example.com', credenciais_criptografadas='test'))
    elif dependency == 'url':
        obj.url_producao = 'https://example.com'
    elif dependency == 'secret':
        obj.webhook_secret = 'secret-encrypted'
    elif dependency == 'oficial':
        obj.codigo = 'CLINICAS'
    db.session.commit()
    identifier, code = obj.id, obj.codigo
    login(client)
    response = client.get(f'/cadastros/produtos/{identifier}/excluir')
    assert response.status_code == 200
    assert 'Não é possível excluir' in response.get_data(as_text=True)
    response = client.post(f'/cadastros/produtos/{identifier}/excluir', data={'confirmacao': code})
    assert response.status_code == 422
    assert db.session.get(Produto, identifier) is not None


def test_only_superadmin_can_delete_product(app, client):
    obj = product()
    login(client, 'comercial')
    assert f'/cadastros/produtos/{obj.id}/excluir' not in client.get('/cadastros/produtos').get_data(as_text=True)
    assert client.get(f'/cadastros/produtos/{obj.id}/excluir').status_code == 403
    assert client.post(f'/cadastros/produtos/{obj.id}/excluir', data={'confirmacao': obj.codigo}).status_code == 403
    assert db.session.get(Produto, obj.id) is not None


def test_exclusion_requires_csrf_when_enabled(app, client):
    obj = product()
    login(client)
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        assert client.post(f'/cadastros/produtos/{obj.id}/excluir', data={'confirmacao': obj.codigo}).status_code == 400
        assert db.session.get(Produto, obj.id) is not None
    finally:
        app.config['WTF_CSRF_ENABLED'] = False