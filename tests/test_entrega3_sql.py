import importlib.util
from io import StringIO
from pathlib import Path
import re
from alembic.operations import Operations
from alembic.migration import MigrationContext

ROOT = Path(__file__).resolve().parents[1]


def test_postgresql_sql_matches_migration():
    path = ROOT / 'migrations/versions/20261118_01_notificacao_acesso.py'
    spec = importlib.util.spec_from_file_location('notification_migration_test', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    out = StringIO()
    ctx = MigrationContext.configure(dialect_name='postgresql', opts={'as_sql': True, 'output_buffer': out})
    with Operations.context(ctx):
        module.upgrade()
    sql = (ROOT / 'deploy/sql/postgresql/06_entrega_3_notificacoes.sql').read_text(encoding='utf-8')
    norm = lambda value: re.sub(r'\s+', ' ', value).strip()
    assert norm(out.getvalue()) in norm(sql)
    assert 'BEGIN;' in sql and 'COMMIT;' in sql
    assert 'INSERT INTO notificacoes_acesso' not in sql
    assert "version_num='20261118_01' WHERE version_num='20261112_04'" in sql