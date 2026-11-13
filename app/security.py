import json
import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4
import jwt
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from flask import abort, current_app, g, request
from flask_login import current_user
from app.extensions import db

passwords = PasswordHasher()


def encrypt(value):
    return Fernet(current_app.config['ENCRYPTION_KEY'].encode()).encrypt(value.encode()).decode()


def decrypt(value):
    return Fernet(current_app.config['ENCRYPTION_KEY'].encode()).decrypt(value.encode()).decode()


def service_token(product, scopes=('read',), hours=24):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': str(product.id), 'kind': 'service', 'ver': product.token_version,
                       'scopes': list(scopes), 'iss': 'livesun-central', 'aud': 'livesun-products',
                       'iat': now, 'exp': now + timedelta(hours=hours), 'jti': uuid4().hex},
                      current_app.config['JWT_SECRET'], algorithm='HS256')


def service_required(scope='read'):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from app.models import Produto
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '):
                abort(401)
            try:
                if header[7:].startswith('lsc_'):
                    from app.models import CredencialServico
                    credential = db.session.scalar(db.select(CredencialServico).filter_by(
                        digest=hashlib.sha256(header[7:].encode()).hexdigest(), ativo=True))
                    product = db.session.get(Produto, credential.produto_id) if credential else None
                    if not product or not product.ativo:
                        abort(401)
                    if scope not in credential.scopes:
                        abort(403)
                    g.service_product = product
                    return view(*args, **kwargs)
                claims = jwt.decode(header[7:], current_app.config['JWT_SECRET'], algorithms=['HS256'],
                                    issuer='livesun-central', audience='livesun-products',
                                    options={'require': ['exp', 'iat', 'sub', 'jti']})
                product = db.session.get(Produto, int(claims['sub']))
                if (claims.get('kind') != 'service' or not product or not product.ativo
                        or claims.get('ver') != product.token_version):
                    abort(401)
                if scope not in claims.get('scopes', []):
                    abort(403)
                g.service_product = product
            except (jwt.PyJWTError, ValueError, KeyError):
                abort(401)
            return view(*args, **kwargs)
        return wrapped
    return decorate


def issue_product_credential(product):
    from app.models import CredencialServico
    raw = 'lsc_' + secrets.token_urlsafe(48)
    credential = CredencialServico(produto_id=product.id, nome='Integração do produto',
        digest=hashlib.sha256(raw.encode()).hexdigest(), scopes=['read'], ativo=True)
    db.session.add(credential)
    db.session.flush()
    return credential, raw


def product_scope(identifier):
    if g.service_product.id != identifier:
        abort(404)


def operator_required(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                from flask import redirect, url_for
                return redirect(url_for('admin.login_view'))
            if not current_user.ativo or (roles and current_user.perfil not in roles):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorate


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        # Deliberadamente não serializa mensagem livre, args ou exceções de dependências.
        return json.dumps({'level': record.levelname, 'logger': record.name,
                           'event': getattr(record, 'safe_event', 'application_log')})