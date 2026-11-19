"""Processado exclusivamente pelo worker existente; sem backfill retroativo."""
import hashlib
from datetime import timedelta
from urllib.parse import urlsplit
from flask import current_app, render_template
from app.extensions import db
from app.models import (NotificacaoAcesso, TentativaNotificacaoAcesso, SolicitacaoCadastro,
                        WebhookEntrega, EventoAssinatura)
from app.models.base import now
from .entitlement_service import effective
from .email_service import send_access_email

EVENTS = {'ASSINATURA_CRIADA', 'ASSINATURA_ATIVADA', 'ASSINATURA_REATIVADA'}
FINANCIAL_EVENTS = {'COBRANCA_CRIADA', 'COBRANCA_PAGA', 'COBRANCA_ATRASADA'}


def recipient_hash(email):
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def register_event(event, subscription):
    if not current_app.config['ACCESS_EMAIL_ENABLED']:
        return
    if subscription.produto.codigo != 'PROPOSTAS':
        return
    billing = event.dados_novos.get('notificacao_cobranca')
    if event.tipo_evento == 'ASSINATURA_CRIADA' and subscription.asaas_habilitado:
        return
    if billing and event.tipo_evento in FINANCIAL_EVENTS:
        # Mesmo outbox e worker de acesso. Nenhum backfill de eventos antigos.
        prior = db.session.scalars(db.select(NotificacaoAcesso).where(
            NotificacaoAcesso.assinatura_id == subscription.id)).all()
        if any((row.evento.dados_novos.get('notificacao_cobranca') or {}).get('cobranca_id') == billing['cobranca_id']
               and row.evento.tipo_evento == event.tipo_evento for row in prior):
            return
    elif event.tipo_evento not in EVENTS or not effective(subscription)['acesso_produto']:
        return
    db.session.add(NotificacaoAcesso(evento_id=event.evento_id, assinatura_id=subscription.id,
        destinatario_hash=recipient_hash(subscription.cliente.email_principal)))


def process_one():
    if not current_app.config['ACCESS_EMAIL_ENABLED']:
        return False
    instant = now()
    # Processo caiu após claim: resultado ambíguo, não repetir mensagem.
    expired = db.session.scalars(db.select(NotificacaoAcesso).where(
        NotificacaoAcesso.status == 'ENVIANDO', NotificacaoAcesso.lease_ate < instant).with_for_update(skip_locked=True)).all()
    for item in expired:
        item.status, item.lease_ate = 'INCERTO', None
        attempt = db.session.scalar(db.select(TentativaNotificacaoAcesso).where(
            TentativaNotificacaoAcesso.notificacao_id == item.id,
            TentativaNotificacaoAcesso.resultado == 'INICIADA'))
        if attempt:
            attempt.resultado, attempt.categoria, attempt.concluida_em = 'INCERTO', 'PROCESSO_INTERROMPIDO', instant
    db.session.commit()
    item = db.session.scalar(db.select(NotificacaoAcesso).where(
        NotificacaoAcesso.status == 'PENDENTE', NotificacaoAcesso.proxima_tentativa <= instant)
        .order_by(NotificacaoAcesso.id).with_for_update(skip_locked=True))
    if item is None:
        db.session.rollback()
        return False
    subscription = item.assinatura
    event = item.evento
    snapshot = event.dados_novos
    billing = snapshot.get('notificacao_cobranca')
    if billing:
        return process_billing(item, billing, instant)
    newer = db.session.scalar(db.select(NotificacaoAcesso.id).where(
        NotificacaoAcesso.assinatura_id == item.assinatura_id,
        NotificacaoAcesso.id > item.id).join(NotificacaoAcesso.evento)
        .where(EventoAssinatura.tipo_evento.in_(EVENTS)))
    if (not effective(subscription)['acesso_produto'] or subscription.status != snapshot.get('status')
            or newer is not None
            or subscription.produto.codigo != 'PROPOSTAS'
            or recipient_hash(subscription.cliente.email_principal) != item.destinatario_hash):
        item.status = 'CANCELADA'
        db.session.commit()
        return True
    registration = db.session.scalar(db.select(SolicitacaoCadastro).where(
        SolicitacaoCadastro.assinatura_id == subscription.id))
    delivered = db.session.scalar(db.select(WebhookEntrega.id).where(
        WebhookEntrega.evento_id == item.evento_id, WebhookEntrega.status == 'ENTREGUE'))
    if (registration and registration.status != 'VINCULADA') or (not registration and not delivered):
        item.proxima_tentativa = instant + timedelta(seconds=30)
        db.session.commit()
        return False
    parsed = urlsplit(subscription.produto.url_producao or '')
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        item.status = 'FALHA'
        attempt = TentativaNotificacaoAcesso(notificacao_id=item.id, numero=item.tentativas + 1,
            resultado='FALHA', categoria='URL_PRODUTO_INVALIDA', concluida_em=instant)
        item.tentativas += 1
        db.session.add(attempt)
        db.session.commit()
        return True
    recipient, name = subscription.cliente.email_principal, subscription.cliente.nome_fantasia or subscription.cliente.razao_social
    if (subscription.asaas_ambiente == 'sandbox'
            and recipient.lower() not in current_app.config.get('EMAIL_TEST_RECIPIENTS', [])):
        item.status = 'CANCELADA'
        db.session.commit()
        return True
    if subscription.status == 'TRIAL' and not subscription.trial_ate:
        item.status = 'FALHA'
        db.session.add(TentativaNotificacaoAcesso(notificacao_id=item.id, numero=item.tentativas + 1,
            resultado='FALHA', categoria='PRAZO_TRIAL_AUSENTE', concluida_em=instant))
        item.tentativas += 1
        db.session.commit()
        return True
    html = render_template('email/acesso_liberado.html', nome=name, status=subscription.status,
        inicio=subscription.data_inicio, trial_ate=subscription.trial_ate if subscription.status == 'TRIAL' else None,
        access_url=subscription.produto.url_producao.rstrip('/') + '/auth/login')
    item.status, item.lease_ate = 'ENVIANDO', instant + timedelta(minutes=2)
    item.tentativas += 1
    attempt = TentativaNotificacaoAcesso(notificacao_id=item.id, numero=item.tentativas)
    db.session.add(attempt)
    db.session.flush()
    identifier, attempt_id = item.id, attempt.id
    db.session.commit()
    try:
        result, category = send_access_email(recipient, name, html)
    except Exception:
        result, category = 'INCERTO', 'RESULTADO_NAO_CONFIRMADO'
    item = db.session.get(NotificacaoAcesso, identifier)
    attempt = db.session.get(TentativaNotificacaoAcesso, attempt_id)
    attempt.resultado, attempt.categoria, attempt.concluida_em = result, category, now()
    item.status, item.lease_ate = result, None
    if result == 'FALHA_TEMPORARIA' and item.tentativas < 3:
        item.status, item.proxima_tentativa = 'PENDENTE', now() + timedelta(minutes=5)
    db.session.commit()
    if result != 'ACEITA_BREVO':
        current_app.logger.warning('access_email', extra={'safe_event': 'access_email_not_confirmed'})
    return True


