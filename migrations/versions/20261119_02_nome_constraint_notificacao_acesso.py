"""Alinhar nome da constraint existente de notificacoes_acesso sem alterar dados."""
from alembic import op

revision = '20261119_02'
down_revision = '20261119_01'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            'ALTER TABLE notificacoes_acesso '
            'DROP CONSTRAINT IF EXISTS notificacoes_acesso_evento_id_key')
        op.execute(
            'ALTER TABLE notificacoes_acesso '
            'ADD CONSTRAINT uq_notificacoes_acesso_evento_id '
            'UNIQUE (evento_id)')
    elif bind.dialect.name == 'mysql':
        op.execute(
            'ALTER TABLE notificacoes_acesso '
            'DROP INDEX notificacoes_acesso_evento_id')
        op.execute(
            'ALTER TABLE notificacoes_acesso '
            'ADD UNIQUE INDEX uq_notificacoes_acesso_evento_id (evento_id)')


def downgrade():
    raise RuntimeError('Preserve dados e constraints; use migration corretiva.')
