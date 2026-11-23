"""Gera SQL PostgreSQL offline a partir das migrations e do catálogo versionado."""
from io import StringIO
from pathlib import Path
import importlib.util

from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'deploy' / 'sql' / 'postgresql' / '07_instituicoes_e_gateway_20261119_03_para_20261123_02.sql'


def migration_sql(filename):
    path = ROOT / 'migrations' / 'versions' / filename
    spec = importlib.util.spec_from_file_location('migration_offline_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = StringIO()
    context = MigrationContext.configure(dialect_name='postgresql',
        opts={'as_sql': True, 'output_buffer': output, 'literal_binds': True})
    with Operations.context(context):
        module.upgrade()
    return '\n'.join(line.rstrip() for line in output.getvalue().splitlines()) + '\n'


def generate():
    parts = [
        '-- Central PostgreSQL: 20261119_03 -> 20261123_02. Banco exclusivo do Central.',
        '-- Catálogo: snapshot do Comercial 042; não consulta a internet nem altera o Comercial.',
        '-- Backup obrigatório. Executar em cliente SQL com parada em erro.',
        '-- Atualiza Alembic somente após criar a estrutura e inserir os dados.',
        'BEGIN;',
        "DO $$ BEGIN IF (SELECT COUNT(*) FROM alembic_version) <> 1 OR NOT EXISTS "
        "(SELECT 1 FROM alembic_version WHERE version_num = '20261119_03') THEN "
        "RAISE EXCEPTION 'Revisão divergente: esperado 20261119_03'; END IF; END $$;",
        migration_sql('20261123_01_gateway_alternativo.py'),
        migration_sql('20261123_02_instituicoes_bancarias.py'),
        "UPDATE alembic_version SET version_num='20261123_02' WHERE version_num='20261119_03';",
        'COMMIT;',
        '-- Conferência após COMMIT:',
        'SELECT version_num FROM alembic_version;',
        'SELECT COUNT(*) AS instituicoes FROM instituicoes_bancarias;',
    ]
    return '\n\n'.join(parts) + '\n'


if __name__ == '__main__':
    OUTPUT.write_text(generate(), encoding='utf-8')
    print(f'SQL offline gerado em {OUTPUT}')