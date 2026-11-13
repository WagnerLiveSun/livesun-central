"""Exporta migrations offline e seed portavel. Nunca conecta aos bancos de destino."""
from datetime import datetime
from io import StringIO
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
import sqlalchemy as sa
from app import create_app
from app.extensions import db
from app.models import Produto, Plano

ROOT = Path(__file__).resolve().parent.parent


def seed_sql(dialect):
    # Sem IDs fixos, segredos, clientes ou usuarios; pode repetir sem duplicar.
    timestamp = datetime(2026, 11, 12)
    product = Produto.__table__
    plan = Plano.__table__
    product_values = {
        'codigo': 'PROPOSTAS', 'nome': 'LiveSun Propostas',
        'url_producao': 'https://propostas.livesun.com.br',
        'url_webhook': 'https://propostas.livesun.com.br/webhooks/assinatura',
        'versao_api': 'v1', 'permite_multiplos_planos': False, 'permite_modulos': False,
        'ativo': True, 'token_version': 1, 'criado_em': timestamp, 'atualizado_em': timestamp,
    }
    missing_product = ~sa.exists(sa.select(product.c.id).where(product.c.codigo == 'PROPOSTAS'))
    first = product.insert().from_select(list(product_values), sa.select(
        *[sa.literal(value) for value in product_values.values()]).where(missing_product), include_defaults=False)
    product_id = sa.select(product.c.id).where(product.c.codigo == 'PROPOSTAS').scalar_subquery()
    plan_values = {
        'produto_id': product_id, 'codigo': 'PROPOSTAS', 'nome': 'LiveSun Propostas',
        'descricao': 'Plano único do LiveSun Propostas', 'valor_mensal': 0,
        'periodicidade': 'mensal', 'limite_personalizado_json': '{}', 'ativo': True,
        'criado_em': timestamp, 'atualizado_em': timestamp,
    }
    # Impede criar um segundo plano ativo se o produto ja foi configurado manualmente.
    missing_plan = ~sa.exists(sa.select(plan.c.id).where(plan.c.produto_id == product_id,
        sa.or_(plan.c.codigo == 'PROPOSTAS', plan.c.ativo.is_(True))))
    second = plan.insert().from_select(list(plan_values), sa.select(
        *[v if isinstance(v, sa.sql.ClauseElement) else sa.literal(v) for v in plan_values.values()]
    ).where(missing_plan), include_defaults=False)
    statements = [str(statement.compile(dialect=dialect, compile_kwargs={'literal_binds': True})) + ';'
                  for statement in (first, second)]
    return '-- Seed inicial idempotente; sem credenciais ou operadores.\nBEGIN;\n' + '\n\n'.join(statements) + '\nCOMMIT;\n'


def export():
    paths = []
    for engine, url, folder in (
        ('mysql', 'mysql+pymysql://localhost/central', 'mysql'),
        ('postgresql', 'postgresql+psycopg://localhost/central', 'postgresql'),
    ):
        app = create_app({'TESTING': True, 'APP_ENV': 'development', 'DB_ENGINE': engine,
            'DATABASE_URL': url, 'SECRET_KEY': 's'*40, 'JWT_SECRET': 'j'*40,
            'ENCRYPTION_KEY': Fernet.generate_key().decode()})
        with app.app_context():
            output = StringIO()
            config = Config(str(ROOT/'migrations'/'alembic.ini'), output_buffer=output)
            config.set_main_option('script_location', str(ROOT/'migrations'))
            command.upgrade(config, 'head', sql=True)
            destination = ROOT/'deploy'/'sql'/folder
            destination.mkdir(parents=True, exist_ok=True)
            schema_path = destination/'01_estrutura_inicial.sql'
            schema_path.write_text('-- INSTALACAO EM BANCO VAZIO. Nao reaplicar em banco migrado.\n'
                '-- Gerado das migrations Alembic. Nao contem credenciais nem dados de testes.\n'
                + ('SET NAMES utf8mb4;\n\n' if engine == 'mysql' else '') + output.getvalue(), encoding='utf-8')
            seed_path = destination/'02_seed_propostas.sql'
            seed_path.write_text(seed_sql(db.engine.dialect), encoding='utf-8')
            paths.extend([schema_path, seed_path])
            incremental = StringIO()
            config.output_buffer = incremental
            command.upgrade(config, '20261112_01:head', sql=True)
            incremental_path = destination/'03_atualizar_20261112_01_para_head.sql'
            incremental_path.write_text('-- SOMENTE bancos na revisao 20261112_01. Backup antes de aplicar.\n'+incremental.getvalue(),encoding='utf-8')
            paths.append(incremental_path)
            current_incremental = StringIO()
            config.output_buffer = current_incremental
            command.upgrade(config, '20261112_02:head', sql=True)
            current_path = destination/'04_atualizar_20261112_02_para_head.sql'
            current_path.write_text('-- SOMENTE bancos na revisao 20261112_02.\n'+current_incremental.getvalue(),encoding='utf-8')
            paths.append(current_path)
            latest_incremental = StringIO()
            config.output_buffer = latest_incremental
            command.upgrade(config, '20261112_03:head', sql=True)
            latest_path = destination/'05_atualizar_20261112_03_para_head.sql'
            latest_path.write_text('-- SOMENTE bancos na revisao 20261112_03.\n'+latest_incremental.getvalue(),encoding='utf-8')
            paths.append(latest_path)
    return paths


if __name__ == '__main__':
    for path in export():
        print(path)