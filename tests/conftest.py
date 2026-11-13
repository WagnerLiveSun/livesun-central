import os
import pytest
from cryptography.fernet import Fernet
from app import create_app
from app.extensions import db
from app.cli import seed
from app.models import Cliente, Produto, Plano
from app.security import service_token, encrypt


@pytest.fixture
def app():
    url = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
    engine = 'mysql' if url.startswith('mysql') else 'postgresql' if url.startswith('postgresql') else 'sqlite'
    application = create_app({'TESTING': True, 'DB_ENGINE': engine, 'DATABASE_URL': url,
        'SECRET_KEY': 's' * 40, 'JWT_SECRET': 'j' * 40, 'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'WTF_CSRF_ENABLED': False, 'RATELIMIT_ENABLED': False,
        'WEBHOOK_ALLOWED_HOSTS': ['propostas.livesun.com.br'], 'WEBHOOK_ALLOW_LOCAL_HTTP': False})
    with application.app_context():
        # TEST_DATABASE_URL precisa apontar exclusivamente para banco descartável.
        db.create_all()
        seed()
        product = db.session.scalar(db.select(Produto).filter_by(codigo='PROPOSTAS'))
        product.webhook_secret = encrypt('h' * 40)
        customer = Cliente(codigo_externo='test', razao_social='Teste', email_principal='test@example.com')
        db.session.add(customer)
        db.session.commit()
        application.test_ids = {'cliente_id': customer.id, 'produto_id': product.id,
                                'plano_id': product.planos[0].id}
        application.test_headers = {'Authorization': 'Bearer ' + service_token(product, ['read', 'write', 'webhooks'])}
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()