def process_billing(item, billing, instant):
    """Envio separado da transação financeira; resultado incerto nunca é reenviado."""
    from .email_service import send_template_email
    from app.models import Cobranca
    charge = db.session.get(Cobranca, billing['cobranca_id'])
    recipient = item.assinatura.cliente.email_principal
    expected = {'COBRANCA_CRIADA': 'AGUARDANDO_PAGAMENTO', 'COBRANCA_PAGA': 'PAGA',
                'COBRANCA_ATRASADA': 'VENCIDA'}
    allowed = current_app.config.get('EMAIL_TEST_RECIPIENTS', [])
    if (not charge or charge.assinatura_id != item.assinatura_id
            or charge.asaas_ambiente != billing['ambiente']
            or charge.status != expected.get(billing['tipo'])
            or recipient_hash(recipient) != item.destinatario_hash
            or (billing['ambiente'] == 'sandbox' and recipient.lower() not in allowed)
            or (billing['tipo'] == 'COBRANCA_CRIADA' and not billing.get('invoice_url'))):
        item.status = 'CANCELADA'
        db.session.commit()
        return True
    templates = {'COBRANCA_CRIADA': ('Cobrança criada — LiveSun Propostas', 'cobranca_criada'),
                 'COBRANCA_PAGA': ('Pagamento confirmado — LiveSun Propostas', 'pagamento_confirmado'),
                 'COBRANCA_ATRASADA': ('Cobrança vencida — LiveSun Propostas', 'cobranca_vencida')}
    subject, template = templates[billing['tipo']]
    item.status, item.lease_ate = 'ENVIANDO', instant + timedelta(minutes=2)
    item.tentativas += 1
    attempt = TentativaNotificacaoAcesso(notificacao_id=item.id, numero=item.tentativas)
    db.session.add(attempt)
    db.session.flush()
    identifier, attempt_id = item.id, attempt.id
    name = item.assinatura.cliente.nome_fantasia or item.assinatura.cliente.razao_social
    db.session.commit()
    try:
        result, category = send_template_email(recipient, name, subject,
            'email/' + template + '.html', billing)
    except Exception:
        result, category = 'INCERTO', 'RESULTADO_NAO_CONFIRMADO'
    item = db.session.get(NotificacaoAcesso, identifier)
    attempt = db.session.get(TentativaNotificacaoAcesso, attempt_id)
    attempt.resultado, attempt.categoria, attempt.concluida_em = result, category, now()
    item.status, item.lease_ate = result, None
    if result == 'FALHA_TEMPORARIA' and item.tentativas < 3:
        item.status, item.proxima_tentativa = 'PENDENTE', now() + timedelta(minutes=5)
    db.session.commit()
    return True