import json
from datetime import timedelta
from uuid import uuid4
import requests
from app.extensions import db
from app.models import PurgaProduto, Assinatura
from app.models.base import now, iso
from app.security import decrypt
from .assinatura_service import BusinessError
from .auditoria_service import audit, snapshot
from .webhook_service import signed_headers, validate_destination


def schedule(subscription, reason):
    entry = db.session.scalar(db.select(PurgaProduto).filter_by(assinatura_id=subscription.id))
    if not entry:
        entry = PurgaProduto(assinatura_id=subscription.id, operacao_id='prg_' + uuid4().hex,
            executar_em=(subscription.excluida_em or now()) + timedelta(days=60), motivo=reason)
        db.session.add(entry)
        db.session.flush()
        audit(entry, 'PURGA_AGENDADA')
    return entry


def anticipate(subscription, reason):
    if subscription.status != 'EXCLUIDA' or not reason.strip():
        raise BusinessError('Purga exige exclusão lógica anterior e justificativa.')
    entry = schedule(subscription, reason)
    if entry.status in ('CONCLUIDA', 'EXECUTANDO'):
        raise BusinessError('Purga concluída ou em execução.')
    before = snapshot(entry)
    entry.antecipada, entry.executar_em, entry.motivo, entry.status = True, now(), reason, 'AGENDADA'
    audit(entry, 'PURGA_ANTECIPADA_AUTORIZADA', before)


def process_one():
    entry = db.session.scalar(db.select(PurgaProduto).where(
        db.or_(db.and_(PurgaProduto.status.in_(['AGENDADA', 'FALHA']), PurgaProduto.executar_em <= now()),
               db.and_(PurgaProduto.status == 'EXECUTANDO', PurgaProduto.lease_ate < now())))
        .order_by(PurgaProduto.id).with_for_update(skip_locked=True))
    if not entry:
        db.session.rollback()
        return False
    subscription = entry.assinatura
    if subscription.status != 'EXCLUIDA':
        entry.status, entry.erro = 'IMPEDIDA', 'ASSINATURA_NAO_EXCLUIDA'
        db.session.commit()
        return True
    other = db.session.scalar(db.select(Assinatura.id).where(Assinatura.cliente_id == subscription.cliente_id,
        Assinatura.produto_id == subscription.produto_id, Assinatura.slot_vigente == 1))
    if other:
        entry.status, entry.erro = 'IMPEDIDA', 'NOVA_ASSINATURA_VIGENTE_NO_PRODUTO'
        db.session.commit()
        return True
    if subscription.asaas_habilitado and subscription.asaas_subscription_id:
        from app.models import OperacaoAsaas
        unresolved = db.session.scalar(db.select(OperacaoAsaas.id).where(
            OperacaoAsaas.assinatura_id == subscription.id, OperacaoAsaas.tipo == 'SINCRONIZAR',
            OperacaoAsaas.status != 'CONCLUIDA'))
        if unresolved:
            entry.status, entry.erro = 'FALHA', 'REGULARIZAR_RECORRENCIA_ASAAS_ANTES_DA_PURGA'
            entry.executar_em = now() + timedelta(hours=1)
            db.session.commit()
            return True
    entry.status, entry.lease_ate = 'EXECUTANDO', now() + timedelta(minutes=5)
    entry.tentativas += 1
    db.session.commit()
    try:
        product = subscription.produto
        if product.codigo != 'COMERCIAL':
            raise BusinessError('Receptor de purga ainda não homologado para este produto.')
        if not product.url_producao or not product.webhook_secret:
            raise BusinessError('Produto sem integração de purga.')
        url = product.url_producao.rstrip('/') + '/central/purgar'
        validate_destination(url)
        payload = {'operacao_id': entry.operacao_id, 'cliente_id': str(subscription.cliente_id),
            'produto': product.codigo, 'assinatura_id': subscription.id, 'status': 'EXCLUIDA',
            'versao': subscription.versao, 'excluida_em': iso(subscription.excluida_em),
            'antecipada': entry.antecipada}
        raw = json.dumps(payload, separators=(',', ':')).encode()
        headers = signed_headers(decrypt(product.webhook_secret), raw)
        headers['X-LiveSun-Event'] = 'PURGA_SOLICITADA'
        with requests.Session() as http:
            http.trust_env = False
            response = http.post(url, data=raw, headers=headers, timeout=(5, 90), allow_redirects=False)
        if response.status_code != 200 or response.json().get('operacao_id') != entry.operacao_id:
            raise BusinessError('Produto não confirmou a purga.')
        entry.status, entry.concluida_em, entry.erro = 'CONCLUIDA', now(), None
        audit(entry, 'PURGA_PRODUTO_CONCLUIDA')
    except Exception:
        entry.status, entry.erro = 'FALHA', 'PURGA_NAO_CONFIRMADA'
        entry.executar_em = now() + timedelta(minutes=min(1440, 2 ** min(entry.tentativas, 10)))
    entry.lease_ate = None
    db.session.commit()
    return True