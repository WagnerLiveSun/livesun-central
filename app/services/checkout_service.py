"""Passagem curta assinada com o segredo HMAC já compartilhado com o Propostas."""
import base64
import hashlib
import hmac
import json
import time
import binascii
from flask import abort
from app.extensions import db
from app.models import Produto, Cliente
from app.security import decrypt


def resolve(token):
    try:
        encoded, signature = token.split('.')
        if len(token) > 2048:
            raise ValueError()
        product = db.session.scalar(db.select(Produto).filter_by(codigo='PROPOSTAS', ativo=True))
        if not product or not product.webhook_secret:
            abort(503)
        expected = hmac.new(decrypt(product.webhook_secret).encode(),
            ('checkout-propostas:' + encoded).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            abort(401)
        data = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if (data.get('produto') != 'PROPOSTAS' or type(data.get('cliente_id')) is not int
                or type(data.get('iat')) is not int or not 0 <= time.time() - data['iat'] <= 300):
            abort(401)
        customer = db.session.get(Cliente, data['cliente_id'])
        if not customer or customer.status != 'ATIVO':
            abort(404)
        return customer.id
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
        abort(401)