"""Relacionar configuração de cobrança ao produto."""
from alembic import op
import sqlalchemy as sa

revision='20261112_03'
down_revision='20261112_02'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('produtos') as batch:
        batch.add_column(sa.Column('config_asaas_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_produtos_config_asaas_id_config_asaas_assinaturas',
            'config_asaas_assinaturas',['config_asaas_id'],['id'])


def downgrade():
    raise RuntimeError('Preserve os vínculos; use migration corretiva.')