from app.extensions import db
from .base import Base


class WebhookEntrega(Base):
    __tablename__ = 'webhook_entregas'
    evento_id = db.Column(db.String(50), db.ForeignKey('eventos_assinatura.evento_id'), nullable=False, unique=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    url_destino = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDENTE', index=True)
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    resposta_http = db.Column(db.Integer)
    erro = db.Column(db.String(100))
    payload = db.Column(db.JSON, nullable=False)
    proxima_tentativa = db.Column(db.DateTime, nullable=False, index=True)
    lease_ate = db.Column(db.DateTime)
    produto = db.relationship('Produto')


class WebhookTentativa(Base):
    __tablename__ = 'webhook_tentativas'
    entrega_id = db.Column(db.Integer, db.ForeignKey('webhook_entregas.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    resposta_http = db.Column(db.Integer)
    erro = db.Column(db.String(100))