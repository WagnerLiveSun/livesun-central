from flask import Blueprint
api = Blueprint('api', __name__, url_prefix='/api/v1')
from . import health, produtos, entitlements, assinaturas, webhooks
from . import asaas
from . import cadastros