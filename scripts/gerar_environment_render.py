"""Gera arquivo privado para Environment, sem copiar senhas ou dados locais."""
from pathlib import Path
import secrets
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]


def generate():
    destination = ROOT / '.env.render'
    if destination.exists():
        print('Arquivo .env.render já existe; preservado sem substituir chaves.')
        return destination
    values = {
        'APP_ENV': 'production',
        'PYTHON_VERSION': '3.12.10',
        'DB_ENGINE': 'postgresql',
        'DATABASE_URL': 'PREENCHER_URL_POSTGRESQL_ACESSIVEL_PELO_RENDER',
        'SECRET_KEY': secrets.token_urlsafe(48),
        'JWT_SECRET': secrets.token_urlsafe(48),
        'ENCRYPTION_KEY': Fernet.generate_key().decode(),
        'WEBHOOK_ALLOWED_HOSTS': 'propostas.livesun.com.br,app.livesun.com.br',
        'WEBHOOK_ALLOW_LOCAL_HTTP': 'false',
        'TRUST_PROXY': 'true',
    }
    # Modo exclusivo impede substituir arquivo existente por acidente.
    with destination.open('x', encoding='utf-8') as stream:
        stream.write('# PRIVADO: não versionar nem compartilhar. Instalação com banco vazio.\n')
        for name, value in values.items():
            stream.write(name + '=' + value + '\n')
        stream.write('# BOOTSTRAP_ADMIN_EMAIL=\n# BOOTSTRAP_ADMIN_NAME=Administrador\n# BOOTSTRAP_ADMIN_PASSWORD=\n')
    print('Arquivo privado .env.render criado. Complete PostgreSQL antes de usar no Render; Redis é opcional.')
    print('Chaves geradas sem exibição no terminal; configurações locais preservadas.')
    return destination


if __name__ == '__main__':
    generate()