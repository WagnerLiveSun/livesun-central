from datetime import date, timedelta
from unittest.mock import Mock, patch
import pytest
from app.extensions import db
from app.models import (Produto, Plano, Assinatura, ConfigAsaas, EventoAsaas, OperacaoAsaas,
                        PurgaProduto, Cobranca, CredencialServico)
from app.security import encrypt, issue_product_credential
from app.services import assinatura_service as subscriptions
from app.services.asaas_service import receive, apply_payment, process_one, configure_subscription
from app.services.purga_service import anticipate, process_one as purge_one


def subscription(app):
    obj=subscriptions.create(app.test_ids)
    obj.asaas_ambiente='sandbox'
    obj.asaas_subscription_id='sub_test'
    obj.asaas_habilitado=True
    obj.plano.valor_mensal=99
    config=ConfigAsaas(ambiente='sandbox',api_key=encrypt('fake'),webhook_token=encrypt('t'*40),ativo=True)
    db.session.add(config)
    obj.produto.config_asaas=config
    db.session.commit()
    return obj


def test_persistent_credential_read_only_and_revoked(app,client):
    product=db.session.get(Produto,app.test_ids['produto_id'])
    credential,raw=issue_product_credential(product)
    db.session.commit()
    assert raw not in credential.digest
    headers={'Authorization':'Bearer '+raw}
    assert client.get('/api/v1/produtos',headers=headers).status_code==200
    assert client.post('/api/v1/assinaturas',headers=headers,json=app.test_ids).status_code==403
    credential.ativo=False
    db.session.commit()
    assert client.get('/api/v1/produtos',headers=headers).status_code==401


def test_asaas_auth_idempotency_unknown_subscription_ignored(app,client):
    subscription(app)
    payload={'id':'event_test','event':'PAYMENT_RECEIVED','payment':{'id':'pay_test','subscription':'sub_test'}}
    url='/api/v1/webhooks/asaas/sandbox'
    assert client.post(url,json=payload).status_code==401
    headers={'asaas-access-token':'t'*40}
    assert client.post(url,json=payload,headers=headers).status_code==200
    assert client.post(url,json=payload,headers=headers).json['status']=='duplicado'
    payload['id']='event_foreign'; payload['payment']['subscription']='sub_operacional'
    assert client.post(url,json=payload,headers=headers).status_code==200
    foreign=db.session.scalar(db.select(EventoAsaas).filter_by(evento_externo='sandbox:event_foreign'))
    assert foreign.status=='IGNORADO'


def test_asaas_payment_never_resolves_by_customer(app):
    obj=subscription(app)
    with pytest.raises(subscriptions.BusinessError):
        apply_payment(obj,{'id':'pay','subscription':'sub_foreign','dueDate':date.today().isoformat(),'value':99,'status':'RECEIVED'})
    payment={'id':'pay','subscription':'sub_test','dueDate':date.today().isoformat(),'value':99,'status':'RECEIVED'}
    apply_payment(obj,payment)
    db.session.commit()
    assert obj.status=='ATIVA'
    assert db.session.scalar(db.select(Cobranca)).status=='PAGA'
    apply_payment(obj,payment)
    db.session.commit()
    assert db.session.scalar(db.select(db.func.count()).select_from(Cobranca))==1


def test_old_asaas_event_uses_gateway_current_state(app):
    obj=subscription(app)
    receive('sandbox','t'*40,{'id':'old','event':'PAYMENT_OVERDUE','payment':{'id':'pay','subscription':'sub_test'}})
    with patch('app.services.asaas_service.AsaasClient.request',return_value={'id':'pay','subscription':'sub_test',
        'dueDate':date.today().isoformat(),'value':99,'status':'RECEIVED'}):
        assert process_one()
    assert db.session.scalar(db.select(Cobranca)).status=='PAGA'
    assert db.session.scalar(db.select(EventoAsaas)).status=='PROCESSADO'


def test_ambiguous_asaas_operation_requires_review(app):
    obj=subscription(app)
    from app.services.asaas_service import enqueue
    enqueue(obj,'SINCRONIZAR'); db.session.commit()
    with patch('app.services.asaas_service.sync_subscription',side_effect=TimeoutError):
        assert process_one()
    assert db.session.scalar(db.select(OperacaoAsaas)).status=='REVISAR'


def test_purge_retention_and_product_isolation(app):
    product = db.session.get(Produto, app.test_ids['produto_id'])
    product.codigo = 'COMERCIAL'
    obj=subscriptions.create(app.test_ids)
    db.session.commit()
    subscriptions.change_status(obj,'EXCLUIDA','Contrato encerrado')
    db.session.commit()
    entry=db.session.scalar(db.select(PurgaProduto))
    assert (entry.executar_em.date()-obj.excluida_em.date()).days==60
    anticipate(obj,'Autorizacao expressa para teste')
    db.session.commit()
    response=Mock(status_code=200)
    response.json.return_value={'operacao_id':entry.operacao_id}
    with patch('app.services.purga_service.validate_destination'),patch('requests.Session.post',return_value=response) as post:
        assert purge_one()
        import json
        payload=json.loads(post.call_args.kwargs['data'])
        assert payload['produto']=='COMERCIAL'
        assert payload['antecipada'] is True
    assert entry.status=='CONCLUIDA'


def test_purge_blocked_if_new_subscription_exists(app):
    obj=subscriptions.create(app.test_ids); db.session.commit()
    subscriptions.change_status(obj,'EXCLUIDA','Contrato encerrado'); db.session.commit()
    subscriptions.create(app.test_ids); db.session.commit()
    anticipate(obj,'Purga antecipada'); db.session.commit()
    with patch('requests.Session.post') as post:
        assert purge_one()
        post.assert_not_called()
    assert db.session.scalar(db.select(PurgaProduto)).status=='IMPEDIDA'


def test_bonification_blocks_recurring_and_manual_charge(app):
    obj=subscription(app)
    obj.cortesia=True
    db.session.commit()
    from app.services.cobranca_service import create_charge
    with patch('requests.Session.request') as network:
        with pytest.raises(subscriptions.BusinessError,match='bonificada'):
            configure_subscription(obj,'sandbox','BOLETO')
        with pytest.raises(subscriptions.BusinessError,match='bonificada'):
            create_charge({'assinatura_id':obj.id,'competencia':'2026-11','valor':99,'vencimento':date.today()})
        network.assert_not_called()
    assert obj.cortesia is True


def test_integration_panels_and_buttons(app,client):
    from test_central import login
    obj=subscription(app)
    login(client)
    assert client.get('/integracoes').status_code==200
    assert client.get('/migracao/comercial').status_code==404
    response=client.get(f'/assinaturas/{obj.id}')
    assert b'data-status="SUSPENSA"' in response.data
    assert b'JSON' not in response.data
    assert client.post('/cadastros/clientes/novo',data={'razao_social':'Cadastro visual',
        'email_principal':'visual@example.com','status':'ATIVO'}).status_code==302


def test_credentials_generated_by_panel_never_enter_audit(app,client):
    from test_central import login
    from app.models import Auditoria
    login(client)
    response=client.post(f"/integracoes/produtos/{app.test_ids['produto_id']}/gerar",data={'confirmacao':'GERAR'})
    assert response.status_code==200
    assert b'lsc_' in response.data
    assert response.headers['Cache-Control']=='no-store'
    records=list(db.session.scalars(db.select(Auditoria).where(Auditoria.acao=='CREDENCIAL_PRODUTO_GERADA')))
    assert records and 'digest' not in records[0].novo