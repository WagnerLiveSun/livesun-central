import pytest
from app.extensions import db
from app.models import Produto, Plano
from test_central import login


def commercial():
    product=Produto(codigo='COMERCIAL',nome='LiveSun Comercial',permite_multiplos_planos=True)
    db.session.add(product);db.session.commit()
    return product


@pytest.mark.parametrize('tier,cycle,expected',[
    ('BASIC','mensal','BASIC'),('INTERMEDIATE','mensal','INTERMEDIATE'),
    ('PREMIUM','anual','PREMIUM_ANUAL'),('Básico','anual','BASIC_ANUAL')])
def test_commercial_plan_created_without_manual_code(app,client,tier,cycle,expected):
    product=commercial();login(client)
    response=client.post('/cadastros/planos/novo',data={'produto_id':product.id,
        'categoria_comercial':tier,'nome':'Plano de teste','periodicidade':cycle,
        'valor_mensal':'49.00','ativo':'on'})
    assert response.status_code==302,response.get_data(as_text=True)
    plan=db.session.scalar(db.select(Plano).filter_by(produto_id=product.id))
    assert plan.codigo==expected and plan.periodicidade==cycle


def test_form_preselects_product_and_uses_category_not_code(app,client):
    product=commercial();login(client)
    response=client.get(f'/cadastros/planos/novo?produto={product.id}')
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert 'name="categoria_comercial"' in html
    assert 'name="codigo"' not in html
    assert 'Básico' in html and 'Intermediário' in html and 'Premium' in html


def test_old_form_lowercase_code_is_normalized(app,client):
    product=commercial();login(client)
    response=client.post('/cadastros/planos/novo',data={'produto_id':product.id,
        'codigo':'basic','nome':'Básico','periodicidade':'mensal','valor_mensal':'49','ativo':'on'})
    assert response.status_code==302
    assert db.session.scalar(db.select(Plano).filter_by(produto_id=product.id)).codigo=='BASIC'


def test_edit_preserves_code_without_posting_code(app,client):
    product=commercial()
    plan=Plano(produto_id=product.id,codigo='BASIC',nome='Básico',valor_mensal=49,periodicidade='mensal')
    db.session.add(plan);db.session.commit();login(client)
    response=client.post(f'/cadastros/planos/{plan.id}/editar',data={'produto_id':product.id,
        'nome':'Básico atualizado','valor_mensal':'59','periodicidade':'mensal','ativo':'on'})
    assert response.status_code==302
    assert plan.codigo=='BASIC' and plan.nome=='Básico atualizado'


def test_missing_category_returns_clear_message(app,client):
    product=commercial();login(client)
    response=client.post('/cadastros/planos/novo',data={'produto_id':product.id,
        'nome':'Plano qualquer','periodicidade':'mensal','ativo':'on'})
    assert response.status_code==422
    assert 'Selecione a categoria' in response.get_data(as_text=True)