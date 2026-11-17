from decimal import Decimal
from unittest.mock import patch, Mock
import pytest
from app.extensions import db
from app.models import Produto, Plano, Assinatura, Cliente, Cobranca, OperacaoAsaas, Auditoria
from app.schemas import PlanoInput
from app.services import catalogo_comercial_service as catalog
from app.services import empresas_comercial_service as companies
from app.services.assinatura_service import BusinessError
from app.services.cadastro_service import deliver_one
from app.security import encrypt
from test_central import login
from test_empresas_comercial import company


def offer(identifier=1, **changes):
    return {'id':identifier, 'categoria':'premium', 'nome':'Premium Comercial', 'periodicidade':'mensal',
        'versao':1, 'preco':'99.90', 'moeda':'BRL', 'usuarios':7, 'ativo':True,
        'contratado':True, 'vigencia_inicio':None, 'vigencia_fim':None, **changes}


@pytest.fixture
def commercial_product(app):
    item = Produto(codigo='COMERCIAL',nome='Comercial',permite_multiplos_planos=True,
        url_producao='https://app.livesun.com.br',webhook_secret=encrypt('c'*40),ativo=True)
    db.session.add(item)
    db.session.commit()
    return item


def preview(rows):
    with patch.object(catalog, 'source_catalog', return_value=rows):
        return catalog.preview()


def import_rows(rows, selected=None):
    with patch.object(catalog, 'source_catalog', return_value=rows):
        current=catalog.preview()
        return catalog.import_selected(current['hash'], selected or ['PREMIUM'], True)


def test_preview_creates_nothing_and_import_is_idempotent(app, commercial_product):
    before=db.session.query(Cliente).count()
    result=preview([offer()])
    assert result['linhas'][0]['acao']=='CRIAR'
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==0
    assert import_rows([offer()])==1
    db.session.commit()
    plan=db.session.query(Plano).filter_by(produto_id=commercial_product.id).one()
    assert plan.codigo=='PREMIUM' and plan.valor_mensal==Decimal('99.90')
    assert plan.periodicidade=='mensal' and plan.limite_usuarios==7
    assert import_rows([offer()])==0
    db.session.commit()
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==1
    assert db.session.query(Cliente).count()==before
    assert db.session.query(Assinatura).count()==db.session.query(Cobranca).count()==db.session.query(OperacaoAsaas).count()==0
    event=db.session.query(Auditoria).filter_by(acao='CATALOGO_COMERCIAL_IMPORTADO').one()
    assert event.novo['ofertas_origem']==[offer()]


def test_imports_multiple_tiers_and_cycles_without_manual_recreation(app, commercial_product):
    offers=[offer(1,categoria='basic',nome='Básico',preco='49.90'),
            offer(2),offer(3,periodicidade='anual',preco='999.00')]
    assert import_rows(offers,['BASIC','PREMIUM','PREMIUM_ANUAL'])==3
    db.session.commit()
    assert {row.codigo for row in db.session.query(Plano).filter_by(produto_id=commercial_product.id)}=={
        'BASIC','PREMIUM','PREMIUM_ANUAL'}


@pytest.mark.parametrize('changes',[{'preco':'120.00'}, {'usuarios':99}, {'moeda':'USD'}])
def test_conflicting_versions_require_review(app, commercial_product, changes):
    offers=[offer(),offer(2,versao=2,**changes)]
    assert preview(offers)['linhas'][0]['acao']=='REVISAR'
    with pytest.raises(BusinessError):import_rows(offers)
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==0


def test_equal_versions_can_share_one_plan(app, commercial_product):
    offers=[offer(),offer(2,versao=2)]
    assert len(preview(offers)['linhas'])==1
    assert import_rows(offers)==1


def test_existing_different_plan_is_never_overwritten(app, commercial_product):
    plan=Plano(produto_id=commercial_product.id,codigo='PREMIUM',nome='Contrato existente',
        valor_mensal=Decimal('200.00'),periodicidade='mensal',limite_usuarios=7,ativo=True)
    db.session.add(plan);db.session.commit()
    assert preview([offer()])['linhas'][0]['acao']=='REVISAR'
    with pytest.raises(BusinessError):import_rows([offer()])
    db.session.refresh(plan)
    assert plan.valor_mensal==Decimal('200.00')


@pytest.mark.parametrize('changes',[{'preco':'NaN'},{'preco':'-1'},{'preco':'1.001'},
    {'preco':None},{'usuarios':-1},{'categoria':'inventado'},{'periodicidade':'semanal'}])
def test_invalid_origin_never_becomes_plan(app, commercial_product, changes):
    with pytest.raises(BusinessError):catalog.validate_offer(offer(**changes))


