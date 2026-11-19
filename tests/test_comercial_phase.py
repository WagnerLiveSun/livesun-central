from datetime import date, timedelta
from unittest.mock import Mock, patch
import pytest
from app.extensions import db
from app.models import (Produto, Plano, Assinatura, ConfigAsaas, EventoAsaas, OperacaoAsaas,
                        PurgaProduto, Cobranca, CredencialServico, EventoAssinatura)
from app.security import encrypt, issue_product_credential
from app.services import assinatura_service as subscriptions
from app.services.asaas_service import receive, apply_payment, process_one, configure_subscription
from app.services.purga_service import anticipate, process_one as purge_one
from app.services.asaas_service import sync_subscription
from test_central import login


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
    assert obj.status=='TRIAL'  # pagamento não retira o trial existente
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


def test_public_webhook_rejects_invalid_token(app,client):
    obj=subscription(app)
    response=client.post('/api/asaas/webhook',json={
        'id':'public_invalid','event':'PAYMENT_CREATED',
        'payment':{'id':'pay_public','subscription':'sub_test'}
    },headers={'asaas-access-token':'wrong'})
    assert response.status_code==401
    assert db.session.scalar(db.select(db.func.count()).select_from(EventoAsaas))==0


def test_public_webhook_event_id_is_idempotent(app,client):
    obj=subscription(app)
    payload={'id':'public_event','event':'PAYMENT_CREATED',
             'payment':{'id':'pay_public','subscription':'sub_test'}}
    headers={'asaas-access-token':'t'*40}
    first=client.post('/api/asaas/webhook',json=payload,headers=headers)
    second=client.post('/api/asaas/webhook',json=payload,headers=headers)
    assert first.status_code==second.status_code==200
    assert first.json['status']=='recebido'
    assert second.json['status']=='duplicado'
    assert db.session.scalar(db.select(db.func.count()).select_from(EventoAsaas))==1


def test_confirmed_then_manual_release_then_received_keeps_active(app,client):
    obj=subscription(app)
    charge=Cobranca(assinatura_id=obj.id,competencia=date.today().strftime('%Y-%m'),
                    valor=80,vencimento=date.today(),status='PAGA',
                    gateway='asaas',gateway_payment_id='pay_manual',
                    asaas_ambiente='sandbox',invoice_url='https://sandbox.asaas.com/i/pay_manual')
    db.session.add(charge)
    obj.status='PAGO_AGUARDANDO_LIBERACAO'
    db.session.commit()
    login(client)
    response=client.post(f'/assinaturas/{obj.id}/liberar')
    assert response.status_code==302
    assert obj.status=='ATIVA'
    assert obj.liberado_por_id is not None and obj.liberado_em is not None
    apply_payment(obj,{'id':'pay_manual','subscription':'sub_test',
                       'dueDate':date.today().isoformat(),'value':'80.00',
                       'status':'RECEIVED','billingType':'UNDEFINED'})
    db.session.commit()
    assert obj.status=='ATIVA'
    duplicate=db.session.scalar(db.select(db.func.count()).select_from(EventoAssinatura).where(
        EventoAssinatura.assinatura_id==obj.id,
        EventoAssinatura.tipo_evento=='ASSINATURA_ATIVADA'))
    assert duplicate==1


def test_manual_release_denied_without_permission(app,client):
    obj=subscription(app)
    obj.status='PAGO_AGUARDANDO_LIBERACAO'
    charge=Cobranca(assinatura_id=obj.id,competencia=date.today().strftime('%Y-%m'),
                    valor=80,vencimento=date.today(),status='PAGA',
                    gateway='asaas',gateway_payment_id='pay_denied',
                    asaas_ambiente='sandbox')
    db.session.add(charge)
    db.session.commit()
    login(client,'suporte')
    response=client.post(f'/assinaturas/{obj.id}/liberar')
    assert response.status_code==403
    assert obj.status=='PAGO_AGUARDANDO_LIBERACAO'


