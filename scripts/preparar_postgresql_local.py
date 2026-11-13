"""Prepara banco PostgreSQL local sem apagar tabelas ou transferir dados de outro banco."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prepare(env_file):
    from dotenv import load_dotenv
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url
    load_dotenv(env_file, override=True)
    url = make_url(os.environ['DATABASE_URL'])
    if os.environ.get('DB_ENGINE') != 'postgresql' or url.drivername != 'postgresql+psycopg':
        raise RuntimeError('O perfil deve selecionar postgresql+psycopg.')
    if url.host not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('Este preparador é exclusivo de banco local.')
    if not url.database or url.database in ('postgres', 'template0', 'template1'):
        raise RuntimeError('Informe um banco exclusivo do Central, não um banco de manutenção.')
    params = dict(host=url.host, port=url.port or 5432, user=url.username, password=url.password,
                  connect_timeout=5, **dict(url.query))
    with psycopg.connect(dbname='postgres', autocommit=True, **params) as conn:
        exists = conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', (url.database,)).fetchone()
        if not exists:
            conn.execute(sql.SQL('CREATE DATABASE {} ENCODING {} TEMPLATE template0').format(
                sql.Identifier(url.database), sql.Literal('UTF8')))
            print('Banco exclusivo criado: ' + url.database)
        else:
            print('Banco existente preservado: ' + url.database)
    from app import create_app
    from app.extensions import db
    from flask_migrate import upgrade, check
    from sqlalchemy import inspect, text
    from app.cli import seed, seed_comercial
    app = create_app()
    if app.config['APP_ENV'] != 'development':
        raise RuntimeError('Este preparador é exclusivo de desenvolvimento.')
    with app.app_context():
        try:
            tables = set(inspect(db.engine).get_table_names())
            if tables and 'alembic_version' not in tables:
                raise RuntimeError('Banco não vazio sem revisão Alembic. Preparação interrompida para preservar dados.')
            unexpected = tables - set(db.metadata.tables) - {'alembic_version'}
            if unexpected:
                raise RuntimeError('Há tabelas externas ao Central. Utilize banco exclusivo.')
            upgrade()
            check()
            seed()
            seed_comercial()
            with db.engine.connect() as conn:
                database = conn.execute(text('SELECT current_database()')).scalar_one()
                revision = conn.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
                conn.execute(text('SELECT 1'))
            print('Conexão confirmada: ' + database)
            print('Revisão Alembic: ' + revision)
            print('Tabelas presentes: ' + str(len(inspect(db.engine).get_table_names())))
            print('Migrations e seed conferidos. Nenhum dado MySQL copiado e nenhum operador padrão criado.')
        finally:
            db.session.remove()
            db.engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', default='.env.postgresql')
    args = parser.parse_args()
    path = Path(args.env_file)
    path = path if path.is_absolute() else ROOT / path
    if not path.is_file():
        print('Arquivo de ambiente PostgreSQL não encontrado.', file=sys.stderr)
        return 1
    try:
        prepare(path)
    except Exception as error:
        # Exceções de drivers podem incluir credenciais ou dados. Não imprimir detalhes livres.
        print('Preparação interrompida. Confira conexão, exclusividade do banco e migrations. Tipo: '
              + type(error).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())