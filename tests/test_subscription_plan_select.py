from html.parser import HTMLParser
from app.extensions import db
from app.models import Produto, Plano, Assinatura
from test_central import login


class PlanOptions(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_plans=False; self.options=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='select':self.in_plans=attrs.get('name')=='plano_id'
        if tag=='option' and self.in_plans:self.options.append(attrs)
    def handle_endtag(self,tag):
        if tag=='select':self.in_plans=False


def test_new_plan_has_product_metadata_and_can_be_assigned(app,client):
    product=Produto(codigo='COMERCIAL',nome='LiveSun Comercial',permite_multiplos_planos=True)
    db.session.add(product);db.session.flush()
    plan=Plano(produto_id=product.id,codigo='BASIC',nome='Básico',valor_mensal=49,ativo=True)
    inactive=Plano(produto_id=product.id,codigo='PREMIUM',nome='Inativo',valor_mensal=99,ativo=False)
    db.session.add_all([plan,inactive]);db.session.commit()
    login(client)
    response=client.get('/assinaturas/nova')
    assert response.status_code==200
    parser=PlanOptions();parser.feed(response.get_data(as_text=True))
    option=next(o for o in parser.options if o['value']==str(plan.id))
    assert option['data-product']==str(product.id)
    assert all('data-product' in o for o in parser.options)
    assert not any(o['value']==str(inactive.id) for o in parser.options)
    response=client.post('/assinaturas/nova',data={'cliente_id':app.test_ids['cliente_id'],
        'produto_id':product.id,'plano_id':plan.id,'status':'TRIAL'})
    assert response.status_code==302
    assert db.session.scalar(db.select(Assinatura).filter_by(produto_id=product.id)).plano_id==plan.id