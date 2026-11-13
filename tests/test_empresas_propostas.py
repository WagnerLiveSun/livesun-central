import json
from unittest.mock import Mock, patch

import pytest
from app.extensions import db
from app.models import Produto, SolicitacaoCadastro, Cliente, Assinatura, Cobranca
from app.services.empresas_propostas_service import list_companies, prepare_registration
from app.services.assinatura_service import BusinessError
from test_autocadastro import payload
from test_central import login


def company(identifier=10):
    return {'dados': payload(identifier), 'ativo': True, 'cliente_id': None}


def remote(data, status=200):
    response = Mock(status_code=status)
    response.raw = Mock()
    response.raw.read.return_value = json.dumps(data).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    return response


def test_page_and_prepare_do_not_create_subscription_or_charge(app, client):
    login(client)
    with patch('app.services.empresas_propostas_service.list_companies', return_value=([company()], None)):
        page = client.get('/empresas-propostas')
    assert page.status_code == 200
    assert 'Cadastrar cliente e vincular' in page.get_data(as_text=True)
    before = db.session.scalar(db.select(db.func.count()).select_from(Cliente))
    with patch('app.services.empresas_propostas_service.fetch', return_value={'produto':'PROPOSTAS','empresa':company()}):
        response = client.post('/empresas-propostas/10/cadastrar')
        duplicate = client.post('/empresas-propostas/10/cadastrar')
    assert response.status_code == duplicate.status_code == 302
    assert response.location == duplicate.location
    assert db.session.scalar(db.select(db.func.count()).select_from(SolicitacaoCadastro)) == 1
    assert db.session.scalar(db.select(db.func.count()).select_from(Cliente)) == before
    for model in (Assinatura, Cobranca):
        assert db.session.scalar(db.select(db.func.count()).select_from(model)) == 0


@pytest.mark.parametrize('role', ['suporte','auditor','financeiro'])
def test_readonly_roles_cannot_prepare(app, client, role):
    login(client, role)
    with patch('app.services.empresas_propostas_service.fetch') as fetch:
        assert client.post('/empresas-propostas/10/cadastrar').status_code == 403
        fetch.assert_not_called()


@pytest.mark.parametrize('change', [{'cliente_id': 25}, {'ativo': False}, {'dados': payload(11)}])
def test_linked_inactive_or_wrong_company_rejected(app, change):
    with patch('app.services.empresas_propostas_service.fetch', return_value={'empresa':{**company(), **change}}):
        with pytest.raises(BusinessError):
            prepare_registration(10)


def test_list_uses_signed_query_and_no_redirects(app):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    product.url_producao = 'https://propostas.livesun.com.br'
    db.session.commit()
    with patch('app.services.empresas_propostas_service.validate_destination'), \
         patch('app.services.empresas_propostas_service.signed_headers', return_value={}) as sign, \
         patch('requests.Session.get', return_value=remote({'produto':'PROPOSTAS','empresas':[company()],'proximo':None})) as get:
        rows, cursor = list_companies()
        assert len(rows) == 1 and cursor is None
        assert sign.call_args.args[1] == b'/central/empresas?apos=0'
        assert get.call_args.kwargs['allow_redirects'] is False


def test_unavailable_product_is_visible_without_creating_data(app, client):
    login(client)
    with patch('app.services.empresas_propostas_service.list_companies', side_effect=BusinessError('Integração não publicada.')):
        response = client.get('/empresas-propostas')
    assert response.status_code == 200
    assert 'Integração não publicada.' in response.get_data(as_text=True)


def test_prepare_requires_csrf(app, client):
    login(client)
    app.config['WTF_CSRF_ENABLED'] = True
    with patch('app.services.empresas_propostas_service.fetch') as fetch:
        assert client.post('/empresas-propostas/10/cadastrar').status_code == 400
        fetch.assert_not_called()


@pytest.mark.parametrize('rows,cursor', [([company(), company()], None), ([company()], 0),
    ([company()], '10'), ([company()], 9)])
def test_rejects_duplicate_companies_and_invalid_pagination(app, rows, cursor):
    with patch('app.services.empresas_propostas_service.fetch', return_value={
            'empresas': rows, 'proximo': cursor}):
        with pytest.raises(BusinessError):
            list_companies()


def test_operator_confirms_then_worker_delivers_without_billing(app, client):
    from app.services.cadastro_service import deliver_one
    from app.models import OperacaoAsaas
    login(client)
    with patch('app.services.empresas_propostas_service.fetch', return_value={'empresa': company()}):
        response = client.post('/empresas-propostas/10/cadastrar')
    row = db.session.scalar(db.select(SolicitacaoCadastro))
    assert response.status_code == 302
    confirmation = client.post(f'/cadastros-recebidos/{row.id}/habilitar', data={
        'plano_id': app.test_ids['plano_id'], 'status':'TRIAL', 'motivo':'Vínculo conferido pelo operador'})
    assert confirmation.status_code == 302
    assert row.status == 'VINCULO_PENDENTE'
    response = Mock(status_code=200)
    response.json.return_value = {'evento_id':row.evento_origem}
    with patch('app.services.cadastro_service.validate_destination'), \
         patch('requests.Session.post', return_value=response) as post:
        assert deliver_one()
        sent = json.loads(post.call_args.kwargs['data'])
        assert sent['empresa_id'] == 10
        assert sent['cliente_id'] == row.cliente_id
        assert sent['cnpj_cpf'] == payload()['cnpj_cpf']
    assert row.status == 'VINCULADA'
    for model in (Cobranca, OperacaoAsaas):
        assert db.session.scalar(db.select(db.func.count()).select_from(model)) == 0