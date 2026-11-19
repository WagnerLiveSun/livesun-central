"""Amplia status sem modificar registros; aplicação depende de aprovação."""
from alembic import op
import sqlalchemy as sa

revision = '20261119_03'
down_revision = '20261119_02'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assinaturas') as batch:
        batch.alter_column('status', existing_type=sa.String(20),
                           type_=sa.String(32), existing_nullable=False)


def downgrade():
    raise RuntimeError('Downgrade desabilitado; preserve o esquema e retorne somente o código compatível.')