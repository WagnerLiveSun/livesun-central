from flask import render_template
from app.extensions import db
from app.models import Auditoria
from app.security import operator_required
from . import admin


@admin.get('/auditoria')
@operator_required()
def audit_log():
    page = db.paginate(db.select(Auditoria).order_by(Auditoria.id.desc()), per_page=30)
    return render_template('audit.html', title='Auditoria', page=page)