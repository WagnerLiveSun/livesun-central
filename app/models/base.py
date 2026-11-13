from datetime import datetime, timezone
from app.extensions import db


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class Base(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=now)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)


STATUSES = ('TRIAL', 'ATIVA', 'SUSPENSA', 'BLOQUEADA', 'CANCELADA', 'EXPIRADA', 'EXCLUIDA')
EVENTS = ('ASSINATURA_CRIADA', 'ASSINATURA_ATIVADA', 'ASSINATURA_SUSPENSA',
          'ASSINATURA_BLOQUEADA', 'ASSINATURA_REATIVADA', 'ASSINATURA_CANCELADA',
          'ASSINATURA_EXPIRADA', 'ASSINATURA_EXCLUIDA', 'PLANO_ALTERADO',
          'MODULO_LIBERADO', 'MODULO_REMOVIDO', 'LIMITE_ALTERADO',
          'COBRANCA_CRIADA', 'COBRANCA_PAGA', 'COBRANCA_ATRASADA')