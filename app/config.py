import os
from datetime import timedelta


def configure(app, overrides=None):
    app.config.from_mapping(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        JWT_SECRET=os.getenv('JWT_SECRET'),
        ENCRYPTION_KEY=os.getenv('ENCRYPTION_KEY'),
        APP_ENV=os.getenv('APP_ENV', 'development'),
        DB_ENGINE=os.getenv('DB_ENGINE', 'mysql'),
        DATABASE_URL=os.getenv('DATABASE_URL', 'mysql+pymysql://localhost/livesun_central'),
        DB_SSL_CA=os.getenv('DB_SSL_CA'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_NAME='livesun_central_session',
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=60),
        MAX_CONTENT_LENGTH=128 * 1024,
        ENTITLEMENT_TTL_SECONDS=900, WEBHOOK_MAX_ATTEMPTS=8,
        WEBHOOK_ALLOWED_HOSTS=os.getenv('WEBHOOK_ALLOWED_HOSTS', '').split(','),
        WEBHOOK_ALLOW_LOCAL_HTTP=os.getenv('WEBHOOK_ALLOW_LOCAL_HTTP', 'false').lower() == 'true',
        RATELIMIT_STORAGE_URI=os.getenv('RATELIMIT_STORAGE_URI', '').strip() or 'memory://',
        RATELIMIT_ENABLED=True,
        TRUST_PROXY=os.getenv('TRUST_PROXY') == 'true',
    )
    app.config.update(overrides or {})
    production = app.config['APP_ENV'] == 'production'
    if app.config['WEBHOOK_ALLOW_LOCAL_HTTP'] and app.config['APP_ENV'] != 'development':
        raise RuntimeError('WEBHOOK_ALLOW_LOCAL_HTTP é exclusivo de desenvolvimento. Produção exige HTTPS.')
    app.config['SESSION_COOKIE_SECURE'] = production
    for key in ('SECRET_KEY', 'JWT_SECRET', 'ENCRYPTION_KEY'):
        if not app.config.get(key):
            raise RuntimeError(f'Configure {key} no ambiente.')
    if len(app.config['SECRET_KEY']) < 32 or len(app.config['JWT_SECRET']) < 32:
        raise RuntimeError('SECRET_KEY e JWT_SECRET devem ter pelo menos 32 caracteres.')
    # Instância única: limites locais ativos, sem serviço adicional.
    # Para vários processos/instâncias, configurar backend compartilhado.