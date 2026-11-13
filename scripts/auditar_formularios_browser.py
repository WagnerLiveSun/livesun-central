"""Renderiza formulários reais em banco temporário e valida JS em Chromium separado."""
import sys
import subprocess
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db
from app.models import Cliente, Produto, Plano, UsuarioCentral
from app.services.assinatura_service import create
from app.security import passwords

ROOT=Path(__file__).resolve().parent.parent
PLAYWRIGHT_PYTHON=ROOT.parent.parent/'LiveSun_Comercial_X/.venv313/Scripts/python.exe'
CHECKER=r'''
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
folder=Path(sys.argv[1]);js=Path(sys.argv[2]).read_text(encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    def load(name):
        page.goto('about:blank')
        page.set_content((folder/name).read_text(encoding='utf-8'))
        page.add_script_tag(content=js)
        assert page.locator('select').evaluate_all('(xs)=>xs.every(x=>x.options.length>0)'),name
    load('one-plan.html')
    page.locator('[data-dialog="plano-1"]').click()
    dialog=page.locator('#plano-1')
    assert dialog.is_visible()
    assert dialog.locator('select').is_disabled()
    assert dialog.get_by_text('Confirmar plano',exact=True).is_disabled()
    assert 'não possui outro plano ativo' in dialog.inner_text()
    dialog.locator('[data-close-dialog]').click()
    load('two-plans.html')
    page.locator('[data-dialog="plano-1"]').click()
    dialog=page.locator('#plano-1');select=dialog.locator('select[name="plano_id"]')
    assert select.is_enabled()
    assert select.locator('option').count()==1
    assert select.locator('option').first.text_content().startswith('Básico')
    assert dialog.get_by_text('Confirmar plano',exact=True).is_enabled()
    assert select.input_value()==(folder/'alternative-id.txt').read_text()
    dialog.locator('[data-close-dialog]').click()
    load('new-subscription.html')
    page.locator('#new-subscription-form [name="produto_id"]').select_option((folder/'product-id.txt').read_text())
    assert page.locator('#new-subscription-form [name="plano_id"]').is_enabled()
    assert page.locator('#create-subscription-button').is_enabled()
    load('plan-form.html')
    assert page.locator('#commercial-tier').is_enabled()
    page.locator('#commercial-tier').select_option('BASIC')
    assert page.locator('#commercial-tier').input_value()=='BASIC'
    for name in ('client.html','product.html','modules.html','users.html','charges.html','webhooks.html','billing.html','connections.html'):
        load(name)
    assert not errors,errors
    browser.close()
print('Chromium: diálogos com/sem alternativa, seletor da nova assinatura, categoria e demais formulários renderizados OK.')
'''


def main():
    if not PLAYWRIGHT_PYTHON.exists():
        raise SystemExit('Python com Playwright não encontrado; instale a ferramenta de teste separadamente.')
    app=create_app({'TESTING':True,'DB_ENGINE':'sqlite','DATABASE_URL':'sqlite:///:memory:',
        'APP_ENV':'development','SECRET_KEY':'s'*40,'JWT_SECRET':'j'*40,
        'ENCRYPTION_KEY':Fernet.generate_key().decode(),'WTF_CSRF_ENABLED':False,'RATELIMIT_ENABLED':False})
    with tempfile.TemporaryDirectory() as folder, app.app_context():
        output=Path(folder)
        db.create_all()
        product=Produto(codigo='COMERCIAL',nome='Comercial',permite_multiplos_planos=True)
        customer=Cliente(codigo_externo='LOCAL',razao_social='Teste',email_principal='test@example.com')
        db.session.add_all([product,customer]);db.session.flush()
        plan=Plano(produto_id=product.id,codigo='PREMIUM',nome='Premium',valor_mensal=99)
        db.session.add(plan);db.session.flush()
        sub=create({'cliente_id':customer.id,'produto_id':product.id,'plano_id':plan.id})
        user=UsuarioCentral(nome='Teste',email='browser@example.com',perfil='superadmin',senha_hash=passwords.hash('test-only'))
        db.session.add(user);db.session.commit()
        http=app.test_client();http.post('/login',data={'email':user.email,'senha':'test-only'})
        def save(name,path):
            response=http.get(path)
            assert response.status_code==200,(path,response.status_code)
            # Evita carregar assets externos: injeta apenas o JS real no navegador.
            import re
            html=response.get_data(as_text=True)
            html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.S)
            html=re.sub(r'<link\b[^>]*>','',html)
            output.joinpath(name).write_text(html,encoding='utf-8')
        save('one-plan.html',f'/assinaturas/{sub.id}')
        alternate=Plano(produto_id=product.id,codigo='BASIC',nome='Básico',valor_mensal=49)
        db.session.add(alternate);db.session.commit()
        save('two-plans.html',f'/assinaturas/{sub.id}')
        output.joinpath('alternative-id.txt').write_text(str(alternate.id))
        output.joinpath('product-id.txt').write_text(str(product.id))
        for name,path in {'new-subscription.html':'/assinaturas/nova','plan-form.html':f'/cadastros/planos/novo?produto={product.id}',
            'client.html':'/cadastros/clientes/novo','product.html':'/cadastros/produtos/novo','modules.html':'/cadastros/modulos/novo',
            'users.html':'/cadastros/usuarios/novo','charges.html':'/cobrancas','webhooks.html':'/webhooks',
            'billing.html':f'/produtos/{product.id}/cobranca','connections.html':'/integracoes'}.items():save(name,path)
        output.joinpath('checker.py').write_text(CHECKER,encoding='utf-8')
        result=subprocess.run([str(PLAYWRIGHT_PYTHON),str(output/'checker.py'),folder,str(ROOT/'static/js/central.js')],check=False)
        db.session.remove();db.engine.dispose()
        return result.returncode


if __name__=='__main__':
    sys.exit(main())