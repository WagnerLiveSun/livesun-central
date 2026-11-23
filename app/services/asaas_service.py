"""Asaas exclusivo de assinaturas LiveSun; não recebe cobranças bancárias de tenants."""
import hmac
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote, urlsplit
import requests
from flask import current_app
from app.extensions import db
from app.models import Assinatura, Cobranca, ConfigAsaas, EventoAsaas, OperacaoAsaas
from app.models.base import now
from app.security import decrypt
from .assinatura_service import BusinessError, locked, record
from .auditoria_service import audit, snapshot

BASES = {'sandbox': 'https://api-sandbox.asaas.com/v3', 'producao': 'https://api.asaas.com/v3'}
PAID = {'RECEIVED', 'CONFIRMED', 'RECEIVED_IN_CASH', 'DUNNING_RECEIVED'}
PROPOSTAS_CODES = {'PROPOSTAS', 'LIVE_SUN_PROPOSTAS'}
PROPOSTAS_VALUES = {'mensal': (Decimal('80.00'), 'MONTHLY'), 'anual': (Decimal('600.00'), 'YEARLY')}


class AsaasRequestError(BusinessError):
    """Erro sanitizado; somente falhas de leitura são retomadas automaticamente."""
    def __init__(self, category, safe_to_retry=False):
        super().__init__('Não foi possível concluir a comunicação com o Asaas.')
        self.category = category
        self.safe_to_retry = safe_to_retry


def safe_invoice_url(value, environment):
    try:
        parsed = urlsplit(value or '')
        port = parsed.port
    except (ValueError, TypeError):
        return None
    hosts = {'sandbox': {'sandbox.asaas.com', 'www.asaas.com', 'asaas.com'},
             'producao': {'www.asaas.com', 'asaas.com'}}
    if (parsed.scheme == 'https' and parsed.hostname in hosts.get(environment, set())
            and not parsed.username and not parsed.password and port in (None, 443)):
        return value
    return None


def asaas_value(value):
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    if decimal_value == decimal_value.to_integral_value():
        return int(decimal_value)
    return format(decimal_value, '.2f')


class AsaasClient:
    def __init__(self, config):
        environment = config.ambiente
        configured_url = current_app.config.get('ASAAS_API_URL', '').rstrip('/')
        if environment not in BASES:
            raise BusinessError('Ambiente Asaas inválido.')
        self.base = BASES[environment]
        configured_key = current_app.config.get('ASAAS_API_KEY', '').strip()
        # Chaves globais só podem ser usadas quando a URL fixa comprova o ambiente.
        # Caso contrário, use a credencial isolada já configurada para esta conta.
        self.key = (configured_key if configured_key and configured_url == self.base
                    else decrypt(config.api_key))

    def request(self, method, path, **kwargs):
        with requests.Session() as http:
            http.trust_env = False
            try:
                response = http.request(method, self.base + path, headers={
                    'access_token': self.key, 'User-Agent': 'LiveSun-Central/1.0',
                    'Content-Type': 'application/json'}, timeout=(5, 20), allow_redirects=False, **kwargs)
            except requests.RequestException:
                raise AsaasRequestError('ASAAS_CONEXAO_LEITURA' if method == 'GET' else 'ASAAS_RESPOSTA_INDEFINIDA',
                                        safe_to_retry=method == 'GET') from None
            if not 200 <= response.status_code < 300:
                if response.status_code in (401, 403):
                    category = 'ASAAS_AUTENTICACAO'
                elif response.status_code == 429 or response.status_code >= 500:
                    category = 'ASAAS_INDISPONIVEL' if method == 'GET' else 'ASAAS_RESPOSTA_INDEFINIDA'
                else:
                    category = 'ASAAS_REQUISICAO_RECUSADA'
                raise AsaasRequestError(category, safe_to_retry=method == 'GET'
                    and (response.status_code == 429 or response.status_code >= 500))
            return response.json() if response.content else {}

    def pages(self, path, params=None):
        offset = 0
        while True:
            payload = self.request('GET', path, params={**(params or {}), 'limit': 100, 'offset': offset})
            yield from payload.get('data', [])
            if not payload.get('hasMore'):
                break
            offset += 100


