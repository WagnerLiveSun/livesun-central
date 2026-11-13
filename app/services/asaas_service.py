"""Asaas exclusivo de assinaturas LiveSun; não recebe cobranças bancárias de tenants."""
import hmac
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import quote, urlsplit
import requests
from app.extensions import db
from app.models import Assinatura, Cobranca, ConfigAsaas, EventoAsaas, OperacaoAsaas
from app.models.base import now
from app.security import decrypt
from .assinatura_service import BusinessError, locked, record
from .auditoria_service import audit, snapshot

BASES = {'sandbox': 'https://api-sandbox.asaas.com/v3', 'producao': 'https://api.asaas.com/v3'}
PAID = {'RECEIVED', 'CONFIRMED', 'RECEIVED_IN_CASH', 'DUNNING_RECEIVED'}


class AsaasClient:
    def __init__(self, config):
        self.base = BASES[config.ambiente]
        self.key = decrypt(config.api_key)

    def request(self, method, path, **kwargs):
        with requests.Session() as http:
            http.trust_env = False
            response = http.request(method, self.base + path, headers={
                'access_token': self.key, 'User-Agent': 'LiveSun-Central/1.0',
                'Content-Type': 'application/json'}, timeout=(5, 20), allow_redirects=False, **kwargs)
            if not 200 <= response.status_code < 300:
                raise BusinessError('Asaas recusou a operação. Confira ambiente e configuração.')
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
    if form not in ('BOLETO', 'PIX'):
        raise BusinessError('Use boleto ou Pix; cartão exige fluxo de tokenização separado.')
    if subscription.asaas_subscription_id and existing_id and existing_id != subscription.asaas_subscription_id:
        raise BusinessError('Assinatura já vinculada a outra recorrência.')
    if subscription.asaas_subscription_id and subscription.asaas_ambiente != environment:
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
            elif not subscription.asaas_customer_id:
                customer = subscription.cliente
                created = client.request('POST', '/customers', json={'name': customer.razao_social,
                    'email': customer.email_principal, 'cpfCnpj': ''.join(c for c in (customer.cnpj_cpf or '') if c.isdigit()),
                    'externalReference': customer_ref})
                subscription.asaas_customer_id = created['id']
                db.session.commit()
            due = subscription.trial_ate or subscription.data_proxima_cobranca or date.today()
            created = client.request('POST', '/subscriptions', json={
                'customer': subscription.asaas_customer_id, 'billingType': subscription.asaas_forma,
                'value': float(subscription.plano.valor_mensal), 'nextDueDate': max(due, date.today()).isoformat(),
                'cycle': 'YEARLY' if subscription.plano.periodicidade == 'anual' else 'MONTHLY',
                'externalReference': ref, 'description': f'{subscription.produto.nome} / {subscription.plano.nome}'})
            subscription.asaas_subscription_id = created['id']
            db.session.commit()
    if subscription.asaas_subscription_id:
        remote = client.request('GET', '/subscriptions/' + quote(subscription.asaas_subscription_id, safe=''))
        body = {'status': 'INACTIVE' if inactive else 'ACTIVE'}
        if not inactive:
            body.update(value=float(subscription.plano.valor_mensal), updatePendingPayments=False,
                        cycle='YEARLY' if subscription.plano.periodicidade == 'anual' else 'MONTHLY')
            if remote.get('status') == 'INACTIVE':
                due = subscription.trial_ate or subscription.data_proxima_cobranca or date.today()
                body['nextDueDate'] = max(due, date.today()).isoformat()
        client.request('PUT', '/subscriptions/' + quote(subscription.asaas_subscription_id, safe=''), json=body)
    # Cobranças já emitidas não são canceladas silenciosamente por suspensão.


