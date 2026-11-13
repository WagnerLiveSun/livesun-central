from app.extensions import db
from app.models import Produto, WebhookEntrega
from app.security import service_required, product_scope, encrypt
from app.schemas import WebhookInput
from app.services.auditoria_service import audit, snapshot
from app.services.webhook_service import configure_receiver, resend
from .assinaturas import body
from . import api


@api.post('/produtos/<int:produto_id>/webhooks/registrar')
@service_required('webhooks')
def register(produto_id):
    product_scope(produto_id)
    data = body(WebhookInput)
    product = db.get_or_404(Produto, produto_id)
    configure_receiver(product,data['url_webhook'],data['webhook_secret'])
    db.session.commit()
    return {'status': 'configurado'}


@api.post('/webhooks/<int:entrega_id>/reenviar')
@service_required('webhooks')
def retry(entrega_id):
    entry = db.get_or_404(WebhookEntrega, entrega_id)
    product_scope(entry.produto_id)
    resend(entry)
    db.session.commit()
    return {'status': 'enfileirado'}, 202