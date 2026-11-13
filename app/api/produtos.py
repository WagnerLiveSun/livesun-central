from flask import g
from app.security import service_required
from app.services.auditoria_service import snapshot
from . import api


@api.get('/produtos')
@service_required()
def products():
    product = g.service_product
    data = snapshot(product)
    data['planos'] = [snapshot(p) for p in product.planos if p.ativo]
    data['modulos'] = [snapshot(m) for m in product.modulos if m.ativo] if product.permite_modulos else []
    return {'produtos': [data]}