def config_for(environment, product=None):
    config = (product.config_asaas if product is not None else
              db.session.scalar(db.select(ConfigAsaas).filter_by(ambiente=environment, ativo=True)))
    if config and (config.ambiente != environment or not config.ativo):
        config = None
    if not config:
        raise BusinessError('Configure e habilite o Asaas de assinaturas no Central.')
    return config


def webhook_token(config):
    configured = current_app.config.get('ASAAS_WEBHOOK_TOKEN', '').strip()
    configured_url = current_app.config.get('ASAAS_API_URL', '').rstrip('/')
    # Sem URL global explícita, o token cadastrado na conta é a fonte segura.
    # Nunca compartilhar um token global entre sandbox e produção por inferência.
    if configured and configured_url == BASES.get(config.ambiente):
        return configured
    return decrypt(config.webhook_token)


def enqueue(subscription, kind):
    existing = db.session.scalar(db.select(OperacaoAsaas).where(
        OperacaoAsaas.assinatura_id == subscription.id, OperacaoAsaas.status.in_(['PENDENTE', 'REVISAR', 'EXECUTANDO']),
        OperacaoAsaas.tipo == kind))
    if not existing:
        db.session.add(OperacaoAsaas(assinatura_id=subscription.id, tipo=kind, proxima_tentativa=now()))


def reference(subscription):
    return f'central:{subscription.produto.codigo}:{subscription.id}'


def configure_subscription(subscription, environment, form, existing_id=None):
    config_for(environment, subscription.produto)
    if subscription.cortesia and (not subscription.cortesia_ate or subscription.cortesia_ate >= date.today()):
        raise BusinessError('Assinatura bonificada: encerre a bonificação explicitamente antes de habilitar cobrança.')
    if subscription.status not in ('ATIVA', 'TRIAL'):
        raise BusinessError('Ative a assinatura antes de habilitar cobrança.')
    if subscription.produto.codigo in PROPOSTAS_CODES:
        form = 'BOLETO'
    elif form not in ('BOLETO', 'PIX'):
        raise BusinessError('Use boleto ou Pix; cartão exige fluxo de tokenização separado.')
    if subscription.asaas_subscription_id and existing_id and existing_id != subscription.asaas_subscription_id:
        raise BusinessError('Assinatura já vinculada a outra recorrência.')
    if (subscription.asaas_subscription_id or subscription.asaas_customer_id) and subscription.asaas_ambiente != environment:
        raise BusinessError('Não é permitido mover vínculo existente entre sandbox e produção.')
    if subscription.plano.valor_mensal <= 0 and not subscription.cortesia:
        raise BusinessError('Configure preço contratado maior que zero antes de habilitar cobrança.')
    before = snapshot(subscription)
    subscription.asaas_ambiente, subscription.asaas_forma = environment, form
    subscription.asaas_habilitado = True
    if existing_id:
        client = AsaasClient(config_for(environment, subscription.produto))
        remote = client.request('GET', '/subscriptions/' + quote(existing_id, safe=''))
        # Importação de vínculo existente deve ser consciente e conferida pelo operador.
        if not remote.get('id') or not remote.get('customer'):
            raise BusinessError('Assinatura Asaas inválida.')
        subscription.asaas_subscription_id = remote['id']
        subscription.asaas_customer_id = remote['customer']
        enqueue(subscription, 'CONSULTAR')
    else:
        enqueue(subscription, 'SINCRONIZAR')
    audit(subscription, 'ASAAS_VINCULO_CONFIGURADO', before)


