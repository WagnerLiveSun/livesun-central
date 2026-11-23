from unittest.mock import patch

from app.extensions import db
from app.models import ConfigAsaas, OperacaoAsaas, Produto
from app.models.base import now
from app.security import encrypt
from app.services.assinatura_service import create
from test_central import login
from test_autocadastro import payload
from app.services.cadastro_service import receive


def test_billing_page_shows_asaas_subscription_and_pending_review(app, client):
    obj = create({**app.test_ids, 'status': 'ATIVA'})
    obj.plano.valor_mensal = 80
    obj.asaas_habilitado = True
    obj.asaas_ambiente = 'sandbox'
    obj.produto.config_asaas = ConfigAsaas(ambiente='sandbox', api_key=encrypt('fake'),
        webhook_token=encrypt('t'*40), ativo=True)
    db.session.add(OperacaoAsaas(assinatura_id=obj.id, tipo='SINCRONIZAR', status='REVISAR',
                                proxima_tentativa=now()))
    db.session.commit()
    login(client)
    html = client.get('/cobrancas').get_data(as_text=True)
    assert obj.cliente.razao_social in html and obj.plano.nome in html and '80.00' in html
    assert 'Solicitação precisa de revisão' in html
    assert f'/assinaturas/{obj.id}#cobranca' in html
    assert 'Nenhuma assinatura disponível para registro manual' in html


def test_production_sandbox_cannot_enqueue_recurrence(app, client):
    obj = create({**app.test_ids, 'status': 'ATIVA'})
    obj.plano.valor_mensal = 80
    obj.produto.config_asaas = ConfigAsaas(ambiente='sandbox', api_key=encrypt('fake'),
        webhook_token=encrypt('t'*40), ativo=True)
    db.session.commit()
    login(client)
    app.config['APP_ENV'] = 'production'
    with patch('requests.Session.request') as remote:
        response = client.post(f'/assinaturas/{obj.id}/comercial/asaas', data={'forma':'PIX'},
                               base_url='https://localhost')
        remote.assert_not_called()
    assert response.status_code == 422
    assert 'conta de cobrança deste produto está em testes' in response.get_data(as_text=True)
    assert not db.session.scalar(db.select(OperacaoAsaas))
    html = client.get(f'/assinaturas/{obj.id}', base_url='https://localhost').get_data(as_text=True)
    assert 'conta deste produto está configurada em testes' in html
    assert 'data-dialog="cobrar-' not in html


def test_production_onboarding_sandbox_is_rolled_back(app, client):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    product.planos[0].valor_mensal = 80
    product.config_asaas = ConfigAsaas(ambiente='sandbox', api_key=encrypt('fake'),
        webhook_token=encrypt('t'*40), ativo=True)
    row, _ = receive(product, payload())
    db.session.commit()
    login(client)
    app.config['APP_ENV'] = 'production'
    response = client.post(f'/cadastros-recebidos/{row.id}/habilitar', base_url='https://localhost', data={
        'plano_id': app.test_ids['plano_id'], 'modalidade': 'recorrencia', 'forma':'PIX',
        'confirmacao':'CONFIRMAR', 'motivo':'Aprovação comercial'})
    assert response.status_code == 422
    assert row.status == 'PENDENTE' and not db.session.scalar(db.select(OperacaoAsaas))