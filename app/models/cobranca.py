from app.extensions import db
from .base import Base


class Cobranca(Base):
    __tablename__ = 'cobrancas'
    __table_args__ = (db.UniqueConstraint('assinatura_id', 'competencia'),)
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False)
    competencia = db.Column(db.String(7), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ABERTA')
    data_pagamento = db.Column(db.DateTime)
    gateway = db.Column(db.String(50))
    referencia_externa = db.Column(db.String(150))
    observacoes = db.Column(db.Text)
    gateway_payment_id = db.Column(db.String(100), unique=True)
    invoice_url = db.Column(db.String(1000))