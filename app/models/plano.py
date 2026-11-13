from app.extensions import db
from .base import Base


class Plano(Base):
    __tablename__ = 'planos'
    __table_args__ = (db.UniqueConstraint('produto_id', 'codigo'),)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    valor_mensal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    periodicidade = db.Column(db.String(20), nullable=False, default='mensal')
    limite_usuarios = db.Column(db.Integer)
    limite_registros = db.Column(db.Integer)
    limite_armazenamento_mb = db.Column(db.Integer)
    limite_personalizado_json = db.Column(db.JSON, nullable=False, default=dict)
    ativo = db.Column(db.Boolean, nullable=False, default=True)


class PlanoModulo(Base):
    __tablename__ = 'plano_modulos'
    __table_args__ = (db.UniqueConstraint('plano_id', 'modulo_id'),)
    plano_id = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulos.id'), nullable=False)
    liberado = db.Column(db.Boolean, nullable=False, default=True)
    limite = db.Column(db.Integer)