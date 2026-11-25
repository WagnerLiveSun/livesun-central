from flask import render_template, request, redirect, url_for, flash
from datetime import date, datetime, time, timedelta
from app.extensions import db
from app.models import SolicitacaoCadastro, Cliente, Plano, Produto
from app.security import operator_required
from app.services.cadastro_service import review
from app.services.assinatura_service import BusinessError
from app.services.auditoria_service import audit, snapshot
from . import admin
@admin.get('/empresas-clinicas')
@operator_required('superadmin', 'comercial', 'suporte', 'auditor')
def clinicas_companies():
    from app.services import empresas_clinicas_service as service
    cursor = request.args.get('apos', default=0, type=int)
    if cursor is None or not 0 <= cursor <= 2147483647:
        raise BusinessError('Página de clínicas inválida.')
    rows, next_cursor, error = [], None, None
    try:
        rows, next_cursor = service.list_companies(cursor)
    except BusinessError as failure:
        error = str(failure)
    product = db.session.scalar(db.select(Produto).where(Produto.codigo == 'CLINICAS'))
    registrations = {}
    if product and rows:
        identifiers = [str(item['dados']['empresa_id']) for item in rows]
        registrations = {row.empresa_origem: row for row in db.session.scalars(
            db.select(SolicitacaoCadastro).where(SolicitacaoCadastro.produto_id == product.id,
                                                SolicitacaoCadastro.empresa_origem.in_(identifiers)))}
    return render_template('clinicas_companies.html', title='Empresas do Clínicas', rows=rows,
                           next_cursor=next_cursor, error=error, registrations=registrations)


@admin.post('/empresas-clinicas/<int:identifier>/preparar')
@operator_required('superadmin', 'comercial')
def prepare_clinicas_company(identifier):
    from app.services.empresas_clinicas_service import prepare_registration
    try:
        row = prepare_registration(identifier)
        db.session.commit()
    except BusinessError as failure:
        db.session.rollback()
        flash(str(failure), 'warning')
        return redirect(url_for('admin.clinicas_companies'))
    flash('Clínica existente preparada sem exigir confirmação de e-mail. Confira os dados e o plano.', 'success')
    return redirect(url_for('admin.registration_detail', identifier=row.id))




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
    if request.args.get('status') in ('PENDENTE','VINCULO_PENDENTE','VINCULADA','RECUSADA'):
        query=query.where(SolicitacaoCadastro.status==request.args['status'])
    product_id = request.args.get('produto', type=int)
    if product_id:
        query = query.where(SolicitacaoCadastro.produto_id == product_id)
    name = request.args.get('nome', '').strip()[:100]
    if name:
        query = query.where(SolicitacaoCadastro.razao_social.icontains(name, autoescape=True))
    document = ''.join(c for c in request.args.get('documento', '') if c.isdigit())
    if document:
        query = query.where(SolicitacaoCadastro.cnpj_cpf.contains(document, autoescape=True))
    for field, is_end in (('inicio', False), ('fim', True)):
        raw = request.args.get(field, '').strip()
        if raw:
            try:
                day = date.fromisoformat(raw)
                boundary = datetime.combine(day, time.min) + (timedelta(days=1) if is_end else timedelta())
            except (ValueError, OverflowError):
                raise BusinessError('Data do filtro inválida.') from None
            query = query.where(SolicitacaoCadastro.criado_em < boundary if is_end else SolicitacaoCadastro.criado_em >= boundary)
    page=db.paginate(query,per_page=30,max_per_page=30)
    products = db.session.scalars(db.select(Produto).order_by(Produto.nome)).all()
    return render_template('registrations.html',title='Novos clientes',page=page,
                           products=products, clinicas_configurado=any(p.codigo == 'CLINICAS' for p in products))


@admin.post('/cadastros-recebidos/configurar-clinicas')
@operator_required('superadmin', 'comercial')
def configure_clinicas_registration():
    from app.cli import seed_clinicas
    seed_clinicas()
    flash('Produto LiveSun Clínicas disponível. Configure a integração, a credencial e um plano ativo antes de habilitar cadastros.', 'success')
    return redirect(url_for('admin.received_registrations'))


