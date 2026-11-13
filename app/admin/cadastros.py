from flask import render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import SolicitacaoCadastro, Cliente, Plano
from app.security import operator_required
from app.services.cadastro_service import review
from app.services.assinatura_service import BusinessError
from app.services.auditoria_service import audit, snapshot
from . import admin


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