from flask import render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import SolicitacaoCadastro, Cliente, Plano, Produto
from app.security import operator_required
from app.services.cadastro_service import review
from app.services.assinatura_service import BusinessError
from app.services.auditoria_service import audit, snapshot
from . import admin


@admin.get('/empresas-propostas')
@operator_required('superadmin','comercial','suporte','auditor')
def propostas_companies():
    from app.services.empresas_propostas_service import list_companies
    cursor = request.args.get('apos', default=0, type=int)
    if cursor is None or not 0 <= cursor <= 2147483647:
        raise BusinessError('Página de empresas inválida.')
    rows, next_cursor, error = [], None, None
    try:
        rows, next_cursor = list_companies(cursor)
    except BusinessError as failure:
        error = str(failure)
    product = db.session.scalar(db.select(Produto).where(Produto.codigo == 'PROPOSTAS'))
    registrations = {}
    if product and rows:
        identifiers = [str(item['dados']['empresa_id']) for item in rows]
        registrations = {row.empresa_origem: row for row in db.session.scalars(
            db.select(SolicitacaoCadastro).where(SolicitacaoCadastro.produto_id == product.id,
                SolicitacaoCadastro.empresa_origem.in_(identifiers)))}
    return render_template('propostas_companies.html', title='Empresas do Propostas',
        rows=rows, next_cursor=next_cursor, error=error, registrations=registrations)


@admin.post('/empresas-propostas/<int:identifier>/cadastrar')
@operator_required('superadmin','comercial')
def prepare_propostas_company(identifier):
    from app.services.empresas_propostas_service import prepare_registration
    row = prepare_registration(identifier)
    db.session.commit()
    flash('Dados carregados. Confirme cliente, plano e acesso inicial para cadastrar e vincular. Nenhuma cobrança foi iniciada.', 'success')
    return redirect(url_for('admin.registration_detail', identifier=row.id))


@admin.get('/cadastros-recebidos')
@operator_required('superadmin','comercial','suporte','auditor')
def received_registrations():
    query=db.select(SolicitacaoCadastro).order_by(SolicitacaoCadastro.id.desc())
    if request.args.get('status') in ('PENDENTE','VINCULO_PENDENTE','VINCULADA'):
        query=query.where(SolicitacaoCadastro.status==request.args['status'])
    page=db.paginate(query,per_page=30,max_per_page=30)
    return render_template('registrations.html',title='Cadastros recebidos',page=page)


@admin.get('/cadastros-recebidos/<int:identifier>')
@operator_required('superadmin','comercial','suporte','auditor')
def registration_detail(identifier):
    row=db.get_or_404(SolicitacaoCadastro,identifier)
    customers=db.session.scalars(db.select(Cliente).filter_by(status='ATIVO').order_by(Cliente.razao_social)).all()
    plans=db.session.scalars(db.select(Plano).filter_by(produto_id=row.produto_id,ativo=True)).all()
    return render_template('registration.html',title='Cadastro · '+row.razao_social,row=row,customers=customers,plans=plans)


@admin.post('/cadastros-recebidos/<int:identifier>/habilitar')
@operator_required('superadmin','comercial')
def enable_registration(identifier):
    row=review(identifier,request.form.get('cliente_id',type=int),request.form.get('plano_id',type=int),
        request.form.get('status','TRIAL'),request.form.get('motivo','Habilitação do autocadastro'))
    db.session.commit()
    flash('Cadastro habilitado. O vínculo será confirmado pelo produto; nenhuma cobrança foi iniciada.','success')
    return redirect(url_for('admin.registration_detail',identifier=row.id))


@admin.post('/cadastros-recebidos/<int:identifier>/reenviar')
@operator_required('superadmin','comercial')
def retry_registration_link(identifier):
    from app.models.base import now
    row=db.get_or_404(SolicitacaoCadastro,identifier)
    if row.status!='VINCULO_PENDENTE':
        raise BusinessError('Vínculo não está pendente.')
    before=snapshot(row)
    row.proxima_tentativa=now()
    audit(row,'AUTOCADASTRO_REENVIO_VINCULO',before)
    db.session.commit()
    return redirect(url_for('admin.registration_detail',identifier=identifier))