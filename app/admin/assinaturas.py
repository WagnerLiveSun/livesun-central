import json
from flask import render_template, request, redirect, url_for, abort, flash
from flask_login import current_user
from app.extensions import db
from app.models import Assinatura, Cliente, Produto, Plano, Modulo, EventoAssinatura, Cobranca, WebhookEntrega, PurgaProduto, OperacaoAsaas
from app.security import operator_required
from app.schemas import AssinaturaInput, StatusInput, PlanChange, ModuleChange, LimitsInput
from app.services import assinatura_service as service
from app.services.entitlement_service import effective
from app.services.auditoria_service import snapshot
from .catalogo import form_values
from . import admin


@admin.get('/assinaturas')
@operator_required()
def subscriptions():
    query = db.select(Assinatura).join(Cliente)
    search = request.args.get('busca','').strip()[:100]
    product = request.args.get('produto',type=int)
    status = request.args.get('status','')
    if search:
        query = query.where(Cliente.razao_social.ilike('%'+search+'%'))
    if product:
        query = query.where(Assinatura.produto_id == product)
    if status in ('ATIVA','TRIAL','SUSPENSA','BLOQUEADA','CANCELADA','EXCLUIDA','EXPIRADA'):
        query = query.where(Assinatura.status == status)
    page = db.paginate(query.order_by(Assinatura.id.desc()), per_page=30)
    counts = dict(db.session.execute(db.select(Assinatura.status,db.func.count(Assinatura.id)).group_by(Assinatura.status)).all())
    return render_template('subscriptions.html', title='Clientes e assinaturas', page=page,
                           counts=counts, products=db.session.scalars(db.select(Produto)).all())


@admin.route('/assinaturas/nova', methods=['GET', 'POST'])
@operator_required('superadmin', 'comercial')
def new_subscription():
    if request.method == 'POST':
        obj = service.create(AssinaturaInput.model_validate(form_values(AssinaturaInput)).model_dump())
        db.session.commit()
        return redirect(url_for('admin.subscription', identifier=obj.id))
    return render_template('subscription_new.html', title='Nova assinatura',
                           clientes=db.session.scalars(db.select(Cliente).filter_by(status='ATIVO')).all(),
                           produtos=db.session.scalars(db.select(Produto).filter_by(ativo=True)).all(),
                           planos=db.session.scalars(db.select(Plano).filter_by(ativo=True)).all())


@admin.get('/assinaturas/<int:identifier>')
@operator_required()
def subscription(identifier):
    obj = db.get_or_404(Assinatura, identifier)
    history = db.session.scalars(db.select(EventoAssinatura).filter_by(assinatura_id=identifier)
                                 .order_by(EventoAssinatura.id.desc()).limit(100)).all()
    deliveries = db.session.scalars(db.select(WebhookEntrega).join(EventoAssinatura,
        WebhookEntrega.evento_id == EventoAssinatura.evento_id).where(EventoAssinatura.assinatura_id == identifier)
        .order_by(WebhookEntrega.id.desc()).limit(100)).all()
    charges = db.session.scalars(db.select(Cobranca).filter_by(assinatura_id=identifier)
                                 .order_by(Cobranca.id.desc()).limit(100)).all()
    return render_template('subscription.html', title=f'Assinatura #{obj.id}', obj=obj,
                           purge=db.session.scalar(db.select(PurgaProduto).filter_by(assinatura_id=identifier)),
                           operations=db.session.scalars(db.select(OperacaoAsaas).filter_by(assinatura_id=identifier).order_by(OperacaoAsaas.id.desc()).limit(20)).all(),
                           entitlements=effective(obj), history=history, deliveries=deliveries, charges=charges)


@admin.post('/assinaturas/<int:identifier>/<action>')
@operator_required('superadmin', 'comercial', 'financeiro', 'suporte')
def subscription_action(identifier, action):
    obj = service.locked(identifier)
    role = current_user.perfil
    if action == 'status':
        data = StatusInput.model_validate(form_values(StatusInput))
        if role == 'financeiro' and data.status != 'SUSPENSA':
            abort(403)
        if role == 'suporte' and data.status not in ('SUSPENSA', 'BLOQUEADA'):
            abort(403)
        service.change_status(obj, data.status, data.motivo)
    else:
        if role not in ('superadmin', 'comercial'):
            abort(403)
        if action == 'plano':
            service.change_plan(obj, PlanChange.model_validate(form_values(PlanChange)).plano_id)
        elif action == 'modulos':
            data = ModuleChange.model_validate(form_values(ModuleChange))
            service.change_module(obj, data.modulo_id, data.liberado, data.limite)
        elif action == 'limites':
            values = json.loads(request.form['limites']) if 'limites' in request.form else {
                key[7:]: int(value) for key, value in request.form.items() if key.startswith('limite_') and value.strip()}
            service.change_limits(obj, LimitsInput.model_validate({'limites': values}).limites)
        else:
            abort(404)
    db.session.commit()
    flash('Assinatura atualizada.', 'success')
    if request.form.get('retorno') == 'painel':
        return redirect(url_for('admin.subscriptions'))
    return redirect(url_for('admin.subscription', identifier=identifier))