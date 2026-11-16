import copy
import json
from datetime import date, timedelta
from unittest.mock import Mock, patch
import pytest
from app.extensions import db
from app.models import Produto, Plano, Assinatura, Cliente, SolicitacaoCadastro, Cobranca, OperacaoAsaas
from app.security import encrypt
from app.services import empresas_comercial_service as service
from app.services.assinatura_service import BusinessError
from app.services.cadastro_service import deliver_one, review
from test_central import login


def company(identifier=10, **terms):
    return {'dados': {'evento_id': service.legacy_event(identifier), 'empresa_id': identifier,
        'razao_social': 'Empresa Comercial', 'nome_fantasia': None, 'cnpj_cpf': '12345678000190',
        'email': 'owner@example.com', 'telefone': None, 'responsavel': 'Responsável'},
        'ativo': True, 'cliente_id': None, 'assinatura': {
            'id': 20, 'status': 'ativa', 'plano': 'premium', 'periodicidade': 'mensal', 'preco': '99.90',
            'data_inicio': '2024-01-15', 'data_vencimento': '2026-12-15', 'trial_ate': None,
            'bonificada': False, 'bonificacao_ate': None, 'usuarios': 7,
            'recorrencia_externa': False, 'mudanca_plano_pendente': False, **terms}}


@pytest.fixture
def commercial(app):
    product = Produto(codigo='COMERCIAL', nome='Comercial', ativo=True,
        url_producao='https://app.livesun.com.br', webhook_secret=encrypt('c' * 40))
    db.session.add(product)
    db.session.flush()
    plan = Plano(produto_id=product.id, codigo='PREMIUM', nome='Premium',
                 valor_mensal='99.90', periodicidade='mensal', ativo=True, limite_usuarios=5)
    db.session.add(plan)
    db.session.commit()
    return product, plan


def prepare(item):
    with patch.object(service, 'company', return_value=item):
        row = service.prepare_registration(item['dados']['empresa_id'])
    db.session.commit()
    return row


def confirm(row, plan, item, client_id=None):
    with patch.object(service, 'company', return_value=item):
        return service.confirm(row.id, client_id, plan.id, service.fingerprint(item), True, 'Condições legadas conferidas')


def test_discovery_and_preparation_do_not_migrate_or_bill(app, client, commercial):
    login(client)
    item = company()
    with patch.object(service, 'list_companies', return_value=([item], None)):
        response = client.get('/empresas-comercial')
    assert response.status_code == 200
    assert 'Preparar migração' in response.get_data(as_text=True)
    before = db.session.query(Cliente).count()
    row = prepare(item)
    assert prepare(item).id == row.id
    assert db.session.query(SolicitacaoCadastro).count() == 1
    assert db.session.query(Cliente).count() == before
    assert db.session.query(Assinatura).count() == db.session.query(Cobranca).count() == 0
    with patch.object(service, 'company', return_value=item):
        preview = client.get(f'/cadastros-recebidos/{row.id}')
    assert preview.status_code == 200
    assert 'Conferir assinatura legada' in preview.get_data(as_text=True)
    assert 'Acesso inicial<select' not in preview.get_data(as_text=True)


@pytest.mark.parametrize('status,expected', [('ativa','ATIVA'), ('suspensa','SUSPENSA'),
    ('cancelada','CANCELADA'), ('bloqueada','BLOQUEADA'), ('expirada','EXPIRADA')])
def test_confirmation_preserves_status_dates_limits_without_billing(app, commercial, status, expected):
    item = company(status=status)
    row = prepare(item)
    confirm(row, commercial[1], item)
    db.session.commit()
    subscription = row.assinatura
    assert subscription.status == expected
    assert subscription.data_inicio == date(2024, 1, 15)
    assert subscription.data_proxima_cobranca == date(2026, 12, 15)
    assert not subscription.asaas_habilitado
    assert row.status == 'VINCULO_PENDENTE'
    assert db.session.query(Cobranca).count() == db.session.query(OperacaoAsaas).count() == 0
    from app.services.entitlement_service import effective
    if expected == 'ATIVA':
        assert effective(subscription)['limites']['usuarios'] == 7


@pytest.mark.parametrize('end', [None, (date.today() + timedelta(days=20)).isoformat()])
def test_courtesy_preserves_original_end(app, commercial, end):
    item = company(status='suspensa', bonificada=True, bonificacao_ate=end)
    row = prepare(item)
    confirm(row, commercial[1], item)
    db.session.commit()
    assert row.assinatura.cortesia
    assert row.assinatura.status == 'ATIVA'
    assert row.assinatura.cortesia_ate == (date.fromisoformat(end) if end else None)


