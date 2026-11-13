"""Migrations/seed antes da API, dentro do túnel autenticado pelo supervisor."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class PreparationError(RuntimeError):
    """Falha já diagnosticada sem incluir valores ou exceções sensíveis."""


def stage(name, action, hint):
    print(json.dumps({'event': 'preparation_stage_started', 'stage': name}), flush=True)
    try:
        return action()
    except Exception:
        print(json.dumps({'event': 'preparation_stage_failed', 'stage': name,
                          'hint': hint}), file=sys.stderr, flush=True)
        raise PreparationError() from None


def validate_environment():
    from flask import Flask
    from app.config import configure
    from cryptography.fernet import Fernet
    import os
    for key in ('SECRET_KEY', 'JWT_SECRET', 'ENCRYPTION_KEY'):
        stage(key, lambda key=key: require_secret(os.environ.get(key)),
              f'Configure {key} no Environment; não use texto de exemplo.')
    app = Flask(__name__)
    stage('app_configuration', lambda: configure(app),
          'Confira APP_ENV, chaves com pelo menos 32 caracteres, Redis compartilhado em produção e HTTPS dos webhooks.')
    stage('encryption_key', lambda: Fernet(app.config['ENCRYPTION_KEY'].encode()),
          'ENCRYPTION_KEY deve ser uma chave Fernet válida. Preserve a chave que criptografou os dados existentes.')


def require_secret(value):
    if not value or not value.strip():
        raise PreparationError()


def main():
    from app import create_app
    from app.extensions import db
    from flask_migrate import upgrade
    from app.cli import seed, seed_comercial, bootstrap_admin
    from sqlalchemy import inspect
    validate_environment()
    app = stage('create_app', create_app,
                'Confira driver do banco, configuração do rate limit/Redis e dependências da aplicação.')
    with app.app_context():
        try:
            def validate_schema():
                tables = set(inspect(db.engine).get_table_names())
                if tables and 'alembic_version' not in tables:
                    raise PreparationError()
                if tables - set(db.metadata.tables) - {'alembic_version'}:
                    raise PreparationError()
            stage('schema_validation', validate_schema,
                  'Confira conexão, permissões e banco exclusivo do Central com controle Alembic. Não apague tabelas.')
            stage('migrations', upgrade, 'Confira revisões Alembic e permissões DDL. Não recrie o banco.')
            stage('seed_propostas', seed, 'Confira catálogo, constraints e PROPOSTAS_WEBHOOK_SECRET (mínimo 32 caracteres).')
            stage('seed_comercial', seed_comercial, 'Confira catálogo e constraints do produto Comercial.')
            stage('bootstrap_admin', bootstrap_admin,
                  'Confira BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD e BOOTSTRAP_ADMIN_NAME, se configurados.')
            print('Migrations e seed concluídos pelo túnel SSH.', flush=True)
            return 0
        finally:
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Preparação interrompida. Confira banco, migrations e variáveis do Central.', file=sys.stderr)
        sys.exit(1)