from flask import abort, g
from app.extensions import db
from app.models import Assinatura
from app.security import service_required
from app.services.entitlement_service import effective
from . import api


@api.get('/entitlements/<int:cliente_id>/<produto_codigo>')
@service_required()
def entitlements(cliente_id, produto_codigo):
    if g.service_product.codigo != produto_codigo:
        abort(404)
    obj = db.session.scalar(db.select(Assinatura).filter_by(cliente_id=cliente_id,
        produto_id=g.service_product.id).order_by(db.case((Assinatura.slot_vigente == 1, 0), else_=1), Assinatura.id.desc()))
    if not obj:
        abort(404)
    return effective(obj)