def sync_subscription(subscription, client):
    terminal = subscription.status in ('CANCELADA', 'EXCLUIDA', 'EXPIRADA')
    courtesy = subscription.cortesia and (not subscription.cortesia_ate or subscription.cortesia_ate >= date.today())
    inactive = terminal or courtesy or subscription.status in ('SUSPENSA', 'BLOQUEADA')
    ref = reference(subscription)
    if not subscription.asaas_subscription_id:
        if inactive:
            return
        remote = list(client.pages('/subscriptions', {'externalReference': ref}))
        if len(remote) > 1:
            raise BusinessError('Mais de uma assinatura Asaas corresponde à referência; revise manualmente.')
        if remote:
            subscription.asaas_subscription_id = remote[0]['id']
            subscription.asaas_customer_id = remote[0]['customer']
            db.session.commit()
        else:
            customer_ref = 'central-cliente:' + str(subscription.cliente_id)
            customers = list(client.pages('/customers', {'externalReference': customer_ref}))
            if len(customers) > 1:
                raise BusinessError('Clientes Asaas duplicados; revise o vínculo.')
            if customers:
                subscription.asaas_customer_id = customers[0]['id']
                if subscription.asaas_ambiente == 'sandbox':
                    subscription.cliente.asaas_sandbox_customer_id = customers[0]['id']
                elif subscription.asaas_ambiente == 'producao':
                    subscription.cliente.asaas_producao_customer_id = customers[0]['id']
            elif not subscription.asaas_customer_id:
                customer = subscription.cliente
                created = client.request('POST', '/customers', json={'name': customer.razao_social,
                    'email': customer.email_principal, 'cpfCnpj': ''.join(c for c in (customer.cnpj_cpf or '') if c.isdigit()),
                    'externalReference': customer_ref})
                subscription.asaas_customer_id = created['id']
                if subscription.asaas_ambiente == 'sandbox':
                    customer.asaas_sandbox_customer_id = created['id']
                elif subscription.asaas_ambiente == 'producao':
                    customer.asaas_producao_customer_id = created['id']
                db.session.commit()
            due = (subscription.trial_ate if subscription.status == 'TRIAL' else None) or subscription.data_proxima_cobranca or date.today()
            if subscription.produto.codigo in PROPOSTAS_CODES:
                expected_period = subscription.plano.periodicidade
                if expected_period not in PROPOSTAS_VALUES:
                    raise BusinessError('Periodicidade inválida para LiveSun Propostas.')
                value, cycle = PROPOSTAS_VALUES[expected_period]
                billing_type = 'BOLETO'
                value_payload = asaas_value(value)
            else:
                value_payload = asaas_value(subscription.plano.valor_mensal)
                cycle = 'YEARLY' if subscription.plano.periodicidade == 'anual' else 'MONTHLY'
                billing_type = subscription.asaas_forma
            created = client.request('POST', '/subscriptions', json={
                'customer': subscription.asaas_customer_id, 'billingType': billing_type,
                'value': value_payload, 'nextDueDate': max(due, date.today()).isoformat(),
                'cycle': cycle,
                'externalReference': ref, 'description': f'{subscription.produto.nome} / {subscription.plano.nome}'})
            subscription.asaas_subscription_id = created['id']
            db.session.commit()
    if subscription.asaas_subscription_id:
        remote = client.request('GET', '/subscriptions/' + quote(subscription.asaas_subscription_id, safe=''))
        body = {'status': 'INACTIVE' if inactive else 'ACTIVE'}
        if not inactive:
            body.update(value=asaas_value(PROPOSTAS_VALUES[subscription.plano.periodicidade][0])
                        if subscription.produto.codigo in PROPOSTAS_CODES
                        else asaas_value(subscription.plano.valor_mensal),
                        updatePendingPayments=False,
                        cycle='YEARLY' if subscription.plano.periodicidade == 'anual' else 'MONTHLY')
            if remote.get('status') == 'INACTIVE':
                due = (subscription.trial_ate if subscription.status == 'TRIAL' else None) or subscription.data_proxima_cobranca or date.today()
                body['nextDueDate'] = max(due, date.today()).isoformat()
        client.request('PUT', '/subscriptions/' + quote(subscription.asaas_subscription_id, safe=''), json=body)
    # Cobranças já emitidas não são canceladas silenciosamente por suspensão.


