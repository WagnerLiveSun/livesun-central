import json
from datetime import date
from unittest.mock import Mock, patch

import pytest

from app.extensions import db
from app.models import Produto
from app.services.cadastro_service import pull_pending, receive
from test_autocadastro import payload
from test_central import login


def test_single_registration_queue_filters_multiple_products(app, client):
    products = [db.session.get(Produto, app.test_ids['produto_id']),
                Produto(codigo='COMERCIAL', nome='Comercial'), Produto(codigo='FUTURO', nome='Futuro')]
    db.session.add_all(products[1:])
    db.session.flush()
    for index, product in enumerate(products):
        receive(product, {**payload(index + 1, 'cad_' + str(index) * 32),
                          'razao_social': 'Empresa ' + product.nome})
    db.session.commit()
    login(client)
    html = client.get('/cadastros-recebidos').get_data(as_text=True)
    for product in products:
        assert 'Empresa ' + product.nome in html
    html = client.get('/cadastros-recebidos', query_string={'produto': products[2].id, 'nome': 'Futu',
        'documento': '12.345.678/0001-90', 'inicio': date.today().isoformat(),
        'fim': date.today().isoformat()}).get_data(as_text=True)
    assert 'Empresa Futuro' in html and 'Empresa Comercial' not in html
    assert client.get('/cadastros-recebidos?inicio=2026-99-01').status_code == 422


@pytest.mark.parametrize('role', ['comercial', 'financeiro', 'suporte', 'auditor'])
def test_technical_settings_are_not_accessible_to_non_admin(app, client, role):
    login(client, role)
    assert client.get('/configuracoes').status_code == 403
    assert client.get('/integracoes').status_code == 403
    assert client.get('/webhooks').status_code == 403
    html = client.get('/').get_data(as_text=True)
    assert '>Configurações<' not in html
    assert '>Empresas do Propostas<' not in html


@pytest.mark.parametrize('code,event', [(401, 'autocadastro_coleta_autenticacao'),
                                        (404, 'autocadastro_coleta_endpoint'),
                                        (503, 'autocadastro_coleta_resposta')])
def test_collection_failure_is_logged_without_sensitive_data(app, caplog, code, event):
    product = Produto(codigo='COMERCIAL', nome='Comercial',
                      url_producao='https://comercial.example', webhook_secret='encrypted')
    db.session.add(product)
    db.session.commit()
    response = Mock(status_code=code, content=b'secret-content')
    with patch('app.services.cadastro_service.validate_destination'), \
         patch('app.services.cadastro_service.decrypt', return_value='sensitive-token'), \
         patch('requests.Session.get', return_value=response):
        pull_pending()
    from app.security import SafeJSONFormatter
    record = next(record for record in caplog.records if getattr(record, 'safe_event', '') == event)
    data = SafeJSONFormatter().format(record)
    assert json.loads(data)['event'] == event
    assert 'sensitive-token' not in data and 'secret-content' not in data