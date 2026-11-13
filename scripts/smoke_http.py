"""Smoke HTTP real local, banco temporário, sem credenciais/serviços externos."""
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests
from cryptography.fernet import Fernet
from werkzeug.serving import make_server, WSGIRequestHandler
from flask_migrate import upgrade
from app import create_app
from app.cli import seed
from app.extensions import db
from app.models import Cliente, Produto
from app.security import service_token


class QuietHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = create_app({'TESTING': True, 'DB_ENGINE': 'sqlite',
            'DATABASE_URL': 'sqlite:///'+str(Path(folder)/'smoke.db'), 'SECRET_KEY': 's'*40,
            'JWT_SECRET': 'j'*40, 'ENCRYPTION_KEY': Fernet.generate_key().decode(),
            'RATELIMIT_ENABLED': False})
        with app.app_context():
            upgrade()
            seed()
            product = db.session.scalar(db.select(Produto))
            customer = Cliente(codigo_externo='smoke', razao_social='Smoke', email_principal='smoke@example.com')
            db.session.add(customer)
            db.session.commit()
            headers = {'Authorization': 'Bearer '+service_token(product, ['read', 'write'])}
            data = {'cliente_id': customer.id, 'produto_id': product.id, 'plano_id': product.planos[0].id}
        server = make_server('127.0.0.1', 0, app, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            assert requests.get(base+'/api/v1/health', timeout=5).status_code == 200
            assert requests.get(base+'/login', timeout=5).status_code == 200
            assert requests.get(base+'/static/images/logo.png', timeout=5).status_code == 200
            created = requests.post(base+'/api/v1/assinaturas', headers=headers, json=data, timeout=5)
            assert created.status_code == 201, created.text
            identifier = created.json()['id']
            blocked = requests.patch(base+f'/api/v1/assinaturas/{identifier}/status', headers=headers,
                json={'status': 'SUSPENSA', 'motivo': 'Teste HTTP local'}, timeout=5)
            assert blocked.status_code == 200 and not blocked.json()['acesso_produto']
            print('HTTP smoke: health, login, logo, criação e suspensão OK.')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == '__main__':
    main()