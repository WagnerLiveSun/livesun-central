from flask import Blueprint
admin = Blueprint('admin', __name__)
from . import auth, dashboard, catalogo, assinaturas, cobrancas, webhooks, auditoria
from . import operacao
from . import cadastros