def test_monthly_and_annual_server_payload_values(app):
    obj=subscription(app)
    obj.asaas_subscription_id=None
    obj.asaas_habilitado=True
    obj.asaas_customer_id=None
    obj.asaas_ambiente='sandbox'
    obj.produto.codigo='PROPOSTAS'
    captured=[]

    class Remote:
        def pages(self, path, params=None):
            return iter(())
        def request(self, method, path, **kwargs):
            if method=='POST' and path=='/customers':
                return {'id':'cus_env_test'}
            if method=='POST' and path=='/subscriptions':
                captured.append(kwargs['json'])
                return {'id':'sub_server_test'}
            if method=='GET':
                return {'id':'sub_server_test','customer':'cus_env_test','status':'ACTIVE'}
            if method=='PUT':
                return {'id':'sub_server_test'}
            return {}

    obj.plano.periodicidade='mensal'
    sync_subscription(obj,Remote())
    db.session.commit()
    obj.asaas_subscription_id=None
    obj.plano.periodicidade='anual'
    sync_subscription(obj,Remote())
    db.session.commit()
    assert captured[0]['value']==80
    assert captured[0]['cycle']=='MONTHLY'
    assert captured[0]['billingType']=='UNDEFINED'
    assert captured[0]['nextDueDate']==date.today().isoformat()
    assert captured[1]['value']==600
    assert captured[1]['cycle']=='YEARLY'
    assert captured[1]['billingType']=='UNDEFINED'


def test_repeated_sync_recovers_existing_subscription_without_duplicate(app):
    obj=subscription(app)
    obj.asaas_subscription_id=None
    obj.asaas_customer_id='cus_existing'
    obj.asaas_habilitado=True

    class Remote:
        def pages(self, path, params=None):
            if path=='/subscriptions':
                return iter([{'id':'sub_recovered','customer':'cus_existing'}])
            return iter(())
        def request(self, method, path, **kwargs):
            if method=='GET' and path=='/subscriptions/sub_recovered':
                return {'id':'sub_recovered','customer':'cus_existing','status':'ACTIVE'}
            if method=='PUT' and path=='/subscriptions/sub_recovered':
                return {'id':'sub_recovered','customer':'cus_existing','status':'ACTIVE'}
            raise AssertionError('Criação não deveria ocorrer quando referência já existe')

    sync_subscription(obj,Remote())
    db.session.commit()
    assert obj.asaas_subscription_id=='sub_recovered'
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura))==1


def test_timeout_then_recovery_queries_before_create(app):
    obj=subscription(app)
    obj.asaas_subscription_id=None
    obj.asaas_customer_id='cus_timeout'
    obj.asaas_habilitado=True

    class TimeoutRemote:
        def pages(self, path, params=None):
            return iter(())
        def request(self, method, path, **kwargs):
            raise TimeoutError('timeout mockado')

    with pytest.raises(TimeoutError):
        sync_subscription(obj,TimeoutRemote())

    class RecoveryRemote:
        def pages(self, path, params=None):
            if path=='/subscriptions':
                return iter([{'id':'sub_after_timeout','customer':'cus_timeout'}])
            return iter(())
        def request(self, method, path, **kwargs):
            if method=='GET' and path=='/subscriptions/sub_after_timeout':
                return {'id':'sub_after_timeout','customer':'cus_timeout','status':'ACTIVE'}
            if method=='PUT' and path=='/subscriptions/sub_after_timeout':
                return {'id':'sub_after_timeout','customer':'cus_timeout','status':'ACTIVE'}
            raise AssertionError('A recuperação deve localizar o recurso antes de criar')

    sync_subscription(obj,RecoveryRemote())
    db.session.commit()
    assert obj.asaas_subscription_id=='sub_after_timeout'
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura))==1


