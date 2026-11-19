"""Notificações transacionais de acesso, sem campanhas ou conteúdo sensível."""
from app.extensions import db
from .base import now


class NotificacaoAcesso(db.Model):
    __tablename__ = 'notificacoes_acesso'
    __table_args__ = (
        db.UniqueConstraint('evento_id', name='uq_notificacoes_acesso_evento_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    evento_id = db.Column(db.String(50), db.ForeignKey('eventos_assinatura.evento_id'), nullable=False, unique=True)
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False)
    destinatario_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(25), nullable=False, default='PENDENTE')
    criada_em = db.Column(db.DateTime, nullable=False, default=now)
    proxima_tentativa = db.Column(db.DateTime, nullable=False, default=now)
    lease_ate = db.Column(db.DateTime)
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    evento = db.relationship('EventoAssinatura')
    assinatura = db.relationship('Assinatura')


class TentativaNotificacaoAcesso(db.Model):
    __tablename__ = 'tentativas_notificacao_acesso'
    id = db.Column(db.Integer, primary_key=True)
    notificacao_id = db.Column(db.Integer, db.ForeignKey('notificacoes_acesso.id'), nullable=False, index=True)
    numero = db.Column(db.Integer, nullable=False)
    resultado = db.Column(db.String(25), nullable=False, default='INICIADA')
    categoria = db.Column(db.String(40))
    iniciada_em = db.Column(db.DateTime, nullable=False, default=now)
    concluida_em = db.Column(db.DateTime)