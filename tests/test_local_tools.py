from pathlib import Path
import importlib.util
from unittest.mock import patch
import pytest
from sqlalchemy.dialects import mysql, postgresql

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('dialect', [mysql.dialect(), postgresql.dialect()])
def test_exported_seed_contains_no_secrets(dialect):
    sql = load('exportar_sql').seed_sql(dialect)
    assert 'PROPOSTAS' in sql
    assert 'NOT (EXISTS' in sql
    assert 'INSERT INTO produtos' in sql and 'INSERT INTO planos' in sql
    assert 'INSERT INTO usuarios_central' not in sql
    assert 'webhook_secret' not in sql
    assert 'DROP ' not in sql


def test_bootstrap_rejects_unversioned_nonempty_database(app):
    module = load('iniciar_local')
    # Fixture possui tabelas sem alembic_version: nao assumir controle silenciosamente.
    with pytest.raises(RuntimeError, match='sem controle Alembic'):
        module.check_database(app)


def test_batch_launcher_exists_and_forwards_arguments():
    batch = (ROOT.parent/'Iniciar_LiveSun_Central.bat').read_text(encoding='utf-8')
    assert '%~dp0livesun-central' in batch
    assert 'scripts\\iniciar_local.py %*' in batch
    assert 'livesun@' not in batch