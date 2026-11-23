import pytest

from app.extensions import db
from app.models import ConfigAsaas, GatewayAlternativo, Produto
from app.security import encrypt
from test_central import login


def test_existing_asaas_configuration_is_visible_without_copying_or_exposing_secrets(app, client):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    config = ConfigAsaas(ambiente='sandbox', ativo=True, api_key=encrypt('secret-key-example'),
                         webhook_token=encrypt('webhook-secret-example-1234567890'))
    product.config_asaas = config
    other = Produto(codigo='OUTRO', nome='Outro produto')
    db.session.add(other)
    db.session.commit()
    login(client)
    app.config['APP_ENV'] = 'production'
    response = client.get('/configuracoes/gateways', base_url='https://localhost')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Asaas por produto' in html
    assert product.nome in html and 'Asaas · Testes' in html
    assert 'Ativa em testes; não processa cobranças neste ambiente de produção' in html
    assert 'Outro produto' in html and 'Nenhuma conta vinculada' in html
    assert f'/produtos/{product.id}/cobranca#configuracao-cobranca' in html
    assert 'secret-key-example' not in html and 'webhook-secret-example' not in html
    assert config.api_key not in html and config.webhook_token not in html
    assert not db.session.scalar(db.select(GatewayAlternativo))


def test_screen_reflects_saved_asaas_configuration_and_separate_alternative(app, client):
    login(client)
    response = client.post('/integracoes/asaas', data={'produto_id': app.test_ids['produto_id'],
        'ambiente': 'sandbox', 'api_key': 'test-key', 'webhook_token': 't'*40, 'ativo': 'on'})
    assert response.status_code == 302
    html = client.get('/configuracoes/gateways').get_data(as_text=True)
    assert 'Asaas · Testes' in html and 'Gerenciar Asaas' in html
    assert 'Nenhuma integração alternativa cadastrada.' in html
    assert 'test-key' not in html


def test_global_environment_override_is_explained_without_exposing_values(app, client):
    login(client)
    app.config['ASAAS_API_KEY'] = 'global-secret'
    html = client.get('/configuracoes/gateways').get_data(as_text=True)
    assert 'parâmetros Asaas definidos no ambiente da aplicação' in html
    assert 'global-secret' not in html


@pytest.mark.parametrize('role', ['comercial', 'financeiro', 'suporte', 'auditor'])
def test_payment_integration_page_remains_admin_only(app, client, role):
    login(client, role)
    assert client.get('/configuracoes/gateways').status_code == 403