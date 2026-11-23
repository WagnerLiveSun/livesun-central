from flask import current_app, render_template, request, redirect, url_for
from app.extensions import db
from app.models import Cobranca, Assinatura, OperacaoAsaas
from app.schemas import ChargeInput
from app.security import operator_required
from app.services.cobranca_service import create_charge, pay
from app.services.assinatura_service import BusinessError
from .catalogo import form_values
from . import admin


@admin.get('/cobrancas')
@operator_required()
def charges():
    page = db.paginate(db.select(Cobranca).order_by(Cobranca.id.desc()), per_page=30)
    subscriptions = db.session.scalars(db.select(Assinatura).order_by(Assinatura.id.desc())).all()
    contexts = {s.id:s for s in subscriptions}
    eligible = [s for s in subscriptions if s.status == 'ATIVA' and not s.cortesia and not s.asaas_habilitado]
    latest_ids = (db.select(db.func.max(OperacaoAsaas.id).label('id'))
        .where(OperacaoAsaas.tipo == 'SINCRONIZAR')
        .group_by(OperacaoAsaas.assinatura_id).subquery())
    operations = db.session.scalars(db.select(OperacaoAsaas).join(latest_ids, OperacaoAsaas.id == latest_ids.c.id)).all()
    latest = {operation.assinatura_id: operation for operation in operations}
    return render_template('charges.html', title='Cobranças', page=page, subscriptions=eligible,
        all_subscriptions=subscriptions, contexts=contexts, operations=latest,
        production=current_app.config['APP_ENV'] == 'production')


@admin.post('/cobrancas')
@operator_required('superadmin', 'financeiro')
def new_charge():
    if request.form.get('confirmacao') != 'CONFIRMAR':
        raise BusinessError('Confirme a criação do registro local de cobrança.')
    create_charge(ChargeInput.model_validate(form_values(ChargeInput)).model_dump())
    db.session.commit()
    return redirect(url_for('admin.charges'))


@admin.post('/cobrancas/<int:identifier>/pagar')
@operator_required('superadmin', 'financeiro')
def pay_charge(identifier):
    if request.form.get('confirmacao') != 'CONFIRMAR':
        raise BusinessError('Confirme o registro manual de pagamento.')
    obj = db.session.scalar(db.select(Cobranca).where(Cobranca.id == identifier).with_for_update())
    if obj is None:
        from flask import abort
        abort(404)
    pay(obj)
    db.session.commit()
    return redirect(url_for('admin.charges'))