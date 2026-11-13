from io import StringIO
from pathlib import Path
import importlib.util
import pytest
from cryptography.fernet import Fernet
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from app import create_app
from app.extensions import db

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize('engine,url', [
    ('mysql', 'mysql+pymysql://test:test@localhost/test_central'),
    ('postgresql', 'postgresql+psycopg://test:test@localhost/test_central'),
])
def test_migration_offline_dialects(engine, url):
    app = create_app({'TESTING': True, 'DB_ENGINE': engine, 'DATABASE_URL': url,
        'SECRET_KEY': 's'*40, 'JWT_SECRET': 'j'*40, 'ENCRYPTION_KEY': Fernet.generate_key().decode()})
    with app.app_context():
        output = StringIO()
        config = Config(str(ROOT/'migrations'/'alembic.ini'), output_buffer=output)
        config.set_main_option('script_location', str(ROOT/'migrations'))
        command.upgrade(config, 'head', sql=True)
        sql = output.getvalue()
        assert 'CREATE TABLE assinaturas' in sql
        assert 'CREATE TABLE webhook_entregas' in sql
        assert 'slot_vigente' in sql


def test_upgrade_empty_database(tmp_path):
    path = tmp_path/'migration.db'
    app = create_app({'TESTING': True, 'DB_ENGINE': 'sqlite', 'DATABASE_URL': 'sqlite:///'+str(path),
        'SECRET_KEY': 's'*40, 'JWT_SECRET': 'j'*40, 'ENCRYPTION_KEY': Fernet.generate_key().decode()})
    with app.app_context():
        from flask_migrate import upgrade, check
        upgrade()
        check()
        assert set(inspect(db.engine).get_table_names()) == set(db.metadata.tables) | {'alembic_version'}
        from app.cli import seed
        seed()
        seed()
        from app.models import Produto, Plano
        assert db.session.scalar(db.select(db.func.count()).select_from(Produto)) == 1
        assert db.session.scalar(db.select(db.func.count()).select_from(Plano)) == 1


def test_upgrade_existing_subscription_preserves_data(tmp_path):
    path = tmp_path/'existing.db'
    app = create_app({'TESTING':True,'APP_ENV':'development','DB_ENGINE':'sqlite','DATABASE_URL':'sqlite:///'+str(path),
        'SECRET_KEY':'s'*40,'JWT_SECRET':'j'*40,'ENCRYPTION_KEY':Fernet.generate_key().decode()})
    with app.app_context():
        from flask_migrate import upgrade, check
        from sqlalchemy import text
        upgrade(revision='20261112_01')
        with db.engine.begin() as conn:
            conn.execute(text("INSERT INTO clientes (id,codigo_externo,razao_social,email_principal,status,criado_em,atualizado_em) VALUES (1,'LEG','Legado','leg@example.com','ATIVO',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO produtos (id,codigo,nome,versao_api,permite_multiplos_planos,permite_modulos,ativo,token_version,criado_em,atualizado_em) VALUES (1,'LEGADO','Legado','v1',0,0,1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO planos (id,produto_id,codigo,nome,valor_mensal,periodicidade,limite_personalizado_json,ativo,criado_em,atualizado_em) VALUES (1,1,'LEGADO','Legado',49,'mensal','{}',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO assinaturas (id,cliente_id,produto_id,plano_id,status,slot_vigente,data_inicio,versao,criado_em,atualizado_em) VALUES (1,1,1,1,'ATIVA',1,'2026-11-01',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        upgrade()
        check()
        from app.models import Assinatura
        obj=db.session.get(Assinatura,1)
        assert obj.status=='ATIVA' and obj.carencia_dias==7
        assert not obj.asaas_habilitado and not obj.cortesia