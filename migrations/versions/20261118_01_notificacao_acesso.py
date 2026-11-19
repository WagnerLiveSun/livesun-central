"""Notificações de acesso PROPOSTAS, sem disparos retroativos."""
from alembic import op
import sqlalchemy as sa

revision = '20261118_01'
down_revision = '20261112_04'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notificacoes_acesso',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('evento_id', sa.String(50), sa.ForeignKey('eventos_assinatura.evento_id'), nullable=False, unique=True),
        sa.Column('assinatura_id', sa.Integer(), sa.ForeignKey('assinaturas.id'), nullable=False),
        sa.Column('destinatario_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(25), nullable=False),
        sa.Column('criada_em', sa.DateTime(), nullable=False),
        sa.Column('proxima_tentativa', sa.DateTime(), nullable=False),
        sa.Column('lease_ate', sa.DateTime()),
        sa.Column('tentativas', sa.Integer(), nullable=False))
    op.create_table('tentativas_notificacao_acesso',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('notificacao_id', sa.Integer(), sa.ForeignKey('notificacoes_acesso.id'), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('resultado', sa.String(25), nullable=False),
        sa.Column('categoria', sa.String(40)),
        sa.Column('iniciada_em', sa.DateTime(), nullable=False),
        sa.Column('concluida_em', sa.DateTime()))
    op.create_index('ix_tentativas_notificacao_acesso_notificacao_id', 'tentativas_notificacao_acesso', ['notificacao_id'])


def downgrade():
    raise RuntimeError('Rollback de código deve preservar tentativas e deduplicação de e-mails.')