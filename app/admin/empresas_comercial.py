from flask import render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Produto, SolicitacaoCadastro
from app.security import operator_required
from app.services import empresas_comercial_service as service
from app.services.assinatura_service import BusinessError
from . import admin


@admin.get('/empresas-comercial/planos')
@operator_required('superadmin', 'comercial', 'suporte', 'auditor')
def comercial_catalog():
    from app.services.catalogo_comercial_service import preview
    catalog, error = None, None
    try:
        catalog = preview()
    except BusinessError as failure:
        error = str(failure)
    return render_template('comercial_catalog.html', title='Planos de origem · Comercial', catalog=catalog, error=error)


@admin.post('/empresas-comercial/planos/importar')
@operator_required('superadmin', 'comercial')
def import_comercial_catalog():
    from app.services.catalogo_comercial_service import import_selected
    try:
        count = import_selected(request.form.get('origem_hash', ''), request.form.getlist('planos'),
            request.form.get('confirmacao') == 'CONFERIDO')
        db.session.commit()
        flash(f'{count} plano(s) criado(s). Planos existentes preservados; nenhuma assinatura ou cobrança criada.', 'success')
    except BusinessError as failure:
        db.session.rollback()
        flash(str(failure), 'warning')
    return redirect(url_for('admin.comercial_catalog'))


@admin.get('/empresas-comercial')
@operator_required('superadmin', 'comercial', 'suporte', 'auditor')
def comercial_companies():
    cursor = request.args.get('apos', default=0, type=int)
    if cursor is None or not 0 <= cursor <= 2147483647:
        raise BusinessError('Página de empresas inválida.')
    rows, next_cursor, error = [], None, None
    try:
        rows, next_cursor = service.list_companies(cursor)
    except BusinessError as failure:
        error = str(failure)
    product = db.session.scalar(db.select(Produto).where(Produto.codigo == 'COMERCIAL'))
    registrations = {}
    if product and rows:
        identifiers = [str(item['dados']['empresa_id']) for item in rows]
        registrations = {row.empresa_origem: row for row in db.session.scalars(
            db.select(SolicitacaoCadastro).where(SolicitacaoCadastro.produto_id == product.id,
                SolicitacaoCadastro.empresa_origem.in_(identifiers)))}
    return render_template('comercial_companies.html', title='Empresas do Comercial',
        rows=rows, next_cursor=next_cursor, error=error, registrations=registrations)


@admin.post('/empresas-comercial/<int:identifier>/preparar')
@operator_required('superadmin', 'comercial')
def prepare_comercial_company(identifier):
    row = service.prepare_registration(identifier)
    db.session.commit()
    flash('Prévia preparada. Confira plano, datas, cliente e bonificação antes de confirmar. Nenhuma cobrança iniciada.', 'success')
    return redirect(url_for('admin.registration_detail', identifier=row.id))


@admin.post('/empresas-comercial/cadastros/<int:identifier>/confirmar')
@operator_required('superadmin', 'comercial')
def confirm_comercial_company(identifier):
    try:
        row = service.confirm(identifier, request.form.get('cliente_id', type=int), request.form.get('plano_id', type=int),
            request.form.get('origem_hash', ''), request.form.get('confirmacao') == 'CONFERIDO', request.form.get('motivo', ''))
    except BusinessError as error:
        db.session.rollback()
        flash(str(error), 'warning')
        return redirect(url_for('admin.registration_detail', identifier=identifier))
    db.session.commit()
    flash('Condições legadas preservadas no Central. Aguarde a confirmação do vínculo pelo Comercial; controle continua separado da ativação.', 'success')
    return redirect(url_for('admin.registration_detail', identifier=row.id))