from app.extensions import db
from .base import Base


class Produto(Base):
    __tablename__ = 'produtos'
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    url_producao = db.Column(db.String(500))
    url_webhook = db.Column(db.String(500))
    versao_api = db.Column(db.String(20), nullable=False, default='v1')
    webhook_secret = db.Column(db.Text)  # Fernet; nunca texto puro
    permite_multiplos_planos = db.Column(db.Boolean, nullable=False, default=False)
    permite_modulos = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    token_version = db.Column(db.Integer, nullable=False, default=1)
    config_asaas_id = db.Column(db.Integer, db.ForeignKey('config_asaas_assinaturas.id'))
    config_asaas = db.relationship('ConfigAsaas', foreign_keys=[config_asaas_id])
    planos = db.relationship('Plano', backref='produto', lazy='selectin')
    modulos = db.relationship('Modulo', backref='produto', lazy='selectin')