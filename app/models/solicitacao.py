from app.extensions import db
from .base import Base


class SolicitacaoCadastro(Base):
    __tablename__ = 'solicitacoes_cadastro'
    __table_args__ = (db.UniqueConstraint('produto_id', 'empresa_origem'),)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False, index=True)
    empresa_origem = db.Column(db.String(50), nullable=False)
    evento_origem = db.Column(db.String(50), nullable=False)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj_cpf = db.Column(db.String(18), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    telefone = db.Column(db.String(30))
    responsavel = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(25), nullable=False, default='PENDENTE', index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'))
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'))
    motivo = db.Column(db.String(500))
    tentativas_vinculo = db.Column(db.Integer, nullable=False, default=0)
    erro_vinculo = db.Column(db.String(100))
    proxima_tentativa = db.Column(db.DateTime)
    vinculado_em = db.Column(db.DateTime)
    produto = db.relationship('Produto')
    cliente = db.relationship('Cliente')
    assinatura = db.relationship('Assinatura')