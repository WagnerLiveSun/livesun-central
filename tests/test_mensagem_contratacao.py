from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import Cobranca
from test_central import login
from test_comercial_phase import subscription
from test_entrega4_checkout import token


@pytest.mark.parametrize('role', ['cliente', 'operador'])
def test_welcome_for_pending_invoice_has_no_technical_terms(app, client, role):
    obj = subscription(app)
    obj.plano.valor_mensal = Decimal('80.00')
    db.session.commit()
    if role == 'cliente':
        client.get('/contratar/propostas?token=' + token(obj.cliente_id))
        response = client.get('/contratar/propostas')
    else:
        login(client)
        response = client.get(f'/contratar-propostas/{obj.cliente_id}')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Boas-vindas ao LiveSun Propostas!' in html
    assert 'Central de Atendimento LiveSun' in html
    assert 'R$ 80,00 / mensal' in html
    assert 'em até 24 horas após a confirmação do pagamento' in html
    assert obj.cliente.email_principal in html
    assert 'worker' not in html and 'Status de acesso: TRIAL' not in html


@pytest.mark.parametrize('status,expected', [
    ('PAGA', 'Pagamento confirmado.'),
    ('CANCELADA', 'Não foi possível concluir a cobrança.'),
    ('AGUARDANDO_PAGAMENTO', 'O boleto para pagamento do plano será encaminhado'),
])
def test_welcome_reflects_payment_state(app, client, status, expected):
    obj = subscription(app)
    db.session.add(Cobranca(assinatura_id=obj.id, competencia='2026-11',
        valor=Decimal('80.00'), vencimento=date.today(), status=status,
        invoice_url='https://sandbox.asaas.com/i/teste'))
    db.session.commit()
    client.get('/contratar/propostas?token=' + token(obj.cliente_id))
    html = client.get('/contratar/propostas').get_data(as_text=True)
    assert expected in html
    assert 'Abrir cobrança' in html and 'worker' not in html


def test_paid_active_subscription_does_not_claim_access_is_pending(app, client):
    obj = subscription(app)
    obj.status = 'ATIVA'
    db.session.add(Cobranca(assinatura_id=obj.id, competencia='2026-11',
        valor=Decimal('80.00'), vencimento=date.today(), status='PAGA'))
    db.session.commit()
    client.get('/contratar/propostas?token=' + token(obj.cliente_id))
    html = client.get('/contratar/propostas').get_data(as_text=True)
    assert 'Seu acesso está ativo.' in html
    assert 'liberação do plano contratado está pendente' not in html