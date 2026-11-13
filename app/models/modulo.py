from app.extensions import db
from .base import Base


class Modulo(Base):
    __tablename__ = 'modulos'
    __table_args__ = (db.UniqueConstraint('produto_id', 'codigo'),)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    codigo = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    depende_de = db.Column(db.JSON, nullable=False, default=list)  # códigos do mesmo produto
    obrigatorio = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)