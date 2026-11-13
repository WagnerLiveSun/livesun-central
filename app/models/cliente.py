from app.extensions import db
from .base import Base


class Cliente(Base):
    __tablename__ = 'clientes'
    codigo_externo = db.Column(db.String(100), unique=True, nullable=False)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj_cpf = db.Column(db.String(18))
    email_principal = db.Column(db.String(254), nullable=False)
    telefone = db.Column(db.String(30))
    status = db.Column(db.String(20), nullable=False, default='ATIVO')
    observacoes = db.Column(db.Text)