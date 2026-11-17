from unittest.mock import patch
import pytest
from app.extensions import db
from app.models import Cliente, Produto, SolicitacaoCadastro
from app.services.cadastro_service import receive, resolve_customer
from app.services.assinatura_service import BusinessError
from test_autocadastro import payload
from test_central import login


def existing(status='ATIVO'):
    customer = Cliente(codigo_externo='documento-existente', razao_social='Cliente encontrado',
        cnpj_cpf='12.345.678/0001-90', email_principal='cliente@example.com', status=status)
    db.session.add(customer)
    db.session.commit()
    return customer


def registration(app):
    row, _ = receive(db.session.get(Produto, app.test_ids['produto_id']), payload())
    db.session.commit()
    return row


@pytest.mark.parametrize('status',['ATIVO','INATIVO','EXCLUIDO'])
def test_preview_exposes_matching_customer_and_status(app,client,status):
    login(client)
    customer=existing(status)
    row=registration(app)
    response=client.get(f'/cadastros-recebidos/{row.id}')
    text=response.get_data(as_text=True)
    assert response.status_code==200
    assert 'Clientes com este CPF/CNPJ' in text
    assert f'#{customer.id}' in text and status in text
    assert f'/cadastros/clientes/{customer.id}/editar' in text
    assert 'Criar cliente com os dados recebidos' not in text
    if status=='ATIVO':
        assert f'<option value="{customer.id}">' in text
    else:
        assert f'<option value="{customer.id}">' not in text
        assert 'Revise a situação do cliente antes de vincular.' in text


def test_document_search_finds_customer_outside_first_page(app,client):
    login(client)
    customer=existing('INATIVO')
    for number in range(35):
        db.session.add(Cliente(codigo_externo=f'outro-{number}',razao_social=f'Outro {number}',
            email_principal=f'outro{number}@example.com',status='ATIVO'))
    db.session.commit()
    assert 'Cliente encontrado' not in client.get('/cadastros/clientes').get_data(as_text=True)
    response=client.get('/cadastros/clientes?documento=12345678000190')
    text=response.get_data(as_text=True)
    assert response.status_code==200
    assert 'Cliente encontrado' in text and 'INATIVO' in text and '12.345.678/0001-90' in text
    assert 'Outro 34' not in text
    assert client.get('/cadastros/clientes?documento=abc').status_code==200


def test_no_automatic_merge_or_reactivation(app):
    customer=existing('INATIVO')
    row=registration(app)
    before=db.session.query(Cliente).count()
    with pytest.raises(BusinessError,match='inativo ou excluído'):
        resolve_customer(row,None)
    with pytest.raises(BusinessError,match='inativo'):
        resolve_customer(row,customer.id)
    assert customer.status=='INATIVO' and db.session.query(Cliente).count()==before


def test_existing_active_requires_explicit_selection(app):
    customer=existing()
    row=registration(app)
    with pytest.raises(BusinessError,match='Selecione-o'):
        resolve_customer(row,None)
    assert resolve_customer(row,customer.id).id==customer.id


def test_legacy_preview_also_shows_matching_customer(app,client):
    from test_empresas_comercial import company
    from app.services import empresas_comercial_service as service
    from app.models import Plano
    login(client)
    customer=existing()
    product=Produto(codigo='COMERCIAL',nome='Comercial',ativo=True)
    db.session.add(product);db.session.flush()
    db.session.add(Plano(produto_id=product.id,codigo='PREMIUM',nome='Premium',ativo=True,
                        periodicidade='mensal',valor_mensal='99.90'))
    row,_=receive(product,company()['dados']);db.session.commit()
    with patch.object(service,'company',return_value=company()):
        response=client.get(f'/cadastros-recebidos/{row.id}')
    text=response.get_data(as_text=True)
    assert response.status_code==200
    assert 'Clientes com este CPF/CNPJ' in text
    assert f'<option value="{customer.id}">' in text
    assert 'Criar cliente com os dados recebidos' not in text