from app.extensions import db
from .base import Base


class Entitlement(Base):
    __tablename__ = 'entitlements'
    __table_args__ = (db.UniqueConstraint('assinatura_id', 'chave'),)
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False)
    chave = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.JSON)
    limite = db.Column(db.Integer)
    ativo = db.Column(db.Boolean, nullable=False, default=True)