def test_webhook_before_charge_is_reprocessable(app):
    obj=subscription(app)
    event=receive('sandbox','t'*40,{'id':'early_event','event':'PAYMENT_CREATED',
                                    'payment':{'id':'pay_early','subscription':'sub_test'}})
    assert event
    row=db.session.scalar(db.select(EventoAsaas).filter_by(evento_externo='sandbox:early_event'))
    assert row.status=='PENDENTE'
    assert row.cobranca_id is None

    with patch('app.services.asaas_service.AsaasClient.request',return_value={
        'id':'pay_early','subscription':'sub_test','dueDate':date.today().isoformat(),
        'value':'80.00','status':'PENDING','billingType':'UNDEFINED','invoiceUrl':'https://sandbox.asaas.com/i/pay_early'
    }):
        assert process_one()
    row=db.session.scalar(db.select(EventoAsaas).filter_by(evento_externo='sandbox:early_event'))
    assert row.status=='PROCESSADO'
    charge=db.session.scalar(db.select(Cobranca).filter_by(gateway_payment_id='pay_early'))
    assert charge is not None
    assert charge.status=='AGUARDANDO_PAGAMENTO'


def test_failed_event_is_reprocessed_without_duplicate_effect(app):
    obj=subscription(app)
    receive('sandbox','t'*40,{'id':'retry_event','event':'PAYMENT_CONFIRMED',
                              'payment':{'id':'pay_retry','subscription':'sub_test'}})
    with patch('app.services.asaas_service.AsaasClient.request',side_effect=TimeoutError):
        assert process_one()
    failed=db.session.scalar(db.select(EventoAsaas).filter_by(evento_externo='sandbox:retry_event'))
    assert failed.status=='FALHA'

    payment={'id':'pay_retry','subscription':'sub_test','dueDate':date.today().isoformat(),
             'value':'80.00','status':'CONFIRMED','billingType':'UNDEFINED'}
    with patch('app.services.asaas_service.AsaasClient.request',return_value=payment):
        assert process_one()
    db.session.commit()
    failed=db.session.scalar(db.select(EventoAsaas).filter_by(evento_externo='sandbox:retry_event'))
    assert failed.status=='PROCESSADO'
    assert db.session.scalar(db.select(db.func.count()).select_from(Cobranca))==1
    assert obj.status=='TRIAL'


def test_confirmed_and_received_do_not_duplicate_payment_effect(app):
    obj=subscription(app)
    payment={'subscription':'sub_test','dueDate':date.today().isoformat(),
             'value':'80.00','billingType':'UNDEFINED'}
    apply_payment(obj,{**payment,'id':'pay_confirmed_received','status':'CONFIRMED'})
    db.session.commit()
    apply_payment(obj,{**payment,'id':'pay_confirmed_received','status':'RECEIVED'})
    db.session.commit()
    assert db.session.scalar(db.select(db.func.count()).select_from(Cobranca))==1
    assert db.session.scalar(db.select(Cobranca).filter_by(
        gateway_payment_id='pay_confirmed_received')).status=='PAGA'
    assert obj.status=='TRIAL'


def test_same_event_in_both_webhook_endpoints_processed_once(app,client):
    subscription(app)
    payload={'id':'shared_endpoint_event','event':'PAYMENT_RECEIVED',
             'payment':{'id':'pay_shared','subscription':'sub_test'}}
    headers={'asaas-access-token':'t'*40}
    old=client.post('/api/v1/webhooks/asaas/sandbox',json=payload,headers=headers)
    public=client.post('/api/asaas/webhook',json=payload,headers=headers)
    assert old.status_code==public.status_code==200
    assert old.json['status']=='recebido'
    assert public.json['status']=='duplicado'
    assert db.session.scalar(db.select(db.func.count()).select_from(EventoAsaas).where(
        EventoAsaas.ambiente=='sandbox',
        EventoAsaas.event_id=='shared_endpoint_event'))==1