def apply_payment(subscription, payment):
    identifier = payment.get('id')
    if not identifier or payment.get('subscription') != subscription.asaas_subscription_id:
        raise BusinessError('Cobrança não pertence à assinatura.')
    due = date.fromisoformat(payment['dueDate'])
    charge = db.session.scalar(db.select(Cobranca).filter_by(gateway_payment_id=identifier))
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
    charge.invoice_url = link if link and urlsplit(link).scheme == 'https' else None
    status = payment.get('status')
    charge.status = ('PAGA' if status in PAID else 'ATRASADA' if status == 'OVERDUE' else
                     'CANCELADA' if status in ('DELETED', 'REFUNDED', 'CHARGEBACK_REQUESTED', 'CHARGEBACK_DISPUTE') else 'ABERTA')
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
        record(subscription, 'COBRANCA_PAGA' if charge.status == 'PAGA' else
            'COBRANCA_ATRASADA' if charge.status == 'ATRASADA' else 'COBRANCA_CRIADA', snapshot(subscription))
    if charge.status == 'PAGA':
        overdue = db.session.scalar(db.select(Cobranca.id).where(Cobranca.assinatura_id == subscription.id,
            Cobranca.status == 'ATRASADA', Cobranca.vencimento < date.today() - timedelta(days=subscription.carencia_dias)))
        if (not overdue and due >= date.today() - timedelta(days=subscription.carencia_dias)
                and (subscription.suspensa_por_inadimplencia or subscription.status == 'TRIAL')):
            before = snapshot(subscription)
            subscription.status, subscription.suspensa_por_inadimplencia = 'ATIVA', False
            record(subscription, 'ASSINATURA_REATIVADA', before)


def receive(environment, token, payload):
    config = config_for(environment)
    if not token or not hmac.compare_digest(decrypt(config.webhook_token), token):
        from flask import abort
        abort(401)
    event_id = payload.get('id')
    event_type = payload.get('event')
    payment = payload.get('payment') or {}
    remote_sub = payload.get('subscription') or {}
    if (not isinstance(payment, dict) or not isinstance(remote_sub, dict) or not isinstance(event_id, str)
            or not event_id or len(event_id) > 120 or not isinstance(event_type, str) or len(event_type) > 100):
        raise BusinessError('Evento Asaas inválido.')
    if db.session.scalar(db.select(EventoAsaas.id).filter_by(evento_externo=environment + ':' + event_id)):
        return False
    subscription_id = payment.get('subscription') or remote_sub.get('id')
    # Nunca resolve por customer: um cliente pode ter assinaturas de vários produtos.
    known = db.session.scalar(db.select(Assinatura.id).filter_by(asaas_subscription_id=subscription_id,
        asaas_ambiente=environment)) if subscription_id else None
    db.session.add(EventoAsaas(evento_externo=environment+':'+event_id, ambiente=environment,
        payment_id=payment.get('id'), subscription_id=subscription_id, tipo=event_type,
        status='PENDENTE' if known else 'IGNORADO'))
    db.session.commit()
    return True


def process_one():
    event = db.session.scalar(db.select(EventoAsaas).filter_by(status='PENDENTE').order_by(EventoAsaas.id).with_for_update(skip_locked=True))
    if event:
        try:
            obj = db.session.scalar(db.select(Assinatura).filter_by(asaas_subscription_id=event.subscription_id,
                asaas_ambiente=event.ambiente, asaas_habilitado=True).with_for_update())
            if not obj:
                event.status = 'IGNORADO'
            else:
                client = AsaasClient(config_for(event.ambiente, obj.produto))
                if event.payment_id:
                    payment = client.request('GET', '/payments/' + quote(event.payment_id, safe=''))
                    apply_payment(obj, payment)  # verdade atual, não snapshot potencialmente antigo
                else:
                    remote = client.request('GET', '/subscriptions/' + quote(event.subscription_id, safe=''))
                    audit(obj, 'ASAAS_ESTADO_CONFERIDO')
                    if remote.get('status') == 'INACTIVE' and obj.status in ('ATIVA', 'TRIAL') and not obj.cortesia:
                        before = snapshot(obj)
                        obj.status = 'SUSPENSA'
                        obj.motivo_status = 'Recorrência desativada no Asaas.'
                        record(obj, 'ASSINATURA_SUSPENSA', before)
                event.status = 'PROCESSADO'
            db.session.commit()
        except Exception:
            db.session.rollback()
            event = db.session.get(EventoAsaas, event.id)
            event.status, event.erro = 'FALHA', 'FALHA_CONSULTA_OU_CONCILIACAO'
            db.session.commit()
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
        audit(subscription, 'ASAAS_OPERACAO_CONCLUIDA')
        db.session.commit()
    except Exception:
        db.session.rollback()
        operation = db.session.get(OperacaoAsaas, identifier)
        # POST com resposta perdida é ambíguo: não recriar automaticamente recorrência.
        operation.status, operation.erro = 'REVISAR', 'RECONCILIAR_ANTES_DE_REPETIR'
        db.session.commit()
    finally:
        db.session.remove()
    return True