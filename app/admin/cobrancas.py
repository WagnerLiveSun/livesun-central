from flask import render_template, request, redirect, url_for
from app.extensions import db
from app.models import Cobranca, Assinatura, Cliente
from app.schemas import ChargeInput
from app.security import operator_required
from app.services.cobranca_service import create_charge, pay
from datetime import date
from .catalogo import form_values
from . import admin


@admin.get('/cobrancas')
@operator_required()
def charges():
    page = db.paginate(db.select(Cobranca).order_by(Cobranca.id.desc()), per_page=30)
    subscriptions = db.session.scalars(db.select(Assinatura).order_by(Assinatura.id.desc())).all()
    contexts = {s.id:s for s in subscriptions}
    eligible = [s for s in subscriptions if s.status not in ('EXCLUIDA','CANCELADA','EXPIRADA')
                and not (s.cortesia and (not s.cortesia_ate or s.cortesia_ate >= date.today()))]
    return render_template('charges.html', title='Cobranças', page=page, subscriptions=eligible, contexts=contexts)


@admin.post('/cobrancas')
@operator_required('superadmin', 'financeiro')
def new_charge():
    create_charge(ChargeInput.model_validate(form_values(ChargeInput)).model_dump())
    db.session.commit()
    return redirect(url_for('admin.charges'))


@admin.post('/cobrancas/<int:identifier>/pagar')
@operator_required('superadmin', 'financeiro')
def pay_charge(identifier):
    obj = db.session.scalar(db.select(Cobranca).where(Cobranca.id == identifier).with_for_update())
    if obj is None:
        from flask import abort
        abort(404)
    pay(obj)
    db.session.commit()
    return redirect(url_for('admin.charges'))