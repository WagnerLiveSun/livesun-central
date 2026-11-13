"""Único ponto de configuração de banco. SQLite permitido somente nos testes."""
from sqlalchemy.engine import make_url


def configure_database(app):
    url = make_url(app.config['DATABASE_URL'])
    expected = {'mysql': 'mysql+pymysql', 'postgresql': 'postgresql+psycopg'}
    if app.testing:
        expected['sqlite'] = 'sqlite'
    if expected.get(app.config['DB_ENGINE']) != url.drivername:
        raise RuntimeError('DB_ENGINE e driver de DATABASE_URL incompatíveis.')
    options = {'pool_pre_ping': True, 'hide_parameters': True}
    if url.get_backend_name() != 'sqlite':
        options.update(pool_recycle=280, pool_size=5, max_overflow=5)
    if url.get_backend_name() == 'mysql':
        options['connect_args'] = {'charset': 'utf8mb4'}
        if app.config.get('DB_SSL_CA'):
            options['connect_args']['ssl'] = {'ca': app.config['DB_SSL_CA'], 'check_hostname': True}
    app.config.update(SQLALCHEMY_DATABASE_URI=url, SQLALCHEMY_ENGINE_OPTIONS=options,
                      SQLALCHEMY_TRACK_MODIFICATIONS=False, SQLALCHEMY_ECHO=False)