from unittest.mock import patch, Mock
from datetime import timedelta
from app.extensions import db
from app.models import SolicitacaoCadastro, Assinatura, Cliente, OperacaoAsaas, Cobranca, Produto, Plano
from app.models.base import now
from app.security import service_token
from app.services.cadastro_service import receive, review, deliver_one, pull_pending
from app.services.assinatura_service import BusinessError
from test_central import login
import pytest


def payload(company=10,event=None):
    return {'evento_id':event or 'cad_'+'a'*32,'empresa_id':company,'razao_social':'Nova empresa',
        'nome_fantasia':'Nova','cnpj_cpf':'12345678000190','email':'owner@example.com',
        'telefone':'11999999999','responsavel':'Responsável'}


def test_received_is_pending_without_access_or_charge(app,client):
    before=db.session.scalar(db.select(db.func.count()).select_from(Cliente))
    response=client.post('/api/v1/cadastros',json=payload(),headers=app.test_headers)
    assert response.status_code==202
    assert response.json['status']=='PENDENTE' and response.json['cliente_id'] is None
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura))==0
    assert db.session.scalar(db.select(db.func.count()).select_from(Cliente))==before
    for model in (OperacaoAsaas,Cobranca):
        assert db.session.scalar(db.select(db.func.count()).select_from(model))==0
    duplicate=client.post('/api/v1/cadastros',json=payload(),headers=app.test_headers)
    assert duplicate.status_code==200 and duplicate.json['solicitacao_id']==response.json['solicitacao_id']


def test_authenticated_read_token_can_request_but_not_approve(app,client):
    product=db.session.get(Produto,app.test_ids['produto_id'])
    headers={'Authorization':'Bearer '+service_token(product,['read'])}
    assert client.post('/api/v1/cadastros',json=payload(),headers=headers).status_code==202
    assert client.post('/api/v1/assinaturas',json=app.test_ids,headers=headers).status_code==403
    assert client.post('/api/v1/cadastros',json=payload()).status_code==401
    assert client.post('/api/v1/cadastros',json={**payload(),'senha':'never-send'},headers=headers).status_code==422


def test_request_ids_are_scoped_by_product(app,client):
    product=Produto(codigo='COMERCIAL',nome='Comercial')
    db.session.add(product);db.session.commit()
    a,_=receive(db.session.get(Produto,app.test_ids['produto_id']),payload())
    b,_=receive(product,payload())
    db.session.commit()
    assert a.id!=b.id


def test_operator_enables_and_defers_link_without_billing(app,client):
    row,_=receive(db.session.get(Produto,app.test_ids['produto_id']),payload())
    db.session.commit()
    login(client)
    assert client.get('/cadastros-recebidos').status_code==200
    assert 'Precisa ser habilitado/vinculado' in client.get('/cadastros-recebidos').get_data(as_text=True)
    response=client.post(f'/cadastros-recebidos/{row.id}/habilitar',data={
        'plano_id':app.test_ids['plano_id'],'status':'TRIAL','motivo':'Aprovação do cadastro'})
    assert response.status_code==302
    assert row.status=='VINCULO_PENDENTE'
    assert row.assinatura.status=='TRIAL' and not row.assinatura.asaas_habilitado
    assert db.session.scalar(db.select(db.func.count()).select_from(OperacaoAsaas))==0
    with pytest.raises(BusinessError):
        review(row.id,None,app.test_ids['plano_id'],'ATIVA','Duplicar não pode')


def test_link_retry_does_not_duplicate_subscription(app):
    product=db.session.get(Produto,app.test_ids['produto_id'])
    product.url_producao='https://propostas.livesun.com.br'
    row,_=receive(product,payload());db.session.commit()
    review(row.id,None,app.test_ids['plano_id'],'ATIVA','Cadastro autorizado');db.session.commit()
    with patch('app.services.cadastro_service.validate_destination'),patch('requests.Session.post',side_effect=TimeoutError):
        assert deliver_one()
    assert row.status=='VINCULO_PENDENTE' and row.erro_vinculo
    row.proxima_tentativa=now()-timedelta(seconds=1);db.session.commit()
    response=Mock(status_code=200);response.json.return_value={'evento_id':row.evento_origem}
    with patch('app.services.cadastro_service.validate_destination'),patch('requests.Session.post',return_value=response):
        assert deliver_one()
    assert row.status=='VINCULADA'
    assert db.session.scalar(db.select(db.func.count()).select_from(Assinatura))==1


def test_auditor_cannot_enable(app,client):
    row,_=receive(db.session.get(Produto,app.test_ids['produto_id']),payload());db.session.commit()
    login(client,'auditor')
    assert client.post(f'/cadastros-recebidos/{row.id}/habilitar',data={'plano_id':app.test_ids['plano_id']}).status_code==403
    assert row.status=='PENDENTE'


def test_worker_collects_paginated_outbox(app):
    product=Produto(codigo='COMERCIAL',nome='Comercial',url_producao='https://comercial.example',webhook_secret='unused')
    db.session.add(product);db.session.commit()
    r1=Mock(status_code=200,content=b'{}');r1.json.return_value={'cadastros':[{'dados':payload()}],'proximo':1}
    r2=Mock(status_code=200,content=b'{}');r2.json.return_value={'cadastros':[{'dados':payload(11,'cad_'+'b'*32)}],'proximo':None}
    with patch('app.services.cadastro_service.validate_destination'),patch('app.services.cadastro_service.decrypt',return_value='h'*40),patch('requests.Session.get',side_effect=[r1,r2]) as get:
        pull_pending()
        assert get.call_count==2
    assert db.session.scalar(db.select(db.func.count()).select_from(SolicitacaoCadastro))==2