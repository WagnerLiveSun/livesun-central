from app.extensions import db
from .base import Base


class Cobranca(Base):
    __tablename__ = 'cobrancas'
    __table_args__ = (
        db.UniqueConstraint('assinatura_id', 'competencia'),
        db.UniqueConstraint('asaas_ambiente', 'gateway_payment_id',
                            name='uq_cobrancas_asaas_ambiente_gateway_payment_id'),
    )
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False)
    competencia = db.Column(db.String(7), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ABERTA')
    data_pagamento = db.Column(db.DateTime)
    gateway = db.Column(db.String(50))
    referencia_externa = db.Column(db.String(150))
    observacoes = db.Column(db.Text)
    gateway_payment_id = db.Column(db.String(100), index=True)
    invoice_url = db.Column(db.String(1000))
    asaas_ambiente = db.Column(db.String(20), index=True)
    billing_type = db.Column(db.String(20))
    ultimo_evento = db.Column(db.String(100))
    ultimo_evento_em = db.Column(db.DateTime)