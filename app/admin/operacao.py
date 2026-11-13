import secrets
from datetime import date
from flask import render_template, request, redirect, url_for, abort, flash
from app.extensions import db
from app.models import Produto, ConfigAsaas, CredencialServico, EventoAsaas, OperacaoAsaas, Assinatura, PurgaProduto
from app.security import operator_required, issue_product_credential, encrypt
from app.services.auditoria_service import audit, snapshot
from app.services.assinatura_service import locked, grant_trial, grant_courtesy, BusinessError
from app.services.asaas_service import configure_subscription, enqueue, AsaasClient
from app.services.purga_service import anticipate
from . import admin


@admin.get('/integracoes')
@operator_required('superadmin')
def integrations():
    return render_template('integrations.html', title='Integrações e credenciais',
        products=db.session.scalars(db.select(Produto)).all(),
        credentials=db.session.scalars(db.select(CredencialServico).order_by(CredencialServico.id.desc())).all(),
        configs=db.session.scalars(db.select(ConfigAsaas)).all(),
        operations=db.session.scalars(db.select(OperacaoAsaas).order_by(OperacaoAsaas.id.desc()).limit(50)).all(),
        failures=db.session.scalars(db.select(EventoAsaas).filter_by(status='FALHA').limit(50)).all())


@admin.get('/produtos/<int:identifier>/cobranca')
@operator_required('superadmin','financeiro','comercial')
def product_billing(identifier):
    product = db.get_or_404(Produto, identifier)
    return render_template('product_billing.html', title='Cobrança · '+product.nome, product=product,
        config=product.config_asaas, subscriptions=db.session.scalars(db.select(Assinatura).filter_by(produto_id=identifier)).all())


@admin.post('/integracoes/produtos/<int:identifier>/gerar')
@operator_required('superadmin')
def generate_credentials(identifier):
    product = db.get_or_404(Produto, identifier)
    if request.form.get('confirmacao') != 'GERAR':
        raise BusinessError('Confirme a geração de credencial.')
    credential, token = issue_product_credential(product)
    # HMAC só é criado se ausente; não gira silenciosamente o segredo do produto.
    secret = None
    if not product.webhook_secret:
        secret = secrets.token_urlsafe(48)
        product.webhook_secret = encrypt(secret)
    audit(credential, 'CREDENCIAL_PRODUTO_GERADA')
    db.session.commit()
    return render_template('credential_once.html', title='Credencial gerada', token=token, secret=secret)


@admin.post('/integracoes/credenciais/<int:identifier>/revogar')
@operator_required('superadmin')
def revoke_credential(identifier):
    credential = db.get_or_404(CredencialServico, identifier)
    credential.ativo = False
    audit(credential, 'CREDENCIAL_REVOGADA')
    db.session.commit()
    return redirect(url_for('admin.integrations'))


@admin.post('/integracoes/produtos/<int:identifier>/hmac')
@operator_required('superadmin')
def rotate_hmac(identifier):
    if request.form.get('confirmacao') != 'RENOVAR':
        raise BusinessError('Confirme RENOVAR e atualize o produto após a rotação.')
    product = db.get_or_404(Produto, identifier)
    secret = secrets.token_urlsafe(48)
    product.webhook_secret = encrypt(secret)
    audit(product, 'HMAC_ROTACIONADO')
    db.session.commit()
    return render_template('credential_once.html', title='Segredo renovado', token=None, secret=secret)


@admin.post('/integracoes/asaas')
@operator_required('superadmin')
def asaas_config():
    product = db.get_or_404(Produto, request.form.get('produto_id', type=int))
    environment = request.form.get('ambiente')
    if environment not in ('sandbox', 'producao'):
        raise BusinessError('Ambiente inválido.')
    if environment == 'producao' and request.form.get('confirmacao') != 'PRODUCAO':
        raise BusinessError('Confirme PRODUCAO para configurar a conta real.')
    key = request.form.get('api_key', '').strip()
    token = request.form.get('webhook_token', '').strip()
    config = db.session.scalar(db.select(ConfigAsaas).filter_by(ambiente=environment))
    if (not config and (not key or len(token)<32)) or len(key)>1000 or (token and not 32<=len(token)<=200):
        raise BusinessError('Informe chave e token válidos; campos vazios preservam os existentes.')
    if config is None:
        config = ConfigAsaas(ambiente=environment)
        db.session.add(config)
    if key:
        config.api_key = encrypt(key)
    if token:
        config.webhook_token = encrypt(token)
    config.ativo = 'ativo' in request.form
    db.session.flush()
    if product.config_asaas_id != config.id:
        existing = db.session.scalar(db.select(Assinatura.id).where(Assinatura.produto_id == product.id,
            Assinatura.asaas_subscription_id.is_not(None), Assinatura.asaas_ambiente != environment))
        if existing:
            raise BusinessError('Produto possui recorrência em outro ambiente. Preserve a configuração existente.')
    product.config_asaas_id = config.id
    audit(config, 'ASAAS_ASSINATURAS_CONFIGURADO')
    audit(product, 'COBRANCA_PRODUTO_CONFIGURADA')
    db.session.commit()
    return redirect(url_for('admin.product_billing', identifier=product.id))


