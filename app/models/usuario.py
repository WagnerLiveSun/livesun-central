from flask_login import UserMixin
from app.extensions import db
from .base import Base

PERFIS = ('superadmin', 'comercial', 'financeiro', 'suporte', 'auditor')


class UsuarioCentral(UserMixin, Base):
    __tablename__ = 'usuarios_central'
    nome = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def is_active(self):
        return self.ativo