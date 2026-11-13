"""Gera revisão a partir da cadeia existente, somente em SQLite temporário."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet
from flask_migrate import upgrade, migrate
from app import create_app
from app.extensions import db


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        app=create_app({'TESTING':True,'APP_ENV':'development','DATABASE_URL':'sqlite:///'+str(Path(folder)/'migration.db'),
            'DB_ENGINE':'sqlite','SECRET_KEY':'s'*40,'JWT_SECRET':'j'*40,'ENCRYPTION_KEY':Fernet.generate_key().decode()})
        with app.app_context():
            upgrade()
            migrate(message='integracao comercial asaas e purga por produto',rev_id='20261112_02')
            db.session.remove()
            db.engine.dispose()