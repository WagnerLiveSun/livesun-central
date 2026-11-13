from flask import render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import WebhookEntrega, Produto, WebhookTentativa
from app.schemas import WebhookInput
from app.security import operator_required, encrypt
from app.services.webhook_service import resend, configure_receiver, probe_receiver, resend_product_failures
from app.security import decrypt
from app.services.auditoria_service import audit, snapshot
from .catalogo import form_values
from . import admin


@admin.get('/webhooks')
@operator_required()
def deliveries():
    page = db.paginate(db.select(WebhookEntrega).order_by(WebhookEntrega.id.desc()), per_page=30)
    return render_template('webhooks.html', title='Webhooks', page=page,
                           produtos=db.session.scalars(db.select(Produto)).all())


@admin.post('/webhooks/<int:identifier>/reenviar')
@operator_required('superadmin', 'suporte')
def resend_delivery(identifier):
    entry = db.get_or_404(WebhookEntrega, identifier)
    resend(entry)
    db.session.commit()
    return redirect(url_for('admin.deliveries'))


@admin.post('/webhooks/produtos/<int:identifier>/reenviar-falhas')
@operator_required('superadmin','suporte')
def resend_product_deliveries(identifier):
    product=db.get_or_404(Produto,identifier)
    if request.form.get('confirmacao')!='REENVIAR':
        from app.services.assinatura_service import BusinessError
        raise BusinessError('Confirme o reenvio das falhas deste produto.')
    count=resend_product_failures(product.id)
    db.session.commit()
    flash(f'{count} entrega(s) de {product.nome} reenfileirada(s) com o destino atual.','success')
    return redirect(url_for('admin.deliveries'))


@admin.post('/webhooks/configurar')
@operator_required('superadmin')
def configure_webhook():
    product = db.get_or_404(Produto, int(request.form.get('produto_id', '0')))
    data = WebhookInput.model_validate({k: request.form.get(k) for k in ('url_webhook', 'webhook_secret')})
    count=configure_receiver(product,data.url_webhook,data.webhook_secret)
    db.session.commit()
    flash(f'Receptor validado para {product.nome}. {count} entrega(s) pendente(s) recuperada(s) automaticamente.','success')
    return redirect(url_for('admin.deliveries'))


@admin.post('/webhooks/produtos/<int:identifier>/testar')
@operator_required('superadmin','suporte')
def test_receiver(identifier):
    product=db.get_or_404(Produto,identifier)
    if not product.webhook_secret or not product.url_webhook:
        from app.services.assinatura_service import BusinessError
        raise BusinessError('Configure o receptor do produto primeiro.')
    probe_receiver(product.codigo,product.url_webhook,decrypt(product.webhook_secret))
    flash('Receptor, identidade do produto e assinatura confirmados. Nenhum estado comercial foi alterado.','success')
    return redirect(url_for('admin.deliveries'))