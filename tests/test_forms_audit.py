from html.parser import HTMLParser
from datetime import date
from app.extensions import db
from app.models import Produto, Plano, Modulo, PlanoModulo, Assinatura
from app.services.assinatura_service import create
from test_central import login


class Controls(HTMLParser):
    def __init__(self):
        super().__init__();self.selects=[];self.current=None;self.inputs=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='select':
            self.current={'attrs':attrs,'options':[]};self.selects.append(self.current)
        elif tag=='option' and self.current is not None:self.current['options'].append(attrs)
        elif tag=='input':self.inputs.append(attrs)
    def handle_endtag(self,tag):
        if tag=='select':self.current=None


def controls(response):
    assert response.status_code==200,response.get_data(as_text=True)
    parser=Controls();parser.feed(response.get_data(as_text=True));return parser


def make_product():
    product=Produto(codigo='COMERCIAL',nome='Comercial',permite_multiplos_planos=True)
    db.session.add(product);db.session.flush()
    first=Plano(produto_id=product.id,codigo='PREMIUM',nome='Premium',valor_mensal=99)
    db.session.add(first);db.session.commit()
    return product,first


def test_plan_change_explains_only_current_plan_and_disables_submit(app,client):
    product,plan=make_product()
    sub=create({'cliente_id':app.test_ids['cliente_id'],'produto_id':product.id,'plano_id':plan.id})
    db.session.commit();login(client)
    for path in ('/assinaturas',f'/assinaturas/{sub.id}'):
        response=client.get(path);parsed=controls(response)
        select=next(s for s in parsed.selects if s['attrs'].get('name')=='plano_id')
        assert 'disabled' in select['attrs']
        assert select['options']==[{'value':''}]
        html=response.get_data(as_text=True)
        assert 'não possui outro plano ativo' in html
        assert f'/cadastros/planos/novo?produto={product.id}' in html
        assert 'disabled>Confirmar plano' in html


def test_plan_change_only_lists_active_same_product_alternatives_and_saves(app,client):
    product,plan=make_product()
    alternative=Plano(produto_id=product.id,codigo='BASIC',nome='Básico',valor_mensal=49)
    inactive=Plano(produto_id=product.id,codigo='INTERMEDIATE',nome='Inativo',ativo=False)
    db.session.add_all([alternative,inactive]);db.session.flush()
    sub=create({'cliente_id':app.test_ids['cliente_id'],'produto_id':product.id,'plano_id':plan.id})
    db.session.commit();login(client)
    for path in ('/assinaturas',f'/assinaturas/{sub.id}'):
        parsed=controls(client.get(path))
        select=next(s for s in parsed.selects if s['attrs'].get('name')=='plano_id')
        assert 'disabled' not in select['attrs']
        assert [o['value'] for o in select['options']]==[str(alternative.id)]
    response=client.post(f'/assinaturas/{sub.id}/plano',data={'plano_id':alternative.id,'retorno':'painel'})
    assert response.status_code==302
    assert sub.plano_id==alternative.id


def test_catalog_selects_keep_defaults_and_never_fall_back_to_free_id(app,client):
    login(client)
    parsed=controls(client.get('/cadastros/clientes/novo'))
    status=next(s for s in parsed.selects if s['attrs'].get('name')=='status')
    assert next(o for o in status['options'] if 'selected' in o)['value']=='ATIVO'
    for kind in ('produtos','usuarios'):
        parsed=controls(client.get('/cadastros/'+kind+'/novo'))
        active=next(i for i in parsed.inputs if i.get('name')=='ativo')
        assert 'checked' in active
    parsed=controls(client.get('/cadastros/modulos/novo'))
    product=next(s for s in parsed.selects if s['attrs'].get('name')=='produto_id')
    assert 'disabled' in product['attrs']
    assert not any(i.get('name')=='produto_id' and i.get('type')=='text' for i in parsed.inputs)


def test_plan_module_composition_visible_checked_and_submits(app,client):
    product=Produto(codigo='FUTURO',nome='Futuro',permite_multiplos_planos=True,permite_modulos=True)
    db.session.add(product);db.session.flush()
    module=Modulo(produto_id=product.id,codigo='FINANCEIRO',nome='Financeiro')
    plan=Plano(produto_id=product.id,codigo='BASE',nome='Base')
    db.session.add_all([module,plan]);db.session.flush()
    db.session.add(PlanoModulo(plano_id=plan.id,modulo_id=module.id,liberado=True));db.session.commit()
    login(client)
    parsed=controls(client.get(f'/cadastros/planos/{plan.id}/editar'))
    checkbox=next(i for i in parsed.inputs if i.get('name')=='modulo_id')
    assert checkbox['value']==str(module.id) and 'checked' in checkbox
    response=client.post(f'/planos/{plan.id}/modulos',data={'modulo_id':str(module.id)})
    assert response.status_code==302
    assert db.session.scalar(db.select(PlanoModulo).filter_by(plano_id=plan.id)).liberado


def test_empty_billing_and_catalog_states_block_invalid_forms(app,client):
    login(client)
    response=client.get('/cobrancas');parsed=controls(response)
    assert 'disabled' in next(s for s in parsed.selects if s['attrs'].get('name')=='assinatura_id')['attrs']
    assert 'disabled>Criar cobrança' in response.get_data(as_text=True)
    client_obj=db.session.get(__import__('app.models',fromlist=['Cliente']).Cliente,app.test_ids['cliente_id'])
    client_obj.status='INATIVO';db.session.commit()
    parsed=controls(client.get('/assinaturas/nova'))
    assert 'disabled' in next(s for s in parsed.selects if s['attrs'].get('name')=='cliente_id')['attrs']


def test_edit_plan_in_inactive_product_keeps_its_selected_product(app,client):
    product,plan=make_product();product.ativo=False;db.session.commit();login(client)
    parsed=controls(client.get(f'/cadastros/planos/{plan.id}/editar'))
    selected=next(s for s in parsed.selects if s['attrs'].get('id')=='plan-product')
    assert next(o for o in selected['options'] if 'selected' in o)['value']==str(product.id)


def test_every_rendered_post_form_has_csrf_and_selects_are_not_empty(app,client):
    product,plan=make_product()
    sub=create({'cliente_id':app.test_ids['cliente_id'],'produto_id':product.id,'plano_id':plan.id})
    db.session.commit();login(client)
    paths=['/login','/','/cadastros/clientes/novo','/cadastros/produtos/novo','/cadastros/planos/novo',
        f'/cadastros/planos/{plan.id}/editar','/cadastros/modulos/novo','/cadastros/usuarios/novo',
        '/assinaturas','/assinaturas/nova',f'/assinaturas/{sub.id}','/cobrancas','/webhooks',
        '/integracoes',f'/produtos/{product.id}/cobranca','/cadastros-recebidos','/configuracoes']
    class Audit(HTMLParser):
        def __init__(self):super().__init__();self.forms=[];self.form=None;self.nested=False
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='form':
                self.nested |= self.form is not None
                self.form={'attrs':attrs,'csrf':False};self.forms.append(self.form)
            if tag=='input' and self.form and attrs.get('name')=='csrf_token':self.form['csrf']=True
        def handle_endtag(self,tag):
            if tag=='form':self.form=None
    for path in paths:
        response=client.get(path);parsed=controls(response)
        assert all(s['options'] for s in parsed.selects),path
        audit=Audit();audit.feed(response.get_data(as_text=True))
        assert not audit.nested,path
        assert all(f['csrf'] for f in audit.forms if f['attrs'].get('method','get').lower()=='post'),path