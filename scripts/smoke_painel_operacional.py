"""Valida renderização do painel com dados descartáveis, sem gateway externo."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db
from app.models import Cliente,Produto,Plano,UsuarioCentral
from app.security import passwords
from app.services.assinatura_service import create,grant_courtesy

app=create_app({'TESTING':True,'APP_ENV':'development','DB_ENGINE':'sqlite','DATABASE_URL':'sqlite:///:memory:',
    'SECRET_KEY':'s'*40,'JWT_SECRET':'j'*40,'ENCRYPTION_KEY':Fernet.generate_key().decode(),
    'WTF_CSRF_ENABLED':False,'RATELIMIT_ENABLED':False})
with app.app_context():
    db.create_all()
    client=Cliente(codigo_externo='SMOKE',razao_social='Empresa de teste',email_principal='test@example.com')
    product=Produto(codigo='COMERCIAL',nome='LiveSun Comercial',permite_multiplos_planos=True)
    db.session.add_all([client,product]);db.session.flush()
    plan=Plano(produto_id=product.id,codigo='BASIC',nome='Básico',valor_mensal=49)
    db.session.add(plan);db.session.flush()
    sub=create({'cliente_id':client.id,'produto_id':product.id,'plano_id':plan.id})
    grant_courtesy(sub,0,True,'Bonificação preservada')
    user=UsuarioCentral(nome='Operador de teste',email='operator@example.com',perfil='superadmin',senha_hash=passwords.hash('test-only'))
    db.session.add(user);db.session.commit()
    http=app.test_client()
    http.post('/login',data={'email':user.email,'senha':'test-only'})
    for path in ('/assinaturas',f'/assinaturas/{sub.id}',f'/produtos/{product.id}/cobranca','/integracoes','/cobrancas'):
        response=http.get(path)
        assert response.status_code==200,path
        app.jinja_env.parse(response.get_data(as_text=True))
        print(path+': render OK')
    page=http.get('/assinaturas').get_data(as_text=True)
    for word in ('Suspender','Bloquear','Bonificação','data-dialog='):
        assert word in page
    print('Painel com ações e bonificação: OK. Nenhuma rede externa utilizada.')