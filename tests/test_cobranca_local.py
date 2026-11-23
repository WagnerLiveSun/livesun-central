from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Auditoria, Cobranca
from app.services.assinatura_service import create
from test_central import login


def active_subscription(app, period='mensal'):
    obj = create({**app.test_ids, 'status': 'ATIVA'})
    obj.plano.valor_mensal = Decimal('100.00')
    obj.plano.periodicidade = period
    db.session.commit()
    return obj


def form(obj, **values):
    return {'assinatura_id': str(obj.id), 'competencia': '2026-11',
            'vencimento': date.today().isoformat(), 'tipo': 'plano',
            'valor': '0.01', 'confirmacao': 'CONFIRMAR', **values}


@pytest.mark.parametrize('period', ['mensal', 'anual'])
def test_plan_value_is_loaded_and_calculated_on_server(app, client, period):
    obj = active_subscription(app, period)
    login(client)
    html = client.get('/cobrancas').get_data(as_text=True)
    assert 'R$ 100.00 / ' + period in html
    assert 'somente no Central' in html
    assert client.post('/cobrancas', data=form(obj)).status_code == 302
    charge = db.session.scalar(db.select(Cobranca))
    assert charge.assinatura_id == obj.id and charge.valor == Decimal('100.00')
    html = client.get('/cobrancas').get_data(as_text=True)
    assert obj.cliente.razao_social in html and obj.produto.nome in html
    assert obj.plano.nome in html and '2026-11' in html and '100.00' in html
    assert db.session.scalar(db.select(Auditoria).filter_by(entidade='cobrancas', acao='COBRANCA_CRIADA'))


def test_avulsa_allows_explicit_value_and_manual_payment(app, client):
    obj = active_subscription(app)
    login(client)
    assert client.post('/cobrancas', data=form(obj, tipo='avulsa', valor='42.50')).status_code == 302
    charge = db.session.scalar(db.select(Cobranca))
    assert charge.valor == Decimal('42.50')
    assert client.post(f'/cobrancas/{charge.id}/pagar').status_code == 422
    assert client.post(f'/cobrancas/{charge.id}/pagar', data={'confirmacao': 'CONFIRMAR'}).status_code == 302
    assert charge.status == 'PAGA' and charge.data_pagamento
    assert db.session.scalar(db.select(Auditoria).filter_by(entidade='cobrancas', acao='COBRANCA_PAGA'))


@pytest.mark.parametrize('state', ['trial', 'cortesia', 'asaas'])
def test_ineligible_subscription_cannot_be_charged_even_by_direct_post(app, client, state):
    obj = active_subscription(app)
    if state == 'trial':
        obj.status = 'TRIAL'
    elif state == 'cortesia':
        obj.cortesia = True
    else:
        obj.asaas_habilitado = True
    db.session.commit()
    login(client)
    html = client.get('/cobrancas').get_data(as_text=True)
    assert 'Nenhuma assinatura disponível para registro manual' in html
    assert obj.plano.nome in html and obj.cliente.razao_social in html
    assert client.post('/cobrancas', data=form(obj)).status_code == 422
    assert not db.session.scalar(db.select(Cobranca))


def test_confirmation_and_authorization_are_required(app, client):
    obj = active_subscription(app)
    login(client, 'comercial')
    assert client.post('/cobrancas', data=form(obj)).status_code == 403
    assert not db.session.scalar(db.select(Cobranca))