from app.extensions import db
from .base import Base


class CredencialServico(Base):
    __tablename__ = 'credenciais_servico'
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False, index=True)
    digest = db.Column(db.String(64), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    scopes = db.Column(db.JSON, nullable=False, default=lambda: ['read'])


class ConfigAsaas(Base):
    __tablename__ = 'config_asaas_assinaturas'
    ambiente = db.Column(db.String(20), nullable=False, unique=True)
    api_key = db.Column(db.Text, nullable=False)
    webhook_token = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=False)


class EventoAsaas(Base):
    __tablename__ = 'eventos_asaas_central'
    evento_externo = db.Column(db.String(150), nullable=False, unique=True)
    ambiente = db.Column(db.String(20), nullable=False)
    payment_id = db.Column(db.String(100))
    subscription_id = db.Column(db.String(100))
    tipo = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDENTE')
    erro = db.Column(db.String(100))


class OperacaoAsaas(Base):
    __tablename__ = 'operacoes_asaas_central'
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False, index=True)
    tipo = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='PENDENTE')
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    erro = db.Column(db.String(100))
    proxima_tentativa = db.Column(db.DateTime, nullable=False)


class PurgaProduto(Base):
    __tablename__ = 'purgas_produto'
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False, unique=True)
    operacao_id = db.Column(db.String(50), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default='AGENDADA')
    executar_em = db.Column(db.DateTime, nullable=False)
    lease_ate = db.Column(db.DateTime)
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    antecipada = db.Column(db.Boolean, nullable=False, default=False)
    motivo = db.Column(db.String(500), nullable=False)
    erro = db.Column(db.String(100))
    concluida_em = db.Column(db.DateTime)
    assinatura = db.relationship('Assinatura')