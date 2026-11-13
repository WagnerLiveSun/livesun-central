import re
from flask import Flask, session, g
from app.extensions import db
from app.models import Cliente, UsuarioCentral
from app.security import passwords


def token(response):
    return re.search(r'name="csrf_token" value="([^"]+)"',response.get_data(as_text=True)).group(1)


def test_client_form_real_csrf_and_session_cookie_isolation(app):
    app.config['WTF_CSRF_ENABLED']=True
    user=UsuarioCentral(nome='Teste',email='csrf@example.com',perfil='superadmin',
        senha_hash=passwords.hash('test-password'))
    db.session.add(user);db.session.commit()
    browser=app.test_client()
    login_page=browser.get('/login')
    assert 'livesun_central_session=' in login_page.headers.get('Set-Cookie','')
    response=browser.post('/login',data={'email':user.email,'senha':'test-password','csrf_token':token(login_page)})
    assert response.status_code==302
    # Fixture mantém app_context; simule novo contexto de requisição após session.clear do login.
    g.pop('csrf_token',None)
    page=browser.get('/cadastros/clientes/novo')
    assert page.status_code==200
    csrf=token(page)
    # Cookie gerado por outro Flask, no mesmo host e outra porta.
    other=Flask('outro_produto');other.secret_key='other-product-secret'
    @other.get('/')
    def other_home():
        session['produto']='comercial'
        return 'ok'
    cookie=other.test_client().get('/').headers['Set-Cookie'].split(';',1)[0].split('=',1)[1]
    browser.set_cookie('session',cookie)
    response=browser.post('/cadastros/clientes/novo',data={'csrf_token':csrf,'razao_social':'Cliente CSRF',
        'email_principal':'client@example.com','status':'ATIVO'})
    assert response.status_code==302,response.get_data(as_text=True)
    assert db.session.scalar(db.select(Cliente).filter_by(razao_social='Cliente CSRF')) is not None


def test_invalid_csrf_explains_recovery_without_saving(app,client):
    app.config['WTF_CSRF_ENABLED']=True
    before=db.session.scalar(db.select(db.func.count()).select_from(Cliente))
    response=client.post('/cadastros/clientes/novo',data={'csrf_token':'invalid','razao_social':'Nao salvar'})
    assert response.status_code==400
    assert 'Atualize a página' in response.get_data(as_text=True)
    assert db.session.scalar(db.select(db.func.count()).select_from(Cliente))==before