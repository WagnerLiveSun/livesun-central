from urllib.parse import urlsplit

from flask import current_app, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import GatewayAlternativo, InstituicaoBancaria, Produto
from app.security import decrypt, encrypt, operator_required
from app.services.assinatura_service import BusinessError
from app.services.auditoria_service import audit, snapshot
from . import admin


def https_url(value, label, required=True):
    value = value.strip()
    if not value and not required:
        return None
    try:
        parsed = urlsplit(value)
        if (len(value) > 500 or any(ord(c) <= 32 for c in value) or parsed.scheme != 'https'
                or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.query or parsed.fragment):
            raise ValueError()
    except ValueError:
        raise BusinessError(f'{label}: use endereço HTTPS válido, sem credenciais, parâmetros ou fragmento.') from None
    return value.rstrip('/')


def credentials(row, replace):
    import json
    fields = ('client_id', 'client_secret', 'api_key', 'certificado', 'chave_privada', 'webhook_token')
    if row:
        try:
            previous = json.loads(decrypt(row.credenciais_criptografadas))
            if not isinstance(previous, dict):
                raise ValueError()
        except Exception:
            raise BusinessError('Não foi possível acessar as credenciais existentes.') from None
    else:
        previous = {}
    values = {key: request.form.get(key, '').strip() for key in fields}
    if any(len(value) > (20000 if key in ('certificado', 'chave_privada') else 4000)
           for key, value in values.items()):
        raise BusinessError('Um campo de credencial excede o tamanho permitido.')
    if replace and not any(values.values()):
        raise BusinessError('Informe as credenciais novamente ao alterar instituição, provedor, produto, ambiente ou URL da API.')
    merged = {key: value for key, value in ({} if replace else previous).items()
              if key in fields and isinstance(value, str) and value}
    merged.update({key: value for key, value in values.items() if value})
    if not merged:
        raise BusinessError('Informe ao menos uma credencial da integração.')
    if bool(merged.get('certificado')) != bool(merged.get('chave_privada')):
        raise BusinessError('Informe o certificado e a chave privada juntos.')
    if bool(values['certificado']) != bool(values['chave_privada']):
        raise BusinessError('Para substituir o certificado, informe também a chave privada correspondente.')
    if merged.get('certificado'):
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key
        try:
            cert = x509.load_pem_x509_certificate(merged['certificado'].encode())
            key = load_pem_private_key(merged['chave_privada'].encode(), password=None)
            if cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) != \
                    key.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo):
                raise ValueError()
        except (ValueError, TypeError):
            raise BusinessError('Certificado e chave privada devem ser PEM válidos do mesmo par.') from None
    return encrypt(json.dumps(merged, ensure_ascii=False, separators=(',', ':')))


@admin.get('/configuracoes/gateways')
@operator_required('superadmin')
def alternative_gateways():
    rows = db.session.scalars(db.select(GatewayAlternativo).order_by(GatewayAlternativo.nome, GatewayAlternativo.id)).all()
    products = db.session.scalars(db.select(Produto).order_by(Produto.nome)).all()
    banks = db.session.scalars(db.select(InstituicaoBancaria).order_by(InstituicaoBancaria.codigo_banco)).all()
    return render_template('alternative_gateways.html', title='Integrações de pagamento', rows=rows,
        products=products, banks=banks,
        asaas_global_override=bool(current_app.config.get('ASAAS_API_KEY', '').strip()
            or current_app.config.get('ASAAS_API_URL', '').strip()
            or current_app.config.get('ASAAS_WEBHOOK_TOKEN', '').strip()),
        production=current_app.config['APP_ENV'] == 'production')


@admin.post('/configuracoes/gateways')
@operator_required('superadmin')
def save_alternative_gateway():
    identifier = request.form.get('id', type=int)
    product = db.get_or_404(Produto, request.form.get('produto_id', type=int))
    row = db.get_or_404(GatewayAlternativo, identifier) if identifier else None
    name = request.form.get('nome', '').strip()
    environment = request.form.get('ambiente', '')
    bank_code = request.form.get('codigo_banco', '').strip() or None
    if bank_code and (len(bank_code) != 3 or not bank_code.isascii() or not bank_code.isdigit()
                      or not db.session.get(InstituicaoBancaria, bank_code)):
        raise BusinessError('Selecione uma instituição bancária cadastrada.')
    if not name or len(name) > 100 or environment not in ('sandbox', 'producao'):
        raise BusinessError('Informe nome e ambiente válidos.')
    if request.form.get('confirmacao') != 'CONFIRMAR':
        raise BusinessError('Confirme o cadastro ou alteração do provedor.')
    api_url = https_url(request.form.get('url_api', ''), 'URL da API')
    callback = https_url(request.form.get('url_callback', ''), 'URL de callback', required=False)
    changed = bool(row and (row.produto_id != product.id or row.ambiente != environment
                            or row.url_api != api_url or row.nome != name or row.codigo_banco != bank_code))
    secret = credentials(row, changed)
    before = snapshot(row) if row else None
    if row is None:
        row = GatewayAlternativo(produto_id=product.id)
        db.session.add(row)
    row.produto_id, row.nome, row.ambiente = product.id, name, environment
    row.codigo_banco = bank_code
    row.url_api, row.url_callback = api_url, callback
    row.ativo = request.form.get('ativo') == 'on'
    row.credenciais_criptografadas = secret
    try:
        db.session.flush()
    except IntegrityError:
        raise BusinessError('Já existe configuração com este nome, ambiente e produto.') from None
    audit(row, 'GATEWAY_ALTERNATIVO_CONFIGURADO', before)
    db.session.commit()
    flash('Parâmetros salvos. Esta configuração ainda não emite cobranças: requer integração compatível.', 'success')
    return redirect(url_for('admin.alternative_gateways'))