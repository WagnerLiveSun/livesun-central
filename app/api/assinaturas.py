from flask import request, abort
from app.extensions import db
from app.models import Assinatura
from app.security import service_required, product_scope
from app.schemas import AssinaturaInput, StatusInput, PlanChange, ModuleChange, LimitsInput
from app.services import assinatura_service as service
from app.services.auditoria_service import snapshot
from app.services.entitlement_service import effective
from . import api


def body(schema):
    return schema.model_validate(request.get_json()).model_dump()


@api.get('/assinaturas/<int:identifier>')
@service_required()
def detail(identifier):
    obj = db.get_or_404(Assinatura, identifier)
    product_scope(obj.produto_id)
    return {**snapshot(obj), 'entitlements': effective(obj)}


@api.post('/assinaturas')
@service_required('write')
def create():
    data = body(AssinaturaInput)
    product_scope(data['produto_id'])
    obj = service.create(data)
    db.session.commit()
    return snapshot(obj), 201


@api.patch('/assinaturas/<int:identifier>/<action>')
@service_required('write')
def change(identifier, action):
    obj = service.locked(identifier)
    product_scope(obj.produto_id)
    if action == 'status':
        data = body(StatusInput)
        service.change_status(obj, data['status'], data['motivo'])
    elif action == 'plano':
        service.change_plan(obj, body(PlanChange)['plano_id'])
    elif action == 'modulos':
        data = body(ModuleChange)
        service.change_module(obj, data['modulo_id'], data['liberado'], data['limite'])
    elif action == 'limites':
        service.change_limits(obj, body(LimitsInput)['limites'])
    else:
        abort(404)
    db.session.commit()
    return effective(obj)