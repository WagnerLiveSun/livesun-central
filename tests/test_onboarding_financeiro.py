from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models import Assinatura, Cobranca, ConfigAsaas, OperacaoAsaas, Produto, SolicitacaoCadastro
from app.security import encrypt
from app.services.asaas_service import process_one
from app.services.cadastro_service import receive
from test_autocadastro import payload
from test_central import login


def setup_registration(app):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    product.planos[0].valor_mensal = Decimal('100.00')
    row, _ = receive(product, payload())
    db.session.commit()
    return row


def submit(client, app, row, mode, **options):
    return client.post(f'/cadastros-recebidos/{row.id}/habilitar', data={
        'plano_id': app.test_ids['plano_id'], 'modalidade': mode,
        'motivo': 'Conferência comercial', 'confirmacao': 'CONFIRMAR', **options})


@pytest.mark.parametrize('mode', ['trial', 'cortesia'])
def test_onboarding_trial_and_courtesy_create_no_charge(app, client, mode):
    row = setup_registration(app)
    login(client)
    result = submit(client, app, row, mode)
    assert result.status_code == 302
    assert result.location.endswith(f'/assinaturas/{row.assinatura_id}')
    assert row.assinatura.status == ('TRIAL' if mode == 'trial' else 'ATIVA')
    assert row.assinatura.cortesia == (mode == 'cortesia')
    assert not db.session.scalar(db.select(Cobranca))
    assert not db.session.scalar(db.select(OperacaoAsaas))


def test_onboarding_avulsa_creates_local_charge_with_explicit_value(app, client):
    row = setup_registration(app)
    login(client)
    result = submit(client, app, row, 'avulsa', valor='43.25', competencia='2026-11', vencimento='2026-11-30')
    assert result.status_code == 302
    charge = db.session.scalar(db.select(Cobranca))
    assert charge.assinatura_id == row.assinatura_id
    assert charge.valor == Decimal('43.25') and charge.status == 'ABERTA' and not charge.gateway


def test_onboarding_recurring_queues_and_worker_calls_gateway(app, client):
    row = setup_registration(app)
    row.produto.codigo = 'COMERCIAL'
    row.produto.config_asaas = ConfigAsaas(ambiente='sandbox', api_key=encrypt('key'),
                                           webhook_token=encrypt('t'*40), ativo=True)
    db.session.commit()
    login(client)
    result = submit(client, app, row, 'recorrencia', forma='PIX')
    assert result.status_code == 302
    subscription = db.session.get(Assinatura, row.assinatura_id)
    operation = db.session.scalar(db.select(OperacaoAsaas))
    assert operation.status == 'PENDENTE' and operation.assinatura_id == subscription.id
    operation_id = operation.id
    calls = []

    def api(method, path, **kwargs):
        calls.append((method, path, kwargs.get('json')))
        if path == '/customers':
            return {'id': 'cus_1'}
        if method == 'POST' and path == '/subscriptions':
            return {'id': 'sub_1'}
        if method == 'GET' and path == '/subscriptions/sub_1':
            return {'id': 'sub_1', 'customer': 'cus_1', 'status': 'ACTIVE'}
        if method == 'PUT':
            return {'id': 'sub_1'}
        raise AssertionError((method, path))

    with patch('app.services.asaas_service.AsaasClient.pages', return_value=[]), \
         patch('app.services.asaas_service.AsaasClient.request', side_effect=api):
        assert process_one()
    assert db.session.get(OperacaoAsaas, operation_id).status == 'CONCLUIDA'
    assert any(method == 'POST' and path == '/subscriptions' and body['value'] == 100
               and body['cycle'] == 'MONTHLY' for method, path, body in calls)


def test_divergent_propostas_plan_never_queues_an_incorrect_amount(app, client):
    row = setup_registration(app)
    row.produto.config_asaas = ConfigAsaas(ambiente='sandbox', api_key=encrypt('key'),
                                           webhook_token=encrypt('t'*40), ativo=True)
    db.session.commit()
    login(client)
    assert submit(client, app, row, 'recorrencia').status_code == 422
    assert not db.session.scalar(db.select(OperacaoAsaas))
    assert not db.session.scalar(db.select(Assinatura))


def test_onboarding_recurring_without_configuration_rolls_back(app, client):
    row = setup_registration(app)
    login(client)
    assert submit(client, app, row, 'recorrencia').status_code == 422
    assert db.session.get(SolicitacaoCadastro, row.id).status == 'PENDENTE'
    assert not db.session.scalar(db.select(Assinatura))


def test_refusal_requires_confirmation_and_is_audited(app, client):
    from app.models import Auditoria
    row = setup_registration(app)
    login(client)
    response = submit(client, app, row, 'recusa')
    assert response.status_code == 302 and row.status == 'RECUSADA'
    assert not db.session.scalar(db.select(Assinatura))
    assert db.session.scalar(db.select(Auditoria).filter_by(entidade_id=row.id,
        entidade='solicitacoes_cadastro', acao='AUTOCADASTRO_RECUSADO'))