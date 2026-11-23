"""Verifica geometria do menu e da cobrança em Chromium com dados isolados."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db
from app.models import Cliente, Produto, Plano, UsuarioCentral, ConfigAsaas, OperacaoAsaas
from app.models.base import now
from app.security import passwords, encrypt
from app.services.assinatura_service import create, grant_courtesy

CHECKER = r'''
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
folder=Path(sys.argv[1]); html=folder.joinpath('page.html').read_text(encoding='utf-8')
css=folder.joinpath('central.css').read_text(encoding='utf-8'); js=folder.joinpath('central.js').read_text(encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    for width in (1365, 900, 390):
        page=browser.new_page(viewport={'width':width,'height':900}, device_scale_factor=1)
        errors=[]; page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_content(html); page.add_style_tag(content=css); page.add_script_tag(content=js)
        if width <= 850: page.locator('#menu-toggle').click()
        for heading in ('Catálogo', 'Configurações'):
            group=page.locator('aside details').filter(has=page.get_by_text(heading,exact=True)).first
            group.locator('summary').click()
            rects=group.locator(':scope > a').evaluate_all('(xs)=>xs.map(x=>{const r=x.getBoundingClientRect(),s=getComputedStyle(x);return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,display:s.display}})')
            assert len(rects)>1 and all(r['display']=='block' for r in rects), (heading,rects)
            sidebar=page.locator('aside').bounding_box()
            assert all(r['x'] >= sidebar['x'] and r['right'] <= sidebar['x']+sidebar['width']+1 for r in rects), (width,heading,rects,sidebar)
            assert all(rects[i]['bottom'] <= rects[i+1]['y']+1 for i in range(len(rects)-1)), (width,heading,rects)
        assert page.get_by_text('Solicitação precisa de revisão',exact=True).count()==1
        assert page.get_by_text('Cortesia',exact=True).count()>=1
        assert page.locator('select[name="assinatura_id"]').is_enabled()
        assert page.locator('input[name="valor"]').input_value()=='100.00'
        page.locator('select[name="tipo"]').select_option('avulsa')
        assert not page.locator('input[name="valor"]').evaluate('(e)=>e.readOnly')
        assert not errors,errors
        page.close()
    browser.close()
print('Chromium: menu e cobrança sem sobreposição em 1365, 900 e 390 px; seletor funcional.')
'''


def main():
    browser_python = ROOT.parent.parent / 'LiveSun_Comercial_X/.venv313/Scripts/python.exe'
    if not browser_python.exists():
        raise SystemExit('Python de testes com Playwright indisponível.')
    app = create_app({'TESTING': True, 'DB_ENGINE': 'sqlite', 'DATABASE_URL': 'sqlite:///:memory:',
        'APP_ENV': 'development', 'SECRET_KEY': 's'*40, 'JWT_SECRET': 'j'*40,
        'ENCRYPTION_KEY': Fernet.generate_key().decode(), 'WTF_CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False})
    with tempfile.TemporaryDirectory() as folder, app.app_context():
        db.create_all()
        product = Produto(codigo='PRODUTO', nome='Produto', permite_multiplos_planos=True)
        customers = [Cliente(codigo_externo=f'TESTE{i}', razao_social=f'Cliente {i}', email_principal=f't{i}@example.com') for i in range(3)]
        db.session.add_all([product, *customers]); db.session.flush()
        plan = Plano(produto_id=product.id, codigo='PLANO', nome='Plano Base', valor_mensal=100)
        db.session.add(plan); db.session.flush()
        objects = [create({'cliente_id': c.id, 'produto_id': product.id, 'plano_id': plan.id, 'status': 'ATIVA'}) for c in customers]
        grant_courtesy(objects[0], 0, True, 'Condição de teste')
        objects[1].asaas_habilitado=True; objects[1].asaas_ambiente='sandbox'
        product.config_asaas=ConfigAsaas(ambiente='sandbox', api_key=encrypt('fake'), webhook_token=encrypt('t'*40), ativo=True)
        db.session.add(OperacaoAsaas(assinatura_id=objects[1].id, tipo='SINCRONIZAR', status='REVISAR', proxima_tentativa=now()))
        db.session.add(UsuarioCentral(nome='Operador', email='browser@example.com', perfil='superadmin', senha_hash=passwords.hash('test-only')))
        db.session.commit()
        http=app.test_client(); http.post('/login', data={'email':'browser@example.com','senha':'test-only'})
        response=http.get('/cobrancas')
        assert response.status_code == 200
        import re
        html=re.sub(r'<script\b[^>]*>.*?</script>', '', response.get_data(as_text=True), flags=re.S)
        html=re.sub(r'<link\b[^>]*>', '', html)
        output=Path(folder); output.joinpath('page.html').write_text(html,encoding='utf-8')
        output.joinpath('central.css').write_text((ROOT/'static/css/central.css').read_text(encoding='utf-8'),encoding='utf-8')
        output.joinpath('central.js').write_text((ROOT/'static/js/central.js').read_text(encoding='utf-8'),encoding='utf-8')
        output.joinpath('checker.py').write_text(CHECKER,encoding='utf-8')
        result=subprocess.run([str(browser_python),str(output/'checker.py'),folder],check=False)
        db.session.remove(); db.engine.dispose()
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())