def test_changed_catalog_rejects_stale_preview(app, commercial_product):
    before=preview([offer()])
    with patch.object(catalog,'source_catalog',return_value=[offer(preco='110.00')]), pytest.raises(BusinessError):
        catalog.import_selected(before['hash'],['PREMIUM'],True)
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==0


def test_catalog_follows_all_pages(app, commercial_product):
    first={'planos':[offer()],'proximo':1}
    second={'planos':[offer(2,versao=2)],'proximo':None}
    with patch.object(catalog,'fetch',side_effect=[first,second]) as fetch:
        assert len(catalog.source_catalog())==2
    assert [call.args[0] for call in fetch.call_args_list]==['/central/planos?apos=0','/central/planos?apos=1']


def test_bad_pagination_not_imported_partially(app, commercial_product):
    with patch.object(catalog,'fetch',return_value={'planos':[offer()],'proximo':0}), pytest.raises(BusinessError):
        catalog.source_catalog()


@pytest.mark.parametrize('role',['suporte','auditor','financeiro'])
def test_readonly_roles_cannot_import(app,client,commercial_product,role):
    login(client,role)
    with patch.object(catalog,'source_catalog') as source:
        assert client.post('/empresas-comercial/planos/importar').status_code==403
        source.assert_not_called()


def test_import_requires_csrf_and_explicit_confirmation(app,client,commercial_product):
    login(client)
    app.config['WTF_CSRF_ENABLED']=True
    assert client.post('/empresas-comercial/planos/importar').status_code==400
    app.config['WTF_CSRF_ENABLED']=False
    with pytest.raises(BusinessError):catalog.import_selected('',['PREMIUM'],False)


def test_page_shows_origin_prices_and_reuses_existing_plan(app,client,commercial_product):
    login(client)
    with patch.object(catalog,'source_catalog',return_value=[offer()]):
        response=client.get('/empresas-comercial/planos')
    assert response.status_code==200
    text=response.get_data(as_text=True)
    assert 'BRL 99.90' in text and 'Importar planos selecionados' in text
    assert 'value="PREMIUM"' in text


def test_catalog_to_subscription_to_worker_without_billing(app,commercial_product):
    assert import_rows([offer()])==1
    db.session.commit()
    plan=db.session.query(Plano).filter_by(produto_id=commercial_product.id,codigo='PREMIUM').one()
    origin=company()
    with patch.object(companies,'company',return_value=origin):
        row=companies.prepare_registration(10)
        db.session.commit()
        companies.confirm(row.id,None,plan.id,companies.fingerprint(origin),True,'Migração conferida na prévia')
        db.session.commit()
    response=Mock(status_code=200)
    response.json.return_value={'evento_id':row.evento_origem}
    with patch('app.services.cadastro_service.validate_destination'),patch('requests.Session.post',return_value=response):
        assert deliver_one()
    assert row.status=='VINCULADA' and row.assinatura.plano_id==plan.id
    assert row.assinatura.data_inicio.isoformat()=='2024-01-15'
    assert not row.assinatura.asaas_habilitado
    assert db.session.query(Cobranca).count()==db.session.query(OperacaoAsaas).count()==0


def test_one_conflict_prevents_partial_import(app,commercial_product):
    rows=[offer(),offer(2,categoria='basic',moeda='USD')]
    with pytest.raises(BusinessError):import_rows(rows,['PREMIUM','BASIC'])
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==0


def test_inactive_contracted_offer_can_be_preserved_explicitly(app,commercial_product):
    rows=[offer(ativo=False,contratado=True)]
    assert import_rows(rows)==1
    db.session.commit()
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).one().valor_mensal==Decimal('99.90')


def test_post_import_creates_plan_then_redirects_to_preview(app,client,commercial_product):
    login(client)
    rows=[offer()]
    with patch.object(catalog,'source_catalog',return_value=rows):
        view=catalog.preview()
        response=client.post('/empresas-comercial/planos/importar',data={
            'origem_hash':view['hash'],'planos':'PREMIUM','confirmacao':'CONFERIDO'})
    assert response.status_code==302 and response.location.endswith('/empresas-comercial/planos')
    assert db.session.query(Plano).filter_by(produto_id=commercial_product.id).count()==1


def test_empty_catalog_has_direct_message_without_empty_table(app,client,commercial_product):
    login(client)
    with patch.object(catalog,'source_catalog',return_value=[]):
        response=client.get('/empresas-comercial/planos')
    text=response.get_data(as_text=True)
    assert response.status_code==200
    assert 'Não há planos cadastrados no catálogo do Comercial para importar.' in text
    assert 'Empresas do Comercial</a>' in text
    assert '<table>' not in text
    assert 'A migração não inventa' not in text
    assert '0 oferta(s)' not in text
    assert 'name="planos"' not in text