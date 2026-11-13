import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from cryptography.fernet import Fernet
from flask_wtf.csrf import CSRFError
from app.config import configure
from app.database import configure_database
from app.extensions import db, migrate, login, csrf, limiter
from app.security import SafeJSONFormatter


def create_app(overrides=None):
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / '.env')
    app = Flask(__name__, static_folder=str(root / 'static'))
    configure(app, overrides)
    Fernet(app.config['ENCRYPTION_KEY'].encode())  # falha cedo para chave inválida
    configure_database(app)
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSONFormatter())
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)
    if app.config['TRUST_PROXY']:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    db.init_app(app)
    migrate.init_app(app, db, directory=str(root / 'migrations'))
    login.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    from app.models import UsuarioCentral
    from app.api import api
    from app.admin import admin
    csrf.exempt(api)
    limiter.limit('120 per minute')(api)
    app.register_blueprint(api)
    app.register_blueprint(admin)
    login.login_view = 'admin.login_view'

    @login.user_loader
    def user_loader(identifier):
        try:
            user = db.session.get(UsuarioCentral, int(identifier))
        except ValueError:
            return None
        return user if user and user.ativo else None

    @app.before_request
    def require_https():
        if app.config['APP_ENV'] == 'production' and not request.is_secure and request.path != '/api/v1/health':
            return jsonify(error='HTTPS obrigatório.'), 400

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        # Flask-WTF valida Referer em POST HTTPS; omitir em todos os casos
        # bloqueia inclusive formulários legítimos. Não enviar a outros sites.
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if app.config['APP_ENV'] == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def error_response(message, status):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify(error=message), status
        return render_template('error.html', title='Não foi possível concluir', message=message), status

    @app.errorhandler(ValidationError)
    def invalid_schema(error):
        fields = ', '.join('.'.join(map(str, e['loc'])) for e in error.errors())
        return error_response('Campos inválidos: ' + fields, 422)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        app.logger.warning('csrf', extra={'safe_event':'form_csrf_rejected'})
        return error_response('A sessão do formulário expirou ou foi alterada. Atualize a página e tente novamente. '
                              'Se necessário, entre novamente no Central. Nenhum dado foi salvo por esta requisição.', 400)

    @app.errorhandler(ValueError)
    def invalid_value(error):
        from app.services.assinatura_service import BusinessError
        return error_response(str(error) if isinstance(error, BusinessError) else 'Entrada inválida.', 422)

    @app.errorhandler(IntegrityError)
    def conflict(error):
        return error_response('Registro duplicado ou vínculo inválido. Verifique assinatura vigente e códigos únicos.', 409)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return error_response({401: 'Autenticação necessária.', 403: 'Operação não permitida.',
                               404: 'Registro não encontrado.', 429: 'Muitas requisições.'}.get(error.code, 'Requisição inválida.'), error.code)

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.error('unexpected', extra={'safe_event': 'unexpected_error'})
        return error_response('Falha interna. Consulte o suporte.', 500)

    from app.cli import register_commands
    register_commands(app)
    return app