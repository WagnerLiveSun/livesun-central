from datetime import date, datetime
from decimal import Decimal
from flask import g, has_request_context, request
from flask_login import current_user
from app.extensions import db
from app.models import Auditoria

SECRET_FIELDS = {'senha_hash', 'webhook_secret', 'api_key', 'webhook_token', 'digest'}


def snapshot(obj):
    result = {}
    for column in obj.__table__.columns:
        if column.name in SECRET_FIELDS:
            continue
        value = getattr(obj, column.name)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[column.name] = value
    return result


def actor():
    if has_request_context():
        if getattr(g, 'service_product', None):
            return f'servico:{g.service_product.codigo}', request.remote_addr
        if current_user.is_authenticated:
            return f'operador:{current_user.id}', request.remote_addr
    return 'sistema', None


def audit(obj, action, before=None):
    who, ip = actor()
    db.session.add(Auditoria(entidade=obj.__tablename__, entidade_id=obj.id, acao=action,
                             anterior=before or {}, novo=snapshot(obj), responsavel=who, ip_origem=ip))