@pytest.mark.parametrize('terms', [
    {'recorrencia_externa': True}, {'mudanca_plano_pendente': True},
    {'status': 'trial', 'trial_ate': None},
    {'bonificada': True, 'bonificacao_ate': '2020-01-01'},
    {'plano': 'basic'}, {'periodicidade': 'anual'}, {'preco': '999.00'},
    {'bloqueio_nivel': 'parcial'}, {'carencia_dias': -1},
])
def test_divergences_require_review_without_creating_subscription(app, commercial, terms):
    item = company(**terms)
    row = prepare(item)
    with pytest.raises(BusinessError):
        confirm(row, commercial[1], item)
    db.session.rollback()
    assert db.session.query(Assinatura).count() == 0


def test_changed_preview_and_generic_review_rejected(app, commercial):
    item = company()
    row = prepare(item)
    altered = copy.deepcopy(item)
    altered['assinatura']['usuarios'] = 8
    with patch.object(service, 'company', return_value=altered), pytest.raises(BusinessError):
        service.confirm(row.id, None, commercial[1].id, service.fingerprint(item), True, 'Conferido')
    with pytest.raises(BusinessError):
        review(row.id, None, commercial[1].id, 'ATIVA', 'Nao contornar legado')


def test_signed_discovery_includes_query_and_rejects_other_product(app, commercial):
    response = Mock(status_code=200)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.raw.read.return_value = json.dumps({'produto':'COMERCIAL','empresas':[company()],'proximo':None}).encode()
    with patch.object(service, 'validate_destination'), patch.object(service, 'signed_headers', return_value={}) as sign, \
            patch('requests.Session.get', return_value=response) as get:
        assert len(service.list_companies()[0]) == 1
        assert sign.call_args.args[1] == b'/central/empresas?apos=0'
        assert get.call_args.kwargs['allow_redirects'] is False
    response.raw.read.return_value = b'{"produto":"PROPOSTAS"}'
    with patch.object(service, 'validate_destination'), patch('requests.Session.get', return_value=response), pytest.raises(BusinessError):
        service.fetch('/central/empresas?apos=0')


@pytest.mark.parametrize('role', ['suporte','auditor','financeiro'])
def test_readonly_cannot_prepare_or_confirm(app, client, commercial, role):
    login(client, role)
    assert client.post('/empresas-comercial/10/preparar').status_code == 403
    assert client.post('/empresas-comercial/cadastros/10/confirmar').status_code == 403


def test_prepare_and_confirm_require_csrf(app, client, commercial):
    login(client)
    app.config['WTF_CSRF_ENABLED'] = True
    assert client.post('/empresas-comercial/10/preparar').status_code == 400
    assert client.post('/empresas-comercial/cadastros/10/confirmar').status_code == 400


def test_worker_delivers_audited_hash_for_suspended_legacy(app, commercial):
    item = company(status='suspensa')
    row = prepare(item)
    confirm(row, commercial[1], item)
    db.session.commit()
    response = Mock(status_code=200)
    response.json.return_value = {'evento_id':row.evento_origem}
    with patch('app.services.cadastro_service.validate_destination'), patch('requests.Session.post', return_value=response) as post:
        assert deliver_one()
        body = json.loads(post.call_args.kwargs['data'])
    assert body['origem_legada'] is True
    assert body['origem_hash'] == service.fingerprint(item)
    assert body['entitlements']['status'] == 'SUSPENSA'
    assert not body['entitlements']['acesso_produto']
    assert row.status == 'VINCULADA'


@pytest.mark.parametrize('rows,cursor', [([company(),company()],None),([company()],0),([company()],'10')])
def test_invalid_pagination(app, commercial, rows, cursor):
    with patch.object(service,'fetch',return_value={'empresas':rows,'proximo':cursor}), pytest.raises(BusinessError):
        service.list_companies()


def test_expired_trial_not_extended(app, commercial):
    old_end = (date.today() - timedelta(days=4)).isoformat()
    item = company(status='trial', trial_ate=old_end)
    row = prepare(item)
    confirm(row, commercial[1], item)
    db.session.commit()
    assert row.assinatura.status == 'EXPIRADA'
    assert row.assinatura.trial_ate.isoformat() == old_end


def test_document_matching_and_no_duplicate_subscription(app, commercial):
    item = company()
    row = prepare(item)
    customer = db.session.get(Cliente, app.test_ids['cliente_id'])
    customer.cnpj_cpf = '99999999000199'
    db.session.commit()
    with pytest.raises(BusinessError):
        confirm(row, commercial[1], item, customer.id)
    db.session.rollback()
    customer.cnpj_cpf = item['dados']['cnpj_cpf']
    db.session.commit()
    confirm(row, commercial[1], item, customer.id)
    db.session.commit()
    assert row.cliente_id == customer.id
    with pytest.raises(BusinessError):
        confirm(row, commercial[1], item, customer.id)
    assert db.session.query(Assinatura).count() == 1