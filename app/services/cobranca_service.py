from datetime import date, timedelta
from app.extensions import db
from app.models import Cobranca, Assinatura
from app.models.base import now
from .assinatura_service import locked, record, BusinessError, change_status
from .auditoria_service import audit, snapshot


def create_charge(data):
    subscription = locked(data['assinatura_id'])
    if subscription.status in ('EXCLUIDA', 'CANCELADA', 'EXPIRADA'):
        raise BusinessError('Assinatura encerrada.')
    if subscription.cortesia and (not subscription.cortesia_ate or subscription.cortesia_ate >= date.today()):
        raise BusinessError('Assinatura bonificada: cobrança não será criada.')
    charge = Cobranca(**data, status='ABERTA')
    db.session.add(charge)
    db.session.flush()
    audit(charge, 'COBRANCA_CRIADA')
    record(subscription, 'COBRANCA_CRIADA', snapshot(subscription))
    return charge


def pay(charge):
    if charge.status not in ('ABERTA', 'ATRASADA'):
        raise BusinessError('Cobrança não está em aberto.')
    subscription = locked(charge.assinatura_id)
    before = snapshot(charge)
    charge.status, charge.data_pagamento = 'PAGA', now()
    audit(charge, 'COBRANCA_PAGA', before)
    record(subscription, 'COBRANCA_PAGA', snapshot(subscription))


def maintenance():
    from .assinatura_service import record
    for charge in db.session.scalars(db.select(Cobranca).where(
            Cobranca.status == 'ABERTA', Cobranca.vencimento < date.today()).with_for_update()):
        before = snapshot(charge)
        charge.status = 'ATRASADA'
        audit(charge, 'COBRANCA_ATRASADA', before)
        subscription = locked(charge.assinatura_id)
        record(subscription, 'COBRANCA_ATRASADA', snapshot(subscription))
    for subscription in db.session.scalars(db.select(Assinatura).where(
            Assinatura.data_fim < date.today(), Assinatura.status.in_(['TRIAL', 'ATIVA', 'SUSPENSA', 'BLOQUEADA']))):
        change_status(locked(subscription.id), 'EXPIRADA', 'Fim da validade contratual.')
    db.session.commit()
    for obj in db.session.scalars(db.select(Assinatura).where(Assinatura.slot_vigente == 1).with_for_update()):
        if obj.cortesia and obj.cortesia_ate and obj.cortesia_ate < date.today():
            before = snapshot(obj)
            obj.cortesia = False
            record(obj, 'CORTESIA_ENCERRADA', before)
            if obj.asaas_habilitado:
                from .asaas_service import enqueue
                enqueue(obj, 'SINCRONIZAR')
        courtesy = obj.cortesia and (not obj.cortesia_ate or obj.cortesia_ate >= date.today())
        late = db.session.scalar(db.select(Cobranca.id).where(Cobranca.assinatura_id == obj.id,
            Cobranca.status == 'ATRASADA', Cobranca.vencimento < date.today() - timedelta(days=obj.carencia_dias)))
        trial_ended = obj.status == 'TRIAL' and obj.trial_ate and obj.trial_ate <= date.today()
        if not courtesy and obj.status in ('ATIVA', 'TRIAL') and (late or trial_ended):
            before = snapshot(obj)
            obj.status, obj.suspensa_por_inadimplencia = 'SUSPENSA', True
            obj.motivo_status = 'Prazo de pagamento/trial encerrado.'
            record(obj, 'ASSINATURA_SUSPENSA', before)
        if obj.asaas_habilitado and obj.asaas_subscription_id and not courtesy:
            from app.models import OperacaoAsaas
            last = db.session.scalar(db.select(OperacaoAsaas).where(OperacaoAsaas.assinatura_id == obj.id,
                OperacaoAsaas.tipo == 'CONSULTAR').order_by(OperacaoAsaas.id.desc()).limit(1))
            if not last or (last.status == 'CONCLUIDA' and last.atualizado_em < now() - timedelta(hours=1)):
                from .asaas_service import enqueue
                enqueue(obj, 'CONSULTAR')
    db.session.commit()