@admin.post('/integracoes/asaas/<int:identifier>/testar')
@operator_required('superadmin')
def test_asaas(identifier):
    config = db.get_or_404(ConfigAsaas, identifier)
    AsaasClient(config).request('GET', '/customers', params={'limit': 1})
    audit(config, 'ASAAS_CONEXAO_VALIDADA')
    db.session.commit()
    from flask import flash
    flash('Conexão com o Asaas validada. Nenhum cliente ou cobrança foi criado.', 'success')
    product_id = request.form.get('produto_id',type=int)
    return redirect(url_for('admin.product_billing',identifier=product_id)) if product_id else redirect(url_for('admin.integrations'))


@admin.post('/integracoes/asaas/operacoes/<int:identifier>/revisar')
@operator_required('superadmin')
def retry_asaas(identifier):
    operation = db.get_or_404(OperacaoAsaas, identifier)
    if operation.status not in ('REVISAR', 'EXECUTANDO') or request.form.get('confirmacao') != 'CONFERIDO':
        raise BusinessError('Confira primeiro o gateway e confirme CONFERIDO.')
    operation.status, operation.erro = 'PENDENTE', None
    audit(operation, 'ASAAS_REPROCESSAMENTO_AUTORIZADO')
    db.session.commit()
    return redirect(url_for('admin.subscription',identifier=operation.assinatura_id))


@admin.post('/integracoes/asaas/eventos/<int:identifier>/repetir')
@operator_required('superadmin', 'financeiro')
def retry_event(identifier):
    event = db.get_or_404(EventoAsaas, identifier)
    if event.status != 'FALHA':
        raise BusinessError('Evento não está com falha.')
    event.status, event.erro = 'PENDENTE', None
    audit(event, 'ASAAS_EVENTO_REPROCESSADO')
    db.session.commit()
    return redirect(url_for('admin.integrations'))


@admin.post('/assinaturas/<int:identifier>/comercial/<action>')
@operator_required('superadmin', 'comercial', 'financeiro')
def commercial_action(identifier, action):
    from flask_login import current_user
    obj = locked(identifier)
    if obj.status == 'EXCLUIDA' and action != 'purga':
        raise BusinessError('Assinatura excluída: somente retenção/purga estão disponíveis.')
    reason = request.form.get('motivo', '').strip()
    if action in ('trial', 'cortesia') and current_user.perfil == 'financeiro':
        abort(403)
    if action == 'trial':
        grant_trial(obj, int(request.form.get('dias', '7')), reason)
    elif action == 'cortesia':
        grant_courtesy(obj, int(request.form.get('dias', '0')), request.form.get('liberado') == 'true', reason)
    elif action == 'asaas':
        config = obj.produto.config_asaas
        if not config or not config.ativo:
            raise BusinessError('Configure a cobrança no cadastro do produto primeiro.')
        if config.ambiente == 'producao' and request.form.get('confirmacao') != 'COBRAR':
            raise BusinessError('Confirme COBRAR para habilitar recorrência em produção.')
        configure_subscription(obj, config.ambiente, request.form.get('forma','BOLETO'))
    elif action == 'consultar':
        if not obj.asaas_subscription_id:
            raise BusinessError('Assinatura sem vínculo Asaas.')
        enqueue(obj, 'CONSULTAR')
    elif action == 'purga':
        if current_user.perfil != 'superadmin':
            abort(403)
        if request.form.get('confirmacao') != 'PURGAR':
            raise BusinessError('Digite PURGAR para confirmar exclusão definitiva neste produto.')
        anticipate(obj, reason)
    else:
        abort(404)
    db.session.commit()
    if request.form.get('retorno') == 'painel':
        return redirect(url_for('admin.subscriptions'))
    return redirect(url_for('admin.subscription', identifier=identifier))