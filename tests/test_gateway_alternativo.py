import json

import pytest

from app.extensions import db
from app.models import Auditoria, GatewayAlternativo
from app.security import decrypt
from test_central import login


def gateway_form(app, **values):
    return {'produto_id': str(app.test_ids['produto_id']), 'nome': 'Banco Teste',
            'ambiente': 'sandbox', 'url_api': 'https://pagamentos.example/api',
            'url_callback': 'https://central.example/callback',
            'api_key': 'segredo-privado', 'client_id': 'abc',
            'ativo': 'on', 'confirmacao': 'CONFIRMAR', **values}


def test_create_and_edit_gateway_keeps_secrets_encrypted_and_out_of_audit(app, client):
    login(client)
    assert client.post('/configuracoes/gateways', data=gateway_form(app)).status_code == 302
    row = db.session.scalar(db.select(GatewayAlternativo))
    assert row.ativo and row.produto_id == app.test_ids['produto_id']
    assert 'segredo-privado' not in row.credenciais_criptografadas
    assert json.loads(decrypt(row.credenciais_criptografadas))['api_key'] == 'segredo-privado'
    encrypted = row.credenciais_criptografadas
    html = client.get('/configuracoes/gateways').get_data(as_text=True)
    assert 'segredo-privado' not in html and encrypted not in html
    records = db.session.scalars(db.select(Auditoria).filter_by(entidade='gateways_alternativos')).all()
    assert len(records) == 1 and 'credenciais_criptografadas' not in records[0].novo
    assert client.post('/configuracoes/gateways', data=gateway_form(app, id=str(row.id), api_key='', client_id='')).status_code == 302
    assert json.loads(decrypt(row.credenciais_criptografadas))['api_key'] == 'segredo-privado'
    assert client.post('/configuracoes/gateways', data=gateway_form(app, id=str(row.id),
                       ambiente='producao', api_key='', client_id='')).status_code == 422
    assert row.ambiente == 'sandbox'


@pytest.mark.parametrize('role', ['comercial', 'financeiro', 'suporte', 'auditor'])
def test_gateway_configuration_is_superadmin_only(app, client, role):
    login(client, role)
    assert client.get('/configuracoes/gateways').status_code == 403
    assert client.post('/configuracoes/gateways', data=gateway_form(app)).status_code == 403
    assert not db.session.scalar(db.select(GatewayAlternativo))


@pytest.mark.parametrize('overrides', [
    {'url_api': 'http://example.com'},
    {'url_api': 'https://user:pass@example.com'},
    {'url_api': 'https://example.com/api?token=secret'},
    {'url_callback': 'javascript:alert(1)'},
    {'api_key': '', 'client_id': ''},
    {'certificado': 'inválido', 'chave_privada': ''},
    {'confirmacao': ''},
])
def test_invalid_configuration_is_not_stored(app, client, overrides):
    login(client)
    assert client.post('/configuracoes/gateways', data=gateway_form(app, **overrides)).status_code == 422
    assert not db.session.scalar(db.select(GatewayAlternativo))


def test_named_provider_does_not_select_a_hardcoded_process(app, client):
    login(client)
    assert client.post('/configuracoes/gateways', data=gateway_form(app, nome='Banco Inter')).status_code == 302
    assert client.post('/configuracoes/gateways', data=gateway_form(app, nome='Outro Banco')).status_code == 302
    rows = db.session.scalars(db.select(GatewayAlternativo).order_by(GatewayAlternativo.nome)).all()
    assert [row.nome for row in rows] == ['Banco Inter', 'Outro Banco']
    html = client.get('/configuracoes/gateways').get_data(as_text=True)
    assert 'Adicionar integração de pagamento alternativa' in html
    assert 'Configurar Banco Inter' not in html and 'objeto JSON' not in html
    assert 'não emite cobranças' in html


def test_certificate_pair_must_match_and_secrets_do_not_appear(app, client):
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    login(client)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'teste')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1))
            .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    assert client.post('/configuracoes/gateways', data=gateway_form(app, certificado=pem, chave_privada=private)).status_code == 302
    row = db.session.scalar(db.select(GatewayAlternativo))
    assert json.loads(decrypt(row.credenciais_criptografadas))['chave_privada'] == private.strip()
    assert private not in client.get('/configuracoes/gateways').get_data(as_text=True)