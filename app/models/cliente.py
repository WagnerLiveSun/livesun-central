from app.extensions import db
from .base import Base


class Cliente(Base):
    __tablename__ = 'clientes'
    __table_args__ = (
        db.UniqueConstraint('asaas_sandbox_customer_id',
                            name='uq_clientes_asaas_sandbox_customer_id'),
        db.UniqueConstraint('asaas_producao_customer_id',
                            name='uq_clientes_asaas_producao_customer_id'),
    )
    codigo_externo = db.Column(db.String(100), unique=True, nullable=False)
    razao_social = db.Column(db.String(200), nullable=False)
    nome_fantasia = db.Column(db.String(200))
    cnpj_cpf = db.Column(db.String(18))
    email_principal = db.Column(db.String(254), nullable=False)
    telefone = db.Column(db.String(30))
    # IDs externos separados por ambiente evitam reutilização de IDs sandbox em produção.
    asaas_sandbox_customer_id = db.Column(db.String(100), index=True)
    asaas_producao_customer_id = db.Column(db.String(100), index=True)
    status = db.Column(db.String(20), nullable=False, default='ATIVO')
    observacoes = db.Column(db.Text)