from flask import request, abort
from app.extensions import db
from app.models import Assinatura, Produto, Cobranca
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


@api.post('/propostas/contratacao')
@service_required('write')
def create_propostas_contratacao():
    product = db.session.scalar(db.select(Produto)
                                .filter_by(codigo='PROPOSTAS', ativo=True))
    if not product:
        abort(404)
    product_scope(product.id)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        abort(422)
    customer_id = payload.get('cliente_id')
    periodicidade = payload.get('periodicidade')
    if type(customer_id) is not int or type(periodicidade) is not str:
        abort(422)
    from app.services.asaas_service import start_propostas_contratacao
    subscription, created = start_propostas_contratacao(customer_id, periodicidade)
    db.session.commit()
    charge = db.session.scalar(db.select(Cobranca)
                               .filter_by(assinatura_id=subscription.id)
                               .order_by(Cobranca.id.desc()))
    return {
        'created': created,
        'assinatura_id': subscription.id,
        'status': subscription.status,
        'invoice_url': charge.invoice_url if charge else None,
        'periodicidade': subscription.plano.periodicidade,
        'valor': str(subscription.plano.valor_mensal),
    }, 201 if created else 200
