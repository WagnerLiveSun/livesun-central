from app.extensions import db
from .base import Base


class EventoAssinatura(Base):
    __tablename__ = 'eventos_assinatura'
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False, index=True)
    evento_id = db.Column(db.String(50), nullable=False, unique=True)
    tipo_evento = db.Column(db.String(50), nullable=False)
    dados_anteriores = db.Column(db.JSON, nullable=False)
    dados_novos = db.Column(db.JSON, nullable=False)
    usuario_responsavel = db.Column(db.String(150), nullable=False)
    ip_origem = db.Column(db.String(45))


class Auditoria(Base):
    __tablename__ = 'auditoria_central'
    entidade = db.Column(db.String(50), nullable=False)
    entidade_id = db.Column(db.Integer)
    acao = db.Column(db.String(60), nullable=False)
    anterior = db.Column(db.JSON, nullable=False)
    novo = db.Column(db.JSON, nullable=False)
    responsavel = db.Column(db.String(150), nullable=False)
    ip_origem = db.Column(db.String(45))