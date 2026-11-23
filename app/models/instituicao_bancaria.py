from app.extensions import db
from .base import now


class InstituicaoBancaria(db.Model):
    __tablename__ = 'instituicoes_bancarias'

    codigo_banco = db.Column(db.String(3), primary_key=True)
    nome_banco = db.Column(db.String(150), nullable=False)
    criado_em = db.Column(db.DateTime, nullable=False, default=now, server_default=db.func.current_timestamp())