@admin.get('/cadastros-recebidos/<int:identifier>')
@operator_required('superadmin','comercial','suporte','auditor')
def registration_detail(identifier):
    row=db.get_or_404(SolicitacaoCadastro,identifier)
    from app.services.cadastro_service import matching_customers
    customer_matches = matching_customers(row.cnpj_cpf)
    customers = [customer for customer in customer_matches if customer.status == 'ATIVO']
    plans=db.session.scalars(db.select(Plano).filter_by(produto_id=row.produto_id,ativo=True)).all()
    from app.services.empresas_comercial_service import is_legacy, company, fingerprint, conditions, plan_mismatch
    legacy_preview, legacy_hash, legacy_error = None, None, None
    legacy = is_legacy(row)
    if legacy and row.status == 'PENDENTE':
        try:
            legacy_preview = company(int(row.empresa_origem))
            legacy_hash = fingerprint(legacy_preview)
            conditions(legacy_preview)
            plans = [plan for plan in plans if not plan_mismatch(plan, legacy_preview['assinatura'])]
            if not plans:
                old = legacy_preview['assinatura']
                legacy_error = (f'Nenhum plano compatível no Central para {old["plano"]} / {old["periodicidade"]}. '
                    'Use Trazer planos da origem para consultar e importar o catálogo do Comercial, incluindo o preço quando informado na origem. '
                    'Não altere a assinatura legada para contornar esta conferência.')
        except BusinessError as error:
            legacy_error = str(error)
    return render_template('registration.html',title='Cadastro · '+row.razao_social,row=row,customers=customers,plans=plans,
        legacy=legacy, legacy_preview=legacy_preview, legacy_hash=legacy_hash, legacy_error=legacy_error,
        customer_matches=customer_matches)


@admin.post('/cadastros-recebidos/<int:identifier>/habilitar')
@operator_required('superadmin','comercial')
def enable_registration(identifier):
    modalidade = request.form.get('modalidade', '')
    if modalidade and request.form.get('confirmacao') != 'CONFIRMAR':
        raise BusinessError('Confirme a conclusão do cadastro e a modalidade escolhida.')
    if modalidade and modalidade not in ('trial', 'cortesia', 'recorrencia', 'avulsa', 'recusa'):
        raise BusinessError('Modalidade de contratação inválida.')
    if modalidade == 'recusa':
        row = db.session.scalar(db.select(SolicitacaoCadastro).where(
            SolicitacaoCadastro.id == identifier).with_for_update().execution_options(populate_existing=True))
        reason = request.form.get('motivo', '').strip()
        if not row or row.status != 'PENDENTE' or not 3 <= len(reason) <= 500:
            raise BusinessError('Solicitação não pendente ou motivo da recusa inválido.')
        before = snapshot(row)
        row.status, row.motivo = 'RECUSADA', reason
        audit(row, 'AUTOCADASTRO_RECUSADO', before)
        db.session.commit()
        flash('Cadastro recusado. Nenhuma assinatura ou cobrança foi criada.', 'success')
        return redirect(url_for('admin.received_registrations'))
    status = ('TRIAL' if modalidade == 'trial' else 'ATIVA') if modalidade else request.form.get('status','TRIAL')
    row=review(identifier,request.form.get('cliente_id',type=int),request.form.get('plano_id',type=int),
        status,request.form.get('motivo','Habilitação do autocadastro'))
    subscription = row.assinatura
    if modalidade and subscription.status != status:
        raise BusinessError('A assinatura existente possui outra condição; revise-a antes de concluir.')
    if modalidade == 'cortesia':
        from app.services.assinatura_service import grant_courtesy
        if subscription.cortesia or subscription.asaas_habilitado:
            raise BusinessError('Revise a condição de cobrança existente antes de conceder cortesia.')
        grant_courtesy(subscription, 0, True, request.form.get('motivo', ''))
    elif modalidade == 'recorrencia':
        from app.services.asaas_service import configure_subscription, PROPOSTAS_CODES, PROPOSTAS_VALUES
        config = subscription.produto.config_asaas
        if not config or not config.ativo:
            raise BusinessError('Integração de pagamento não configurada para este produto.')
        if subscription.cortesia:
            raise BusinessError('Assinatura em cortesia não pode iniciar cobrança.')
        if subscription.asaas_habilitado:
            raise BusinessError('A assinatura já possui cobrança habilitada; confira antes de continuar.')
        if subscription.produto.codigo in PROPOSTAS_CODES:
            expected = PROPOSTAS_VALUES.get(subscription.plano.periodicidade)
            if not expected or subscription.plano.valor_mensal != expected[0]:
                raise BusinessError('O preço do plano diverge da regra atual de cobrança do produto. Não foi criada recorrência.')
        configure_subscription(subscription, config.ambiente, request.form.get('forma', 'BOLETO'))
    elif modalidade == 'avulsa':
        from app.schemas import ChargeInput
        from app.services.cobranca_service import create_charge
        data = ChargeInput.model_validate({'assinatura_id': subscription.id, 'tipo': 'avulsa',
            'competencia': request.form.get('competencia'), 'valor': request.form.get('valor'),
            'vencimento': request.form.get('vencimento')}).model_dump()
        create_charge(data)
    db.session.commit()
    flash('Cadastro concluído. O vínculo será confirmado pelo produto.' +
          (' A recorrência foi encaminhada para processamento; confira o resultado na assinatura.' if modalidade == 'recorrencia' else
           ' Foi criado apenas um registro local, sem emissão no gateway.' if modalidade == 'avulsa' else ''), 'success')
    return redirect(url_for('admin.subscription',identifier=row.assinatura_id))


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