def apply_payment(subscription, payment):
    identifier = payment.get('id')
    if not identifier or payment.get('subscription') != subscription.asaas_subscription_id:
        raise BusinessError('Cobrança não pertence à assinatura.')
    due = date.fromisoformat(payment['dueDate'])
    charge = db.session.scalar(db.select(Cobranca).filter_by(
        asaas_ambiente=subscription.asaas_ambiente, gateway_payment_id=identifier))
    if charge and charge.assinatura_id != subscription.id:
        raise BusinessError('Cobrança já pertence a outra assinatura.')
    if charge is None:
        charge = db.session.scalar(db.select(Cobranca).filter_by(assinatura_id=subscription.id, competencia=due.strftime('%Y-%m')))
        if charge and charge.gateway_payment_id != identifier:
            raise BusinessError('Competência já possui outra cobrança; exige reconciliação manual.')
    created = charge is None
    if created:
        charge = Cobranca(assinatura_id=subscription.id, competencia=due.strftime('%Y-%m'),
            gateway='asaas', gateway_payment_id=identifier, referencia_externa=identifier)
        db.session.add(charge)
    before = snapshot(charge) if not created else {}
    charge.valor = Decimal(str(payment['value']))
    charge.vencimento = due
    link = payment.get('invoiceUrl')
    charge.invoice_url = safe_invoice_url(link, subscription.asaas_ambiente)
    status = payment.get('status')
    charge.status = ('PAGA' if status in PAID else 'VENCIDA' if status == 'OVERDUE' else
                     'ESTORNADA' if status in ('REFUNDED', 'CHARGEBACK_REQUESTED',
                                               'CHARGEBACK_DISPUTE') else
                     'CANCELADA' if status == 'DELETED' else 'AGUARDANDO_PAGAMENTO')
    charge.asaas_ambiente = subscription.asaas_ambiente
    charge.billing_type = payment.get('billingType')
    charge.ultimo_evento = str(status)[:100]
    charge.ultimo_evento_em = now()
    if charge.status == 'PAGA':
        paid = payment.get('paymentDate') or payment.get('clientPaymentDate') or date.today().isoformat()
        charge.data_pagamento = datetime.fromisoformat(paid[:10])
        if due >= date.today() - timedelta(days=subscription.carencia_dias):
            from calendar import monthrange
            months = 12 if subscription.plano.periodicidade == 'anual' else 1
            month = due.month - 1 + months
            subscription.data_proxima_cobranca = date(due.year + month // 12, month % 12 + 1,
                min(due.day, monthrange(due.year + month // 12, month % 12 + 1)[1]))
    db.session.flush()
    if created or before.get('status') != charge.status:
        audit(charge, 'ASAAS_COBRANCA_ATUALIZADA', before)
        kind = ('COBRANCA_PAGA' if charge.status == 'PAGA' else
                'COBRANCA_ATRASADA' if charge.status == 'VENCIDA' else 'COBRANCA_CRIADA')
        notice = {'cobranca_id': charge.id, 'tipo': kind, 'invoice_url': charge.invoice_url,
                  'valor': str(charge.valor), 'vencimento': due.isoformat(),
                  'periodicidade': subscription.plano.periodicidade,
                  'ambiente': subscription.asaas_ambiente}
        record(subscription, kind, snapshot(subscription), notification=notice)
    if charge.status == 'PAGA' and subscription.produto.codigo in PROPOSTAS_CODES:
        if subscription.status in ('ATIVA', 'TRIAL'):
            pass
        elif subscription.status == 'SUSPENSA':
            before = snapshot(subscription)
            subscription.status = 'PAGO_AGUARDANDO_LIBERACAO'
            subscription.suspensa_por_inadimplencia = False
            record(subscription, 'ASSINATURA_PAGO_AGUARDANDO_LIBERACAO', before)


def receive(environment, token, payload):
    config = config_for(environment)
    if not token or not hmac.compare_digest(webhook_token(config), token):
        from flask import abort
        abort(401)
    event_id = payload.get('id')
    event_type = payload.get('event')
    payment = payload.get('payment') or {}
    remote_sub = payload.get('subscription') or {}
    if (not isinstance(payment, dict) or not isinstance(remote_sub, dict) or not isinstance(event_id, str)
            or not event_id or len(event_id) > 120 or not isinstance(event_type, str) or len(event_type) > 100):
        raise BusinessError('Evento Asaas inválido.')
    if db.session.scalar(db.select(EventoAsaas.id).filter_by(ambiente=environment, event_id=event_id)):
        return False
    subscription_id = payment.get('subscription') or remote_sub.get('id')
    # Nunca resolve por customer: um cliente pode ter assinaturas de vários produtos.
    known = db.session.scalar(db.select(Assinatura.id).filter_by(asaas_subscription_id=subscription_id,
        asaas_ambiente=environment)) if subscription_id else None
    charge = db.session.scalar(db.select(Cobranca).filter_by(
        asaas_ambiente=environment, gateway_payment_id=payment.get('id'))) if payment.get('id') else None
    db.session.add(EventoAsaas(evento_externo=environment+':'+event_id, ambiente=environment,
        event_id=event_id, payment_id=payment.get('id'), subscription_id=subscription_id,
        cobranca_id=charge.id if charge else None, tipo=event_type,
        data_recebimento=now(),
        status='PENDENTE' if known or charge else 'IGNORADO'))
    db.session.commit()
    return True


def receive_public(token, payload):
    if not token:
        from flask import abort
        abort(401)
    matches = []
    for environment in ('sandbox', 'producao'):
        config = db.session.scalar(db.select(ConfigAsaas).filter_by(
            ambiente=environment, ativo=True))
        if config:
            try:
                expected = webhook_token(config)
            except BusinessError:
                continue
            if hmac.compare_digest(expected, token):
                matches.append(environment)
    if len(matches) == 1:
        return receive(matches[0], token, payload)
    from flask import abort
    abort(401)


def release_access(subscription):
    from flask import has_request_context
    from flask_login import current_user
    if not has_request_context() or not current_user.is_authenticated:
        raise BusinessError('Autenticação de operador necessária.')
    if current_user.perfil not in ('superadmin', 'comercial', 'financeiro'):
        raise BusinessError('Permissão de operador necessária.')
    if current_app.config['APP_ENV'] == 'production' and subscription.asaas_ambiente == 'sandbox':
        raise BusinessError('Pagamento sandbox não autoriza liberação no ambiente de produção.')
    if subscription.status == 'ATIVA':
        return False
    if subscription.status not in ('PAGO_AGUARDANDO_LIBERACAO', 'TRIAL', 'SUSPENSA'):
        raise BusinessError('A assinatura não possui pagamento elegível aguardando liberação.')
    if not subscription.asaas_subscription_id or not subscription.asaas_ambiente:
        raise BusinessError('Assinatura sem vínculo Asaas válido.')
    paid = db.session.scalar(db.select(Cobranca.id).where(
        Cobranca.assinatura_id == subscription.id,
        Cobranca.asaas_ambiente == subscription.asaas_ambiente,
        Cobranca.valor == PROPOSTAS_VALUES[subscription.plano.periodicidade][0]
            if subscription.produto.codigo in PROPOSTAS_CODES else Cobranca.valor > 0,
        Cobranca.status == 'PAGA'))
    if not paid:
        raise BusinessError('Não existe pagamento confirmado vinculado à assinatura e ao ambiente.')
    before = snapshot(subscription)
    subscription.status = 'ATIVA'
    subscription.liberado_por_id = current_user.id
    subscription.liberado_em = now()
    subscription.suspensa_por_inadimplencia = False
    record(subscription, 'ASSINATURA_ATIVADA', before)
    audit(subscription, 'ACESSO_LIBERADO_MANUALMENTE', before)
    return True


def ensure_propostas_plans(product):
    from app.models import Plano
    for periodicidade, (value, cycle) in PROPOSTAS_VALUES.items():
        codigo = 'PROPOSTAS_' + ('MENSAL' if periodicidade == 'mensal' else 'ANUAL')
        plan = db.session.scalar(db.select(Plano).where(
            Plano.produto_id == product.id,
            Plano.codigo == codigo))
        if plan is None:
            from app.models import Plano
            plan = Plano(produto_id=product.id, codigo=codigo,
                         nome='Mensal R$ 80,00' if periodicidade == 'mensal' else 'Anual R$ 600,00',
                         descricao='Cobrança anual única, sem parcelamento.',
                         valor_mensal=value if periodicidade == 'mensal' else value,
                         periodicidade=periodicidade, limite_personalizado_json={}, ativo=True)
            db.session.add(plan)
            db.session.flush()
        elif (plan.valor_mensal != value or plan.periodicidade != periodicidade or not plan.ativo):
            raise BusinessError('Plano LiveSun Propostas divergente da configuração comercial.')
    db.session.flush()


def start_propostas_contratacao(cliente_id, periodicidade, customer_data=None):
    from app.models import Plano
    from app.models import Cliente
    customer = db.session.scalar(db.select(Cliente).where(Cliente.id == cliente_id)
                                 .with_for_update().execution_options(populate_existing=True))
    if not customer or customer.status != 'ATIVO':
        raise BusinessError('Cliente indisponível.')
    from app.models import Produto
    product = db.session.scalar(db.select(Produto).filter_by(
        codigo='PROPOSTAS', ativo=True))
    if not product or not product.config_asaas or not product.config_asaas.ativo:
        raise BusinessError('Configure a cobrança do LiveSun Propostas antes da contratação.')
    if periodicidade not in PROPOSTAS_VALUES:
        raise BusinessError('Plano inválido.')
    existing = db.session.scalar(db.select(Assinatura).where(
        Assinatura.cliente_id == customer.id, Assinatura.produto_id == product.id,
        Assinatura.slot_vigente == 1).with_for_update())
    if existing and existing.asaas_habilitado:
        if existing.asaas_ambiente != product.config_asaas.ambiente:
            raise BusinessError('Vínculo de outro ambiente: reconciliação manual necessária; nenhum ID será reutilizado.')
        return existing, False
    if existing and existing.status not in ('TRIAL', 'ATIVA'):
        raise BusinessError('Assinatura vigente exige revisão do operador antes de contratar.')
    if customer_data:
        customer.razao_social = customer_data['razao_social']
        customer.cnpj_cpf = customer_data['cnpj_cpf']
        customer.email_principal = customer_data['email_principal']
        customer.telefone = customer_data['telefone']
    ensure_propostas_plans(product)
    codigo = 'PROPOSTAS_' + ('MENSAL' if periodicidade == 'mensal' else 'ANUAL')
    plan = db.session.scalar(db.select(Plano).filter_by(produto_id=product.id, codigo=codigo, ativo=True))
    if existing:
        before = snapshot(existing)
        existing.plano = plan
        existing.plano_id = plan.id
        configure_subscription(existing, product.config_asaas.ambiente, 'BOLETO')
        record(existing, 'CONTRATACAO_SOLICITADA', before)
        return existing, False
    before = snapshot(customer)
    subscription = Assinatura(cliente_id=customer.id, produto_id=product.id, plano_id=plan.id,
                              status='TRIAL', data_inicio=date.today(),
                              trial_ate=date.today() + timedelta(days=7),
                              data_proxima_cobranca=date.today(), versao=0, slot_vigente=1)
    db.session.add(subscription)
    db.session.flush()
    from .assinatura_service import apply_plan_modules
    apply_plan_modules(subscription)
    # Contratação não dispara outro aviso de boas-vindas do trial já existente.
    subscription.asaas_habilitado = True
    record(subscription, 'ASSINATURA_CRIADA', {})
    configure_subscription(subscription, product.config_asaas.ambiente,
                           'BOLETO')
    db.session.flush()
    charge = db.session.scalar(db.select(Cobranca).where(
        Cobranca.assinatura_id == subscription.id).order_by(Cobranca.id.desc()))
    return subscription, True


def process_one():
    event = db.session.scalar(db.select(EventoAsaas).where(
        db.or_(EventoAsaas.status == 'PENDENTE',
               db.and_(EventoAsaas.status == 'FALHA',
                       EventoAsaas.atualizado_em <= now() - timedelta(minutes=1)))
    ).order_by(EventoAsaas.id).with_for_update(skip_locked=True))
    if event:
        try:
            obj = db.session.scalar(db.select(Assinatura).filter_by(asaas_subscription_id=event.subscription_id,
                asaas_ambiente=event.ambiente, asaas_habilitado=True).with_for_update())
            if not obj:
                event.status = 'IGNORADO'
            elif event.tipo not in ('PAYMENT_CREATED', 'PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED',
                                    'PAYMENT_OVERDUE', 'PAYMENT_REFUNDED'):
                event.status = 'IGNORADO'
            else:
                client = AsaasClient(config_for(event.ambiente, obj.produto))
                if event.payment_id:
                    payment = client.request('GET', '/payments/' + quote(event.payment_id, safe=''))
                    apply_payment(obj, payment)  # verdade atual, não snapshot potencialmente antigo
                    charge = db.session.scalar(db.select(Cobranca).filter_by(
                        asaas_ambiente=event.ambiente,
                        gateway_payment_id=event.payment_id))
                    event.cobranca_id = charge.id if charge else None
                else:
                    remote = client.request('GET', '/subscriptions/' + quote(event.subscription_id, safe=''))
                    audit(obj, 'ASAAS_ESTADO_CONFERIDO')
                    if remote.get('status') == 'INACTIVE' and obj.status in ('ATIVA', 'TRIAL') and not obj.cortesia:
                        before = snapshot(obj)
                        obj.status = 'SUSPENSA'
                        obj.motivo_status = 'Recorrência desativada no Asaas.'
                        record(obj, 'ASSINATURA_SUSPENSA', before)
                event.status, event.erro = 'PROCESSADO', None
            db.session.commit()
        except Exception:
            db.session.rollback()
            event = db.session.get(EventoAsaas, event.id)
            event.status, event.erro = 'FALHA', 'FALHA_CONSULTA_OU_CONCILIACAO'
            event.atualizado_em = now()
            db.session.commit()
            current_app.logger.warning('asaas', extra={'safe_event': 'asaas_evento_falhou'})
        return True
    operation = db.session.scalar(db.select(OperacaoAsaas).where(OperacaoAsaas.status == 'PENDENTE',
        OperacaoAsaas.proxima_tentativa <= now()).order_by(OperacaoAsaas.id).with_for_update(skip_locked=True))
    if not operation:
        db.session.rollback()
        return False
    identifier = operation.id
    operation.status, operation.tentativas = 'EXECUTANDO', operation.tentativas + 1
    db.session.commit()
    try:
        subscription = locked(operation.assinatura_id)
        client = AsaasClient(config_for(subscription.asaas_ambiente, subscription.produto))
        if operation.tipo == 'SINCRONIZAR':
            sync_subscription(subscription, client)
        if subscription.asaas_subscription_id:
            for payment in client.pages('/subscriptions/' + quote(subscription.asaas_subscription_id, safe='') + '/payments'):
                apply_payment(subscription, payment)
        operation.status = 'CONCLUIDA'
        operation.erro = None
        audit(subscription, 'ASAAS_OPERACAO_CONCLUIDA')
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        operation = db.session.get(OperacaoAsaas, identifier)
        if isinstance(error, AsaasRequestError) and error.safe_to_retry:
            operation.status, operation.erro = 'PENDENTE', error.category
            operation.proxima_tentativa = now() + timedelta(seconds=min(3600, 30 * 2 ** min(operation.tentativas - 1, 7)))
        else:
            # Resposta perdida em escrita pode já ter gerado cobrança.
            operation.status = 'REVISAR'
            operation.erro = error.category if isinstance(error, AsaasRequestError) else 'RECONCILIAR_ANTES_DE_REPETIR'
        db.session.commit()
        current_app.logger.warning('asaas', extra={'safe_event': 'asaas_operacao_' +
            ('nova_tentativa' if operation.status == 'PENDENTE' else 'requer_revisao')})
    finally:
        db.session.remove()
    return True