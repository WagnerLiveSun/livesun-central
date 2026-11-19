from app.extensions import db
from .base import Base, STATUSES


class Assinatura(Base):
    __tablename__ = 'assinaturas'
    __table_args__ = (
        db.UniqueConstraint('cliente_id', 'produto_id', 'slot_vigente'),
        db.CheckConstraint('status IN (' + ','.join(repr(s) for s in STATUSES) + ')', name='status_valido'),
        db.UniqueConstraint('asaas_ambiente', 'asaas_subscription_id',
                            name='uq_assinaturas_asaas_ambiente_subscription_id'),
    )
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False, index=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=False)
    plano_id = db.Column(db.Integer, db.ForeignKey('planos.id'), nullable=False)
    status = db.Column(db.String(32), nullable=False, default='TRIAL')
    # 1 para vigente; NULL para encerrada. Unique portável evita duplicação concorrente.
    slot_vigente = db.Column(db.Integer, nullable=True, default=1)
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date)
    data_proxima_cobranca = db.Column(db.Date)
    motivo_status = db.Column(db.String(500))
    versao = db.Column(db.Integer, nullable=False, default=1)
    excluida_em = db.Column(db.DateTime)
    trial_ate = db.Column(db.Date)
    cortesia = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    cortesia_ate = db.Column(db.Date)
    carencia_dias = db.Column(db.Integer, nullable=False, default=7, server_default='7')
    suspensa_por_inadimplencia = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    asaas_ambiente = db.Column(db.String(20))
    asaas_customer_id = db.Column(db.String(100))
    asaas_subscription_id = db.Column(db.String(100), index=True)
    asaas_habilitado = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    asaas_forma = db.Column(db.String(20), nullable=False, default='BOLETO', server_default='BOLETO')
    liberado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios_central.id'), index=True)
    liberado_em = db.Column(db.DateTime)
    codigo_legado = db.Column(db.String(100))
    cliente = db.relationship('Cliente')
    produto = db.relationship('Produto')
    plano = db.relationship('Plano')
    liberado_por = db.relationship('UsuarioCentral', foreign_keys=[liberado_por_id])


class AssinaturaModulo(Base):
    __tablename__ = 'assinatura_modulos'
    __table_args__ = (db.UniqueConstraint('assinatura_id', 'modulo_id'),)
    assinatura_id = db.Column(db.Integer, db.ForeignKey('assinaturas.id'), nullable=False)
    modulo_id = db.Column(db.Integer, db.ForeignKey('modulos.id'), nullable=False)
    liberado = db.Column(db.Boolean, nullable=False, default=True)
    limite = db.Column(db.Integer)
    data_liberacao = db.Column(db.DateTime)
    data_remocao = db.Column(db.DateTime)
    modulo = db.relationship('Modulo')