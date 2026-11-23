from app.extensions import db
from .base import Base


class GatewayAlternativo(Base):
    __tablename__ = 'gateways_alternativos'
    __table_args__ = (db.UniqueConstraint('produto_id', 'nome', 'ambiente',
                                         name='uq_gateway_alternativo_produto_nome_ambiente'),)

    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False, index=True)
    codigo_banco = db.Column(db.String(3), db.ForeignKey('instituicoes_bancarias.codigo_banco'), nullable=True, index=True)
    nome = db.Column(db.String(100), nullable=False)
    ambiente = db.Column(db.String(20), nullable=False)
    url_api = db.Column(db.String(500), nullable=False)
    url_callback = db.Column(db.String(500))
    credenciais_criptografadas = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    produto = db.relationship('Produto')
    instituicao = db.relationship('InstituicaoBancaria')