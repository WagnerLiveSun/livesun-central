from datetime import date
from unittest.mock import patch
from app.extensions import db
from app.models import Produto, ConfigAsaas, OperacaoAsaas, Cobranca
from app.security import encrypt
from app.services.assinatura_service import create, grant_courtesy
from test_central import login


def test_list_has_direct_actions_and_no_migration(app,client):
    obj=create(app.test_ids)
    grant_courtesy(obj,0,True,'Bonificação existente')
    db.session.commit()
    login(client)
    html=client.get('/assinaturas').get_data(as_text=True)
    for text in ['Suspender','Bloquear','Cancelar','Excluir','Bonificação','data-dialog=',obj.cliente.razao_social,obj.produto.nome]:
        assert text in html
    assert 'Migrar assinaturas' not in html
    detail=client.get(f'/assinaturas/{obj.id}').get_data(as_text=True)
    assert 'Bonificada' in detail
    assert 'data-dialog="cobrar-' not in detail
    assert 'name="subscription_id"' not in detail
    assert client.get('/migracao/comercial').status_code==404


def test_asaas_configuration_attaches_to_product(app,client):
    login(client)
    response=client.post('/integracoes/asaas',data={'produto_id':app.test_ids['produto_id'],
        'ambiente':'sandbox','api_key':'test-key','webhook_token':'t'*40,'ativo':'on'})
    assert response.status_code==302
    assert response.location.endswith(f"/produtos/{app.test_ids['produto_id']}/cobranca")
    product=db.session.get(Produto,app.test_ids['produto_id'])
    assert product.config_asaas is not None
    assert product.config_asaas.ambiente=='sandbox'
    html=client.get(response.location).get_data(as_text=True)
    assert 'Configuração de cobrança' in html
    integrations=client.get('/integracoes').get_data(as_text=True)
    assert 'Esta conta recebe' not in integrations and 'Operações Asaas recentes' not in integrations
    assert 'name="api_key"' not in integrations


def test_start_charge_uses_product_account_and_subscription_plan(app,client):
    obj=create(app.test_ids)
    obj.status='ATIVA'
    obj.plano.valor_mensal=79
    config=ConfigAsaas(ambiente='sandbox',api_key=encrypt('test'),webhook_token=encrypt('t'*40),ativo=True)
    obj.produto.config_asaas=config
    db.session.commit()
    login(client)
    with patch('requests.Session.request') as remote:
        response=client.post(f'/assinaturas/{obj.id}/comercial/asaas',data={'forma':'PIX','ambiente':'producao'})
        remote.assert_not_called()
    assert response.status_code==302
    assert obj.asaas_ambiente=='sandbox' and obj.asaas_forma=='PIX'
    op=db.session.scalar(db.select(OperacaoAsaas))
    assert op.assinatura_id==obj.id
    assert db.session.scalar(db.select(db.func.count()).select_from(Cobranca))==0


def test_bonified_subscription_cannot_be_charged_by_post(app,client):
    obj=create(app.test_ids)
    grant_courtesy(obj,0,True,'Bonificação preservada')
    obj.produto.config_asaas=ConfigAsaas(ambiente='sandbox',api_key=encrypt('test'),webhook_token=encrypt('t'*40),ativo=True)
    db.session.commit()
    login(client)
    response=client.post(f'/assinaturas/{obj.id}/comercial/asaas',data={'forma':'BOLETO'})
    assert response.status_code==422
    assert obj.cortesia and not obj.asaas_habilitado
    assert db.session.scalar(db.select(db.func.count()).select_from(OperacaoAsaas))==0