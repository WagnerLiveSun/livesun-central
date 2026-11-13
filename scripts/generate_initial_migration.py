"""Geração inicial via autogenerate usando SOMENTE SQLite em memória."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cryptography.fernet import Fernet
from flask_migrate import migrate
from app import create_app

if __name__ == '__main__':
    app = create_app({'TESTING': True, 'DB_ENGINE': 'sqlite', 'DATABASE_URL': 'sqlite:///:memory:',
        'SECRET_KEY': 'm' * 40, 'JWT_SECRET': 'j' * 40, 'ENCRYPTION_KEY': Fernet.generate_key().decode()})
    with app.app_context():
        migrate(message='estrutura inicial independente', rev_id='20261112_01')