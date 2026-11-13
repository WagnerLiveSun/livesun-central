"""Pré-deploy executado dentro de túnel autenticado pelo supervisor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    from app import create_app
    from app.extensions import db
    from flask_migrate import upgrade
    from app.cli import seed, seed_comercial, bootstrap_admin
    from sqlalchemy import inspect
    app = create_app()
    with app.app_context():
        try:
            tables = set(inspect(db.engine).get_table_names())
            if tables and 'alembic_version' not in tables:
                raise RuntimeError('Banco não vazio sem controle Alembic.')
            if tables - set(db.metadata.tables) - {'alembic_version'}:
                raise RuntimeError('Banco deve ser exclusivo do Central.')
            upgrade()
            seed()
            seed_comercial()
            bootstrap_admin()
            print('Migrations e seed concluídos pelo túnel SSH.', flush=True)
            return 0
        finally:
            db.session.remove()
            db.engine.dispose()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('Pré-deploy interrompido. Confira banco, migrations e variáveis do Central.', file=sys.stderr)
        sys.exit(1)