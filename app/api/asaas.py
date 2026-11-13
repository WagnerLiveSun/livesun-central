from flask import request, abort
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.services.asaas_service import receive
from . import api


@api.post('/webhooks/asaas/<environment>')
def asaas_webhook(environment):
    if environment not in ('sandbox', 'producao'):
        abort(404)
    payload = request.get_json()
    if not isinstance(payload, dict):
        abort(422)
    try:
        created = receive(environment, request.headers.get('asaas-access-token', ''), payload)
    except IntegrityError:
        db.session.rollback()
        created = False
    return {'status': 'recebido' if created else 'duplicado'}, 200