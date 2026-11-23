"""Catálogo de instituições baseado no Comercial e vínculo opcional ao gateway."""
import json
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = '20261123_02'
down_revision = '20261123_01'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('instituicoes_bancarias',
        sa.Column('codigo_banco', sa.String(3), nullable=False),
        sa.Column('nome_banco', sa.String(150), nullable=False),
        sa.Column('criado_em', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('codigo_banco', name='pk_instituicoes_bancarias'))
    table = sa.table('instituicoes_bancarias',
        sa.column('codigo_banco', sa.String(3)), sa.column('nome_banco', sa.String(150)))
    path = Path(__file__).resolve().parents[2] / 'app' / 'data' / 'instituicoes_bancarias.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    op.bulk_insert(table, rows)
    with op.batch_alter_table('gateways_alternativos') as batch:
        batch.add_column(sa.Column('codigo_banco', sa.String(3), nullable=True))
        batch.create_foreign_key('fk_gateways_alternativos_codigo_banco_instituicoes_bancarias',
                                 'instituicoes_bancarias', ['codigo_banco'], ['codigo_banco'])
        batch.create_index('ix_gateways_alternativos_codigo_banco', ['codigo_banco'])


def downgrade():
    raise RuntimeError('Downgrade desabilitado; preserve vínculos